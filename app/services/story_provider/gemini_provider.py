from __future__ import annotations

import json
import os
import random
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from services.story_composer.models import Scene, Story
from services.story_composer.schema import story_structured_output_schema

from .base import StoryAIProvider
from .gemini_free_tier_policy import GeminiFreeTierPolicy, api_key_fingerprint
from .gemini_model_catalog import default_gemini_model, get_gemini_model_metadata, validate_gemini_model_id
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


GEMINI_PROVIDER_VERSION = "1.0"
DEFAULT_LOCAL_DAILY_CAP = 10


class GeminiProviderError(RuntimeError):
    def __init__(self, message: str, error_code: str = "gemini_provider_error", retryable: bool = False, retry_after: float | None = None) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.retryable = retryable
        self.retry_after = retry_after


class GeminiUsageStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path

    def load(self) -> dict[str, Any]:
        date = datetime.now(timezone.utc).date().isoformat()
        default = {
            "date_utc": date,
            "request_attempt_count": 0,
            "successful_request_count": 0,
            "failed_request_count": 0,
            "input_tokens": 0,
            "output_tokens": 0,
            "quota_exhausted": False,
            "last_request_at": None,
        }
        if self.path is None or not self.path.exists():
            return default
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return default
        if not isinstance(data, dict) or data.get("date_utc") != date:
            return default
        return {**default, **data}

    def save(self, data: dict[str, Any]) -> None:
        if self.path is None:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        tmp.replace(self.path)

    def cap_reached(self, cap: int) -> bool:
        return int(self.load().get("request_attempt_count", 0) or 0) >= max(0, int(cap))

    def record_attempt(self) -> dict[str, Any]:
        data = self.load()
        data["request_attempt_count"] = int(data.get("request_attempt_count", 0) or 0) + 1
        data["last_request_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        self.save(data)
        return data

    def record_result(self, success: bool, metrics: StoryProviderMetrics | None = None, quota_exhausted: bool = False) -> dict[str, Any]:
        data = self.load()
        key = "successful_request_count" if success else "failed_request_count"
        data[key] = int(data.get(key, 0) or 0) + 1
        if metrics is not None:
            data["input_tokens"] = int(data.get("input_tokens", 0) or 0) + int(metrics.input_tokens or 0)
            data["output_tokens"] = int(data.get("output_tokens", 0) or 0) + int(metrics.output_tokens or 0)
        if quota_exhausted:
            data["quota_exhausted"] = True
        self.save(data)
        return data


class GeminiStoryProvider(StoryAIProvider):
    def __init__(self, client_factory=None, sleep_func=time.sleep, logger=None, usage_store: GeminiUsageStore | None = None) -> None:
        self.client_factory = client_factory
        self.sleep_func = sleep_func
        self.logger = logger
        self.policy = GeminiFreeTierPolicy()
        self.usage_store = usage_store or GeminiUsageStore()

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def provider_name(self) -> str:
        return "Gemini"

    @property
    def provider_version(self) -> str:
        return GEMINI_PROVIDER_VERSION

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(
            structured_outputs=True,
            json_schema=True,
            reasoning_effort=False,
            temperature=True,
            streaming=False,
            thinking_config=True,
            free_tier_guard=True,
        )

    def validate_configuration(self) -> ConfigurationResult:
        if not self._api_key():
            return ConfigurationResult(False, "GEMINI_API_KEY is not configured.", "missing_api_key")
        try:
            self._import_genai()
        except ModuleNotFoundError:
            return ConfigurationResult(False, "google-genai Python SDK is not installed.", "missing_google_genai_sdk")
        return ConfigurationResult(True, "Gemini API configured")

    def estimate_cost(self, request: StoryGenerationRequest) -> StoryCostEstimate:
        metadata = get_gemini_model_metadata(request.model)
        return StoryCostEstimate(
            model=request.model,
            estimated_cost_usd=None,
            method="gemini_free_tier_guard_estimate",
            pricing_snapshot={
                "pricing_mode": "free_tier_expected" if metadata and metadata.free_tier_status == "available" else "unknown",
                "model_free_tier_status": metadata.free_tier_status if metadata else "unknown",
                "checked_at": metadata.metadata_checked_at if metadata else None,
                "source": metadata.source if metadata else None,
                "local_usage_only": True,
            },
            message="Gemini cost is not asserted as $0; Free-tier-only guard and local safety cap are used.",
        )

    def generate_story(
        self,
        request: StoryGenerationRequest,
        cancellation_token: CancellationToken | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> StoryGenerationResult:
        request.validate()
        config = self.validate_configuration()
        if not config.configured:
            return self._failed(request, config.error_code, config.message)
        try:
            model = validate_gemini_model_id(request.model or default_gemini_model(), allow_custom=not self._free_tier_only(request))
        except ValueError as exc:
            return self._failed(request, "gemini_invalid_model", str(exc))
        guard = self._free_tier_decision(request, model)
        if not guard.allowed:
            return self._failed(request, guard.error_code, guard.message)

        retry_count = 0
        max_retries = int(request.retry_count)
        while True:
            if cancellation_token and cancellation_token.cancel_requested:
                return StoryGenerationResult(status="cancelled", provider=self.provider_id, provider_version=self.provider_version, model=model)
            try:
                if progress_callback:
                    progress_callback("Requesting Gemini Story generation", 20)
                self.usage_store.record_attempt()
                response = self._call_gemini(request, model)
                if cancellation_token and cancellation_token.cancel_requested:
                    return StoryGenerationResult(status="cancelled", provider=self.provider_id, provider_version=self.provider_version, model=model)
                story = self._story_from_response(response, request)
                metrics = self._metrics_from_response(response)
                self.usage_store.record_result(True, metrics)
                if progress_callback:
                    progress_callback("Gemini Story structured output received", 80)
                return StoryGenerationResult(
                    story=story,
                    provider=self.provider_id,
                    provider_version=self.provider_version,
                    model=model,
                    metrics=metrics,
                    retry_count=retry_count,
                )
            except GeminiProviderError as exc:
                quota = exc.error_code == "gemini_quota_exhausted"
                self.usage_store.record_result(False, quota_exhausted=quota)
                if cancellation_token and cancellation_token.cancel_requested:
                    return StoryGenerationResult(status="cancelled", provider=self.provider_id, provider_version=self.provider_version, model=model)
                if not exc.retryable or retry_count >= max_retries:
                    return self._failed(request, exc.error_code, str(exc), retry_count=retry_count, model=model)
                retry_count += 1
                if self.logger:
                    self.logger.info("story provider retry provider=gemini model=%s retry=%s error_code=%s", model, retry_count, exc.error_code)
                delay = exc.retry_after if exc.retry_after is not None else min(8.0, 2 ** retry_count) + random.uniform(0, 0.25)
                self.sleep_func(delay)

    def _call_gemini(self, request: StoryGenerationRequest, model: str):
        client = self._client()
        schema = story_structured_output_schema(max_scenes=request.max_scenes)
        config: dict[str, Any] = {
            "response_mime_type": "application/json",
            "response_json_schema": schema,
            "max_output_tokens": int(request.max_output_tokens),
        }
        metadata = get_gemini_model_metadata(model)
        temperature = request.provider_options.get("temperature")
        if metadata is not None and metadata.supports_temperature and temperature is not None:
            config["temperature"] = float(temperature)
        try:
            return client.models.generate_content(
                model=model,
                contents=self._story_instructions(request),
                config=config,
            )
        except Exception as exc:
            raise self._classify_exception(exc) from exc

    def _story_from_response(self, response: Any, request: StoryGenerationRequest) -> Story:
        self._check_response(response)
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            data = parsed if isinstance(parsed, dict) else self._object_to_dict(parsed)
        else:
            text = str(getattr(response, "text", "") or "").strip()
            if not text:
                raise GeminiProviderError("Gemini returned an empty response.", "gemini_empty_response", False)
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise GeminiProviderError("Gemini structured output was not valid JSON.", "gemini_structured_output_invalid", False) from exc
        if not isinstance(data, dict):
            raise GeminiProviderError("Gemini structured output was not a Story object.", "gemini_structured_output_invalid", False)
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

    def _check_response(self, response: Any) -> None:
        candidates = getattr(response, "candidates", None)
        if candidates == []:
            raise GeminiProviderError("Gemini returned no candidates.", "gemini_empty_response", False)
        prompt_feedback = getattr(response, "prompt_feedback", None)
        block_reason = str(getattr(prompt_feedback, "block_reason", "") or "")
        if block_reason:
            raise GeminiProviderError("Gemini blocked the prompt for safety.", "gemini_prompt_blocked", False)
        for candidate in candidates or []:
            finish_reason = str(getattr(candidate, "finish_reason", "") or "")
            if finish_reason in {"SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII"}:
                raise GeminiProviderError("Gemini response was blocked for safety.", "gemini_safety_block", False)
            if finish_reason in {"MAX_TOKENS"}:
                raise GeminiProviderError("Gemini output reached the max output limit.", "gemini_max_output", False)
            if finish_reason and finish_reason not in {"STOP", "FINISH_REASON_UNSPECIFIED"}:
                raise GeminiProviderError(f"Gemini finished with unsupported reason: {finish_reason}", "gemini_incomplete_response", False)

    def _metrics_from_response(self, response: Any) -> StoryProviderMetrics:
        usage = getattr(response, "usage_metadata", None)
        input_tokens = self._int_attr(usage, "prompt_token_count")
        output_tokens = self._int_attr(usage, "candidates_token_count")
        thoughts_tokens = self._int_attr(usage, "thoughts_token_count")
        cached_tokens = self._int_attr(usage, "cached_content_token_count")
        total_tokens = self._int_attr(usage, "total_token_count")
        finish_reason = None
        candidates = getattr(response, "candidates", None) or []
        if candidates:
            finish_reason = str(getattr(candidates[0], "finish_reason", "") or "") or None
        return StoryProviderMetrics(
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            thoughts_tokens=thoughts_tokens,
            cached_tokens=cached_tokens,
            total_tokens=total_tokens,
            finish_reason=finish_reason,
            response_id=str(getattr(response, "response_id", "") or "") or None,
            model_version=str(getattr(response, "model_version", "") or "") or None,
            pricing_mode="free_tier_expected",
            estimated_cost_usd=None,
            charge_expected=False,
            billing_status="user_confirmed_disabled",
            pricing_snapshot={"provider": "gemini", "estimate_is_not_actual_billing": True},
        )

    def _classify_exception(self, exc: Exception) -> GeminiProviderError:
        code = getattr(exc, "code", None) or getattr(exc, "status_code", None)
        message = self._sanitize_error(str(getattr(exc, "message", "") or str(exc)))
        lower = message.lower()
        retry_after = self._retry_after(exc)
        if "api key" in lower or "apikey" in lower or code in {401, 403}:
            return GeminiProviderError("Gemini API key or permission error.", "gemini_invalid_api_key", False)
        if "billing" in lower:
            return GeminiProviderError("Gemini billing is required for this request.", "gemini_billing_required", False)
        if "quota" in lower or "free" in lower and "exhaust" in lower:
            return GeminiProviderError("Gemini quota appears exhausted.", "gemini_quota_exhausted", False)
        if "model" in lower and ("not found" in lower or "unavailable" in lower):
            return GeminiProviderError("Gemini model is unavailable.", "gemini_model_unavailable", False)
        if code == 429:
            if "quota" in lower or "resource_exhausted" in lower and "retry" not in lower:
                return GeminiProviderError("Gemini quota appears exhausted.", "gemini_quota_exhausted", False)
            return GeminiProviderError("Gemini short-term rate limit.", "gemini_rate_limited", True, retry_after)
        if code in {408, 500, 502, 503, 504}:
            return GeminiProviderError(message or "Temporary Gemini service error.", f"gemini_http_{code}", True, retry_after)
        if "timeout" in lower:
            return GeminiProviderError("Gemini request timed out.", "gemini_timeout", True)
        if code == 400:
            return GeminiProviderError(message or "Invalid Gemini request.", "gemini_invalid_request", False)
        return GeminiProviderError(message or "Gemini request failed.", "gemini_provider_error", False)

    def _free_tier_decision(self, request: StoryGenerationRequest, model: str):
        options = request.provider_options or {}
        local_cap = int(options.get("local_daily_request_cap", DEFAULT_LOCAL_DAILY_CAP) or DEFAULT_LOCAL_DAILY_CAP)
        return self.policy.evaluate(
            metadata=get_gemini_model_metadata(model),
            api_key=self._api_key(),
            free_tier_only=self._free_tier_only(request),
            project_free_confirmed=bool(options.get("project_free_tier_confirmed", False)),
            billing_disabled_confirmed=bool(options.get("billing_disabled_confirmed", False)),
            confirmation_key_fingerprint=str(options.get("confirmation_key_fingerprint") or ""),
            local_cap_reached=self.usage_store.cap_reached(local_cap),
            quota_exhausted=bool(self.usage_store.load().get("quota_exhausted", False)),
        )

    def _story_instructions(self, request: StoryGenerationRequest) -> str:
        return (
            "Create a Japanese vertical short-video documentary Story that matches the provided JSON schema. "
            "Return JSON only. Do not include Markdown or explanations. "
            "Use a strong opening hook, avoid excessive clickbait, and distinguish facts from speculation. "
            "Narration, subtitle, and image_prompt must not be empty. "
            "Each scene must have distinct visual content. scene_index starts at 1 and is sequential. "
            "start_time, end_time, and duration must be consistent. "
            f"Theme: {request.theme}\n"
            f"Language: {request.language}\n"
            f"Target duration seconds: {request.target_duration_seconds:.1f}\n"
            f"Scene count range: {request.min_scenes}-{request.max_scenes}"
        )

    def _client(self):
        if self.client_factory:
            return self.client_factory()
        genai_mod, types_mod = self._import_genai()
        return genai_mod.Client(api_key=self._api_key())

    def _import_genai(self):
        from google import genai
        from google.genai import types

        return genai, types

    def _api_key(self) -> str:
        load_dotenv()
        return os.environ.get("GEMINI_API_KEY", "").strip()

    def _free_tier_only(self, request: StoryGenerationRequest) -> bool:
        return bool((request.provider_options or {}).get("free_tier_only", True))

    def _failed(self, request: StoryGenerationRequest, code: str, message: str, retry_count: int = 0, model: str | None = None) -> StoryGenerationResult:
        return StoryGenerationResult(
            status="failed",
            provider=self.provider_id,
            provider_version=self.provider_version,
            model=model or request.model,
            error_code=code,
            error_message=self._sanitize_error(message),
            retry_count=retry_count,
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

    def _retry_after(self, exc: Exception) -> float | None:
        headers = getattr(getattr(exc, "response", None), "headers", {}) or {}
        value = headers.get("retry-after") if hasattr(headers, "get") else None
        try:
            return float(value) if value else None
        except Exception:
            return None

    def _sanitize_error(self, message: str) -> str:
        api_key = self._api_key()
        sanitized = str(message).replace(api_key, "[REDACTED]") if api_key else str(message)
        return sanitized.replace("\n", " ")[:600]

    def current_key_fingerprint(self) -> str:
        return api_key_fingerprint(self._api_key())
