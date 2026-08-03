from __future__ import annotations

import base64
import binascii
import json
import logging
import os
import socket
import ssl
from http.client import HTTPSConnection, HTTPResponse
from typing import Any
from urllib.parse import quote

from dotenv import load_dotenv

from .models import (
    GeneratedImage,
    ImageGenerationCancelled,
    ImageGenerationError,
    ImageGenerationSettings,
    ModelInfo,
    ProviderConfigurationError,
    ProviderStatus,
    UsageEstimate,
)
from .provider import ImageGenerationProvider


CLOUDFLARE_API_HOST = "api.cloudflare.com"
FLUX_1_SCHNELL = "@cf/black-forest-labs/flux-1-schnell"


class CloudflareWorkersAIProvider(ImageGenerationProvider):
    """Cloudflare Workers AI REST provider isolated from UI and project persistence."""

    MODEL_INFO = {
        FLUX_1_SCHNELL: ModelInfo(
            provider="cloudflare_workers_ai",
            model=FLUX_1_SCHNELL,
            prompt_max_length=2048,
            allowed_parameters={"prompt", "steps"},
            default_parameters={"steps": 4},
            portrait_note="flux-1-schnellでは厳密な9:16指定は行わず、既存レンダラーのcrop/fitに任せます。",
            license_url="https://bfl.ai/",
        )
    }

    # Cloudflare pricing page, checked 2026-08-01:
    # 4.80 neurons per 512x512 tile + 9.60 neurons per step for flux-1-schnell.
    FLUX_1_SCHNELL_BASE_NEURONS = 4.8
    FLUX_1_SCHNELL_STEP_NEURONS = 9.6

    def __init__(
        self,
        logger: logging.Logger | None = None,
        connect_timeout: float = 10.0,
        read_timeout: float = 60.0,
        load_env: bool = True,
    ) -> None:
        if load_env:
            load_dotenv()
        self.logger = logger or logging.getLogger("ai_video_factory.image_generation")
        self.connect_timeout = connect_timeout
        self.read_timeout = read_timeout

    def validate_configuration(self) -> ProviderStatus:
        account_id = self._account_id()
        token = self._api_token()
        if not account_id and not token:
            return ProviderStatus(False, "Cloudflare Account ID と API token が未設定です。")
        if not account_id:
            return ProviderStatus(False, "Cloudflare Account ID が未設定です。")
        if not token:
            return ProviderStatus(False, "Cloudflare API token が未設定です。")
        return ProviderStatus(True, "Configured")

    def get_model_info(self, model: str) -> ModelInfo:
        if model not in self.MODEL_INFO:
            raise ImageGenerationError("対応していないCloudflare画像生成モデルです。", "unsupported_model", False)
        return self.MODEL_INFO[model]

    def validate_model_settings(self, settings: ImageGenerationSettings) -> None:
        model_info = self.get_model_info(settings.model)
        steps = int(settings.steps)
        if steps < 1 or steps > 8:
            raise ImageGenerationError("steps は 1〜8 の範囲で指定してください。", "invalid_parameter", False)
        unknown = set(settings.__dict__) & {"width", "height", "guidance"} - model_info.allowed_parameters
        if unknown:
            raise ImageGenerationError("このモデルでは未対応の画像生成パラメータがあります。", "invalid_parameter", False)

    def estimate_usage(self, request_count: int, settings: ImageGenerationSettings) -> UsageEstimate:
        self.validate_model_settings(settings)
        if settings.model == FLUX_1_SCHNELL:
            per_image = self.FLUX_1_SCHNELL_BASE_NEURONS + (self.FLUX_1_SCHNELL_STEP_NEURONS * int(settings.steps))
            return UsageEstimate(
                provider=settings.provider,
                model=settings.model,
                request_count=request_count,
                steps=int(settings.steps),
                estimated_neurons=round(per_image * request_count, 2),
                note="Cloudflare公式単価に基づくアプリ内推定です。Dashboardの実値と差が出る可能性があります。",
            )
        return UsageEstimate(
            provider=settings.provider,
            model=settings.model,
            request_count=request_count,
            steps=int(settings.steps),
            estimated_neurons=None,
            note="このモデルのNeuron推定は未対応です。Cloudflare Dashboardで確認してください。",
        )

    def generate_image(self, prompt: str, settings: ImageGenerationSettings, should_cancel=None) -> GeneratedImage:
        status = self.validate_configuration()
        if not status.configured:
            raise ProviderConfigurationError(status.message, "missing_configuration", False)
        self.validate_model_settings(settings)
        if should_cancel and should_cancel():
            raise ImageGenerationCancelled("画像生成をキャンセルしました。", "cancelled", False)

        payload = {"prompt": prompt, "steps": int(settings.steps)}
        raw_body, content_type, request_id = self._post_json(settings.model, payload, int(settings.max_response_bytes), should_cancel)
        if should_cancel and should_cancel():
            raise ImageGenerationCancelled("画像生成をキャンセルしました。", "cancelled", False)
        image_bytes, image_content_type = self._decode_response(raw_body, content_type, int(settings.max_response_bytes))
        return GeneratedImage(image_bytes=image_bytes, content_type=image_content_type, request_id=request_id)

    def classify_error(self, status_code: int, payload: dict[str, Any] | None, message: str = "") -> ImageGenerationError:
        errors = payload.get("errors", []) if isinstance(payload, dict) else []
        code = ""
        detail = message
        if errors and isinstance(errors[0], dict):
            code = str(errors[0].get("code") or "")
            detail = str(errors[0].get("message") or detail)
        safe_detail = self._sanitize_error(detail)

        if self._is_prompt_rejection(code, safe_detail):
            return ImageGenerationError(
                "画像プロンプトがCloudflareの安全性ポリシーで拒否されました。該当する画像プロンプトを手動で編集してからRetryしてください。",
                "prompt_rejection",
                False,
            )
        if code == "3036":
            return ImageGenerationError("Cloudflare Workers AIの無料割当を超過しました。翌UTC日以降に再試行してください。", "allocation_exceeded", False)
        if status_code in {401, 403}:
            return ImageGenerationError("Cloudflare API tokenの権限またはAccount IDを確認してください。", "auth_or_permission_error", False)
        if status_code == 404 or code in {"3042", "5007"}:
            return ImageGenerationError("Cloudflare画像生成モデルが見つかりません。", "unsupported_model", False)
        if status_code == 400:
            return ImageGenerationError(f"Cloudflareへの画像生成リクエスト形式が正しくありません。{safe_detail}", "invalid_parameter", False)
        if status_code == 413:
            return ImageGenerationError("Cloudflareへの画像生成リクエストが大きすぎます。", "request_too_large", False)
        if status_code == 429:
            retryable = code != "3036"
            return ImageGenerationError("Cloudflareのrate limitに達しました。時間を置いて再試行します。", "rate_limited", retryable)
        if status_code in {408, 500, 502, 503, 504}:
            return ImageGenerationError("Cloudflare Workers AIが一時的に利用できません。", "transient_cloudflare_error", True)
        return ImageGenerationError(f"Cloudflare画像生成に失敗しました。{safe_detail}", "cloudflare_error", False)

    def _post_json(self, model: str, payload: dict[str, object], max_response_bytes: int, should_cancel=None) -> tuple[bytes, str, str]:
        account_id = self._account_id()
        token = self._api_token()
        if not account_id or not token:
            raise ProviderConfigurationError("Cloudflare認証情報が未設定です。", "missing_configuration", False)
        self._validate_account_id(account_id)
        encoded_model = quote(model, safe="@/")
        path = f"/client/v4/accounts/{account_id}/ai/run/{encoded_model}"
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json, image/*",
        }
        context = ssl.create_default_context()
        connection = HTTPSConnection(CLOUDFLARE_API_HOST, timeout=self.connect_timeout, context=context)
        try:
            if should_cancel and should_cancel():
                raise ImageGenerationCancelled("画像生成をキャンセルしました。", "cancelled", False)
            connection.request("POST", path, body=body, headers=headers)
            connection.sock.settimeout(self.read_timeout) if connection.sock else None
            response = connection.getresponse()
            return self._read_response(response, max_response_bytes)
        except ImageGenerationError:
            raise
        except (TimeoutError, socket.timeout, OSError) as exc:
            raise ImageGenerationError("Cloudflareへの接続で一時的な通信エラーが発生しました。", "network_error", True) from exc
        finally:
            connection.close()

    def _read_response(self, response: HTTPResponse, max_response_bytes: int) -> tuple[bytes, str, str]:
        content_type = response.getheader("Content-Type", "")
        request_id = response.getheader("cf-ray", "") or response.getheader("x-request-id", "")
        retry_after = response.getheader("Retry-After", "")
        body = self._read_limited(response, max_response_bytes)
        if 200 <= response.status < 300:
            return body, content_type, self._sanitize_request_id(request_id)
        payload = self._try_json(body)
        error = self.classify_error(response.status, payload, response.reason)
        if retry_after and error.retryable:
            try:
                setattr(error, "retry_after", max(0.0, float(retry_after)))
            except ValueError:
                pass
        raise error

    def _read_limited(self, response: HTTPResponse, max_response_bytes: int) -> bytes:
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_response_bytes:
                raise ImageGenerationError("Cloudflareの応答サイズが上限を超えました。", "response_too_large", False)
            chunks.append(chunk)
        return b"".join(chunks)

    def _decode_response(self, body: bytes, content_type: str, max_response_bytes: int) -> tuple[bytes, str]:
        lower_type = (content_type or "").lower()
        if lower_type.startswith("image/"):
            if not body:
                raise ImageGenerationError("Cloudflareの画像応答が空です。", "empty_response", False)
            return body, lower_type.split(";")[0]
        if "json" not in lower_type:
            raise ImageGenerationError("Cloudflareの応答形式が画像でもJSONでもありません。", "invalid_content_type", False)
        payload = self._try_json(body)
        if not isinstance(payload, dict):
            raise ImageGenerationError("CloudflareのJSON応答を解析できませんでした。", "malformed_response", False)
        if payload.get("success") is False:
            raise self.classify_error(400, payload, "Cloudflare returned success=false")
        result = payload.get("result", payload)
        if not isinstance(result, dict):
            raise ImageGenerationError("Cloudflareの画像応答形式が正しくありません。", "malformed_response", False)
        image_b64 = result.get("image")
        if not isinstance(image_b64, str) or not image_b64.strip():
            raise ImageGenerationError("CloudflareのBase64画像応答が空です。", "empty_response", False)
        if len(image_b64.encode("utf-8")) > max_response_bytes * 2:
            raise ImageGenerationError("CloudflareのBase64画像応答が上限を超えました。", "response_too_large", False)
        try:
            image_bytes = base64.b64decode(image_b64, validate=True)
        except (ValueError, binascii.Error) as exc:  # type: ignore[name-defined]
            raise ImageGenerationError("CloudflareのBase64画像を復号できませんでした。", "malformed_response", False) from exc
        if not image_bytes:
            raise ImageGenerationError("Cloudflareの画像データが空です。", "empty_response", False)
        if len(image_bytes) > max_response_bytes:
            raise ImageGenerationError("Cloudflareの画像データが上限を超えました。", "response_too_large", False)
        return image_bytes, "image/jpeg"

    def _try_json(self, body: bytes) -> dict[str, Any] | None:
        try:
            data = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return None
        return data if isinstance(data, dict) else None

    def _account_id(self) -> str:
        return os.getenv("CLOUDFLARE_ACCOUNT_ID", "").strip()

    def _api_token(self) -> str:
        return os.getenv("CLOUDFLARE_API_TOKEN", "").strip()

    def _validate_account_id(self, account_id: str) -> None:
        if not account_id or not all(char.isalnum() or char in {"_", "-"} for char in account_id):
            raise ProviderConfigurationError("Cloudflare Account ID の形式が正しくありません。", "invalid_account_id", False)

    def _sanitize_error(self, message: str) -> str:
        value = message.replace(self._api_token(), "[redacted]") if self._api_token() else message
        return value[:300]

    def _sanitize_request_id(self, request_id: str) -> str:
        return "".join(char for char in request_id if char.isalnum() or char in {"-", "_"})[:80]

    def _is_prompt_rejection(self, code: str, message: str) -> bool:
        text = f"{code} {message}".lower()
        rejection_markers = [
            "nsfw",
            "safety",
            "policy",
            "prompt",
            "content",
            "moderation",
            "not allowed",
            "rejected",
        ]
        return any(marker in text for marker in rejection_markers)
