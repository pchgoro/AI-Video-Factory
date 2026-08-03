from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Callable

from services.tiktok.models import TikTokUploadError


@dataclass(frozen=True)
class TikTokApiResponse:
    data: dict[str, object]
    headers: dict[str, str]


class TikTokApiClient:
    def __init__(self, opener: Callable[[urllib.request.Request, int], object] | None = None) -> None:
        self.opener = opener or urllib.request.urlopen

    def post_json(self, url: str, access_token: str, payload: dict[str, object], timeout: int = 60) -> TikTokApiResponse:
        body = json.dumps(payload).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json; charset=UTF-8",
            },
        )
        return self._request_json(request, timeout)

    def put_bytes(
        self,
        url: str,
        access_token: str,
        data: bytes,
        content_range: str,
        timeout: int = 120,
    ) -> TikTokApiResponse:
        request = urllib.request.Request(
            url,
            data=data,
            method="PUT",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "video/mp4",
                "Content-Length": str(len(data)),
                "Content-Range": content_range,
            },
        )
        return self._request_json(request, timeout)

    def _request_json(self, request: urllib.request.Request, timeout: int) -> TikTokApiResponse:
        try:
            with self.opener(request, timeout=timeout) as response:
                raw = response.read().decode("utf-8")
                data = json.loads(raw) if raw else {}
                headers = {key: value for key, value in response.headers.items()}
        except urllib.error.HTTPError as exc:
            data = self._read_error_json(exc)
            raise self._api_error(exc.code, data) from exc
        except TimeoutError as exc:
            raise TikTokUploadError("TikTok APIへの接続がタイムアウトしました。", retryable=True) from exc
        except OSError as exc:
            raise TikTokUploadError("TikTok APIへの接続に失敗しました。", retryable=True) from exc
        except json.JSONDecodeError as exc:
            raise TikTokUploadError("TikTok APIの応答形式が正しくありません。", retryable=False, error_code="malformed_response") from exc

        error = data.get("error") if isinstance(data, dict) else None
        if isinstance(error, dict) and str(error.get("code") or "ok") != "ok":
            raise self._api_error(None, data)
        return TikTokApiResponse(data=data if isinstance(data, dict) else {}, headers=headers)

    def _read_error_json(self, exc: urllib.error.HTTPError) -> dict[str, object]:
        try:
            raw = exc.read().decode("utf-8")
            data = json.loads(raw) if raw else {}
            return data if isinstance(data, dict) else {}
        except Exception:
            return {}

    def _api_error(self, http_status: int | None, data: dict[str, object]) -> TikTokUploadError:
        error = data.get("error") if isinstance(data, dict) else {}
        error_code = str(error.get("code") or http_status or "api_error") if isinstance(error, dict) else str(http_status or "api_error")
        if http_status in {429, 500, 502, 503, 504}:
            return TikTokUploadError("TikTok APIで一時的なエラーが発生しました。", retryable=True, error_code=error_code)
        if error_code in {"rate_limit_exceeded", "server_error", "temporarily_unavailable"}:
            return TikTokUploadError("TikTok APIで一時的なエラーが発生しました。", retryable=True, error_code=error_code)
        if http_status in {401, 403} or error_code in {"access_token_invalid", "scope_not_authorized", "permission_denied"}:
            return TikTokUploadError("TikTok認証または権限が不足しています。", retryable=False, error_code=error_code)
        if error_code in {"invalid_param", "spam_risk_too_many_pending_share"}:
            return TikTokUploadError("TikTokアップロード条件を満たしていません。", retryable=False, error_code=error_code)
        return TikTokUploadError("TikTok APIでエラーが発生しました。", retryable=False, error_code=error_code)
