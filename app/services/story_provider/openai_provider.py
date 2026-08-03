from __future__ import annotations

import hashlib
import json
import os
import random
import time
from typing import Any

from dotenv import load_dotenv

from services.story_composer.models import Scene, Story
from services.story_composer.schema import story_structured_output_schema

from .base import StoryAIProvider
from .cost_estimator import StoryCostEstimator, pricing_snapshot
from .models import (
    CancellationToken,
    ConfigurationResult,
    ProgressCallback,
    ProviderCapabilities,
    StoryCostEstimate,
    StoryGenerationRequest,
    StoryGenerationResult,
    StoryProviderMetrics,
)


OPENAI_PROVIDER_VERSION = "1.0"


class StoryProviderError(RuntimeError):
    def __init__(self, message: str, error_code: str = "provider_error", retryable: bool = False, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable
        self.retry_after = retry_after


class OpenAIStoryProvider(StoryAIProvider):
    def __init__(self, client_factory=None, sleep_func=time.sleep, logger=None) -> None:
        self.client_factory = client_factory
        self.sleep_func = sleep_func
        self.logger = logger
        self.estimator = StoryCostEstimator()

    @property
    def provider_id(self) -> str:
        return "openai"

    @property
    def provider_name(self) -> str:
        return "OpenAI"

    @property
    def provider_version(self) -> str:
        return OPENAI_PROVIDER_VERSION

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(structured_outputs=True, reasoning_effort=True, temperature=False, streaming=False)

    def validate_configuration(self) -> ConfigurationResult:
        if not self._api_key():
            return ConfigurationResult(False, "OPENAI_API_KEYが設定されていません。", "missing_api_key")
        try:
            self._import_openai()
        except ModuleNotFoundError:
            return ConfigurationResult(False, "OpenAI Python SDKがインストールされていません。", "missing_openai_sdk")
        return ConfigurationResult(True, "OpenAI API configured")

    def estimate_cost(self, request: StoryGenerationRequest) -> StoryCostEstimate:
        return self.estimator.estimate_pre_request(request)

    def generate_story(
        self,
        request: StoryGenerationRequest,
        cancellation_token: CancellationToken | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> StoryGenerationResult:
        request.validate()
        config = self.validate_configuration()
        if not config.configured:
            return StoryGenerationResult(
                status="failed",
                provider=self.provider_id,
                provider_version=self.provider_version,
                model=request.model,
                error_code=config.error_code,
                error_message=config.message,
            )

        retry_count = 0
        max_retries = request.retry_count
        while True:
            if cancellation_token and cancellation_token.cancel_requested:
                return StoryGenerationResult(status="cancelled", provider=self.provider_id, provider_version=self.provider_version, model=request.model)
            try:
                if progress_callback:
                    progress_callback("OpenAIへStory生成をリクエスト中", 20)
                response = self._call_responses_api(request, cancellation_token)
                if cancellation_token and cancellation_token.cancel_requested:
                    return StoryGenerationResult(status="cancelled", provider=self.provider_id, provider_version=self.provider_version, model=request.model)
                story = self._story_from_response(response, request)
                metrics = self._metrics_from_response(response, request.model)
                if progress_callback:
                    progress_callback("Story構造を検証中", 80)
                return StoryGenerationResult(
                    story=story,
                    provider=self.provider_id,
                    provider_version=self.provider_version,
                    model=request.model,
                    metrics=metrics,
                    retry_count=retry_count,
                )
            except StoryProviderError as exc:
                if cancellation_token and cancellation_token.cancel_requested:
                    return StoryGenerationResult(status="cancelled", provider=self.provider_id, provider_version=self.provider_version, model=request.model)
                if not exc.retryable or retry_count >= max_retries:
                    return StoryGenerationResult(
                        status="failed",
                        provider=self.provider_id,
                        provider_version=self.provider_version,
                        model=request.model,
                        error_code=exc.error_code,
                        error_message=str(exc),
                        retry_count=retry_count,
                    )
                retry_count += 1
                if self.logger:
                    self.logger.info(
                        "story provider retry provider=openai model=%s retry=%s error_code=%s",
                        request.model,
                        retry_count,
                        exc.error_code,
                    )
                if progress_callback:
                    progress_callback(f"Retry {retry_count}/{max_retries}", 20)
                delay = exc.retry_after if exc.retry_after is not None else min(8.0, 2 ** retry_count) + random.uniform(0, 0.25)
                self.sleep_func(delay)

    def _call_responses_api(self, request: StoryGenerationRequest, cancellation_token: CancellationToken | None):
        client = self._client()
        payload: dict[str, Any] = {
            "model": self._safe_model(request.model),
            "instructions": self._instructions(),
            "input": [{"role": "user", "content": self._user_input(request)}],
            "text": {
                "format": {
                    "type": "json_schema",
                    "name": "story_response",
                    "strict": True,
                    "schema": story_structured_output_schema(max_scenes=request.max_scenes),
                }
            },
            "max_output_tokens": int(request.max_output_tokens),
        }
        if request.reasoning_effort and request.reasoning_effort != "none":
            payload["reasoning"] = {"effort": request.reasoning_effort}
        try:
            return client.responses.create(**payload)
        except Exception as exc:
            raise self._classify_exception(exc) from exc

    def _story_from_response(self, response: Any, request: StoryGenerationRequest) -> Story:
        self._check_response_status(response)
        parsed = getattr(response, "output_parsed", None)
        if parsed is not None:
            data = parsed if isinstance(parsed, dict) else self._object_to_dict(parsed)
        else:
            output_text = getattr(response, "output_text", "") or ""
            if not output_text.strip():
                raise StoryProviderError("OpenAIから空の応答が返りました。", "empty_response", False)
            try:
                data = json.loads(output_text)
            except json.JSONDecodeError as exc:
                raise StoryProviderError("Structured OutputsのJSONを読み取れませんでした。", "structured_output_missing", False) from exc
        if not isinstance(data, dict):
            raise StoryProviderError("Structured OutputsがStory objectではありません。", "structured_output_missing", False)
        raw_scenes = data.get("scenes", [])
        scenes = [Scene.from_dict(item) for item in raw_scenes if isinstance(item, dict)] if isinstance(raw_scenes, list) else []
        story = Story(
            project_id=request.project_id,
            theme=str(data.get("theme") or request.theme),
            title=str(data.get("title") or ""),
            description=str(data.get("description") or ""),
            hook=str(data.get("hook") or ""),
            summary=str(data.get("summary") or ""),
            estimated_duration=float(data.get("estimated_duration", request.target_duration_seconds) or request.target_duration_seconds),
            provider=self.provider_id,
            provider_version=self.provider_version,
            schema_version=str(data.get("schema_version") or "1.0"),
            story_prompt_version=str(data.get("story_prompt_version") or "1.0"),
            language=str(data.get("language") or request.language),
            status="json_imported",
            tags=[str(item).strip() for item in data.get("tags", []) if str(item).strip()] if isinstance(data.get("tags", []), list) else [],
            memo=str(data.get("memo") or ""),
            scenes=scenes,
            metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata"), dict) else {},
        )
        story.touch()
        return story

    def _check_response_status(self, response: Any) -> None:
        status = str(getattr(response, "status", "") or "")
        if status in {"cancelled"}:
            raise StoryProviderError("OpenAI requestがcancelledになりました。", "provider_cancelled", False)
        if status in {"incomplete"}:
            details = getattr(response, "incomplete_details", None)
            reason = str(getattr(details, "reason", "") or "")
            code = "max_output_reached" if "max" in reason else "incomplete_response"
            raise StoryProviderError("OpenAI responseが不完全です。", code, False)
        for item in getattr(response, "output", []) or []:
            for content in getattr(item, "content", []) or []:
                content_type = str(getattr(content, "type", "") or "")
                if "refusal" in content_type:
                    raise StoryProviderError("OpenAI modelがStory生成を拒否しました。", "provider_refusal", False)

    def _metrics_from_response(self, response: Any, model: str) -> StoryProviderMetrics:
        usage = getattr(response, "usage", None)
        input_tokens = self._int_attr(usage, "input_tokens")
        output_tokens = self._int_attr(usage, "output_tokens")
        total_tokens = self._int_attr(usage, "total_tokens")
        cached_input_tokens = None
        reasoning_tokens = None
        input_details = getattr(usage, "input_tokens_details", None)
        if input_details is not None:
            cached_input_tokens = self._int_attr(input_details, "cached_tokens")
        output_details = getattr(usage, "output_tokens_details", None)
        if output_details is not None:
            reasoning_tokens = self._int_attr(output_details, "reasoning_tokens")
        metrics = StoryProviderMetrics(
            input_tokens=input_tokens,
            cached_input_tokens=cached_input_tokens,
            output_tokens=output_tokens,
            reasoning_tokens=reasoning_tokens,
            total_tokens=total_tokens,
            response_id=str(getattr(response, "id", "") or "") or None,
            finish_reason=str(getattr(response, "status", "") or "") or None,
            pricing_snapshot=pricing_snapshot(model),
        )
        metrics.estimated_cost_usd = self.estimator.estimate_from_usage(model, metrics)
        return metrics

    def _classify_exception(self, exc: Exception) -> StoryProviderError:
        status_code = getattr(exc, "status_code", None)
        message = self._sanitize_error(str(exc))
        retry_after = None
        response = getattr(exc, "response", None)
        headers = getattr(response, "headers", {}) or {}
        try:
            retry_after = float(headers.get("retry-after")) if headers.get("retry-after") else None
        except Exception:
            retry_after = None
        if status_code in {408, 409, 429, 500, 502, 503, 504}:
            return StoryProviderError(message or "OpenAIの一時的なエラーです。", f"http_{status_code}", True, retry_after)
        if status_code in {401, 403}:
            return StoryProviderError("OpenAI API keyまたは権限に問題があります。", "auth_error", False)
        if status_code == 400:
            return StoryProviderError(message or "OpenAI requestが正しくありません。", "invalid_request", False)
        if "timeout" in message.lower():
            return StoryProviderError("OpenAI requestがtimeoutしました。", "timeout", True)
        if "billing" in message.lower() or "quota" in message.lower():
            return StoryProviderError("OpenAIのbillingまたはquotaに問題があります。", "billing_or_quota", False)
        return StoryProviderError(message or "OpenAI requestに失敗しました。", "provider_error", False)

    def _client(self):
        if self.client_factory:
            return self.client_factory()
        openai_mod = self._import_openai()
        return openai_mod.OpenAI(api_key=self._api_key())

    def _import_openai(self):
        import openai

        return openai

    def _api_key(self) -> str:
        load_dotenv()
        return os.environ.get("OPENAI_API_KEY", "").strip()

    def _safe_model(self, model: str) -> str:
        value = str(model or "").strip()
        if not value or len(value) > 120 or any(ord(ch) < 32 for ch in value):
            raise StoryProviderError("OpenAI model IDが正しくありません。", "invalid_model", False)
        return value

    def _instructions(self) -> str:
        return (
            "You are a Japanese short-video story composer. "
            "Return only data that matches the provided structured output schema. "
            "Do not add Markdown, explanations, or extra text. "
            "Keep claims careful and avoid excessive clickbait. "
            "Narration, subtitle, and image_prompt must not be empty."
        )

    def _user_input(self, request: StoryGenerationRequest) -> str:
        return (
            f"Theme: {request.theme}\n"
            f"Language: {request.language}\n"
            f"Target duration seconds: {request.target_duration_seconds:.1f}\n"
            f"Scene count range: {request.min_scenes}-{request.max_scenes}\n\n"
            "Create a vertical YouTube Shorts / TikTok documentary story. "
            "Start with a strong hook. Make each scene visually distinct. "
            "scene_index must start at 1 and be sequential. "
            "start_time, end_time, and duration must be consistent. "
            "Do not present speculation as fact. Stay on the requested theme."
        )

    def _object_to_dict(self, value: Any) -> dict[str, Any]:
        if hasattr(value, "model_dump"):
            return value.model_dump()
        if hasattr(value, "dict"):
            return value.dict()
        return dict(value)

    def _int_attr(self, obj: Any, name: str) -> int | None:
        if obj is None:
            return None
        value = getattr(obj, name, None)
        if isinstance(value, int):
            return value
        if isinstance(obj, dict) and isinstance(obj.get(name), int):
            return obj[name]
        return None

    def _sanitize_error(self, message: str) -> str:
        api_key = self._api_key()
        sanitized = message.replace(api_key, "[REDACTED]") if api_key else message
        return sanitized[:600]

    def prompt_hash(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
