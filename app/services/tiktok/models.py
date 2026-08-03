from __future__ import annotations

from dataclasses import dataclass


class TikTokUploadError(Exception):
    def __init__(self, message: str, retryable: bool = False, error_code: str = "") -> None:
        super().__init__(message)
        self.retryable = retryable
        self.error_code = error_code


class TikTokDuplicateUploadError(TikTokUploadError):
    pass


class TikTokAuthError(TikTokUploadError):
    pass


class TikTokTokenStorageError(TikTokAuthError):
    pass


class TikTokValidationError(TikTokUploadError):
    pass


class TikTokUploadCancelled(TikTokUploadError):
    pass


@dataclass(frozen=True)
class TikTokTokenData:
    access_token: str = ""
    refresh_token: str = ""
    expires_at: int = 0
    refresh_expires_at: int = 0
    open_id: str = ""
    scope: str = ""
    token_type: str = "Bearer"


@dataclass(frozen=True)
class TikTokUploadResult:
    publish_id: str
    uploaded_at: str
    remote_status: str = ""
    retry_count: int = 0


@dataclass(frozen=True)
class TikTokStatusResult:
    publish_id: str
    remote_status: str
    local_status: str
    uploaded_bytes: int = 0
    fail_reason: str = ""
