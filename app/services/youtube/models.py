from __future__ import annotations

from dataclasses import dataclass


class YouTubeUploadError(Exception):
    def __init__(self, message: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.retryable = retryable


class YouTubeDuplicateUploadError(YouTubeUploadError):
    pass


class YouTubeAuthError(YouTubeUploadError):
    pass


class YouTubeTokenStorageError(YouTubeAuthError):
    pass


class YouTubeValidationError(YouTubeUploadError):
    pass


class YouTubeUploadCancelled(YouTubeUploadError):
    pass


@dataclass(frozen=True)
class YouTubeUploadResult:
    video_id: str
    url: str
    upload_timestamp: str
    retry_count: int = 0
