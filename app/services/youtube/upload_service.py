from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal

from models import AppSettings, ProjectInfo
from services.job_service import JobService
from services.project_service import ProjectService
from services.youtube.models import (
    YouTubeAuthError,
    YouTubeDuplicateUploadError,
    YouTubeUploadCancelled,
    YouTubeUploadError,
    YouTubeUploadResult,
    YouTubeValidationError,
)
from services.youtube.oauth_service import YouTubeOAuthService


ProgressCallback = Callable[[dict[str, object]], None]
CancelCallback = Callable[[], bool]
VOICEVOX_CREDIT_LINE = "音声はVOICEVOXを使用させていただいております。"
DEFAULT_YOUTUBE_CATEGORY_ID = "28"
VALID_PLAYLIST_PRIVACY_STATUSES = {"private", "unlisted", "public"}


class YouTubeUploadWorker(QObject):
    """Run YouTube upload service calls outside the UI thread."""

    progress = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        service: "YouTubeUploadService",
        project: ProjectInfo,
        retry: bool = False,
    ) -> None:
        super().__init__()
        self.service = service
        self.project = project
        self.retry = retry
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def _should_cancel(self) -> bool:
        return self._cancel_requested

    def run(self) -> None:
        try:
            result = self.service.upload_project(
                self.project,
                retry=self.retry,
                progress_callback=self.progress.emit,
                should_cancel=self._should_cancel,
            )
            self.finished.emit(
                {
                    "video_id": result.video_id,
                    "url": result.url,
                    "upload_timestamp": result.upload_timestamp,
                    "retry_count": result.retry_count,
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class YouTubeUploadService:
    RETRYABLE_HTTP_STATUSES = {500, 502, 503, 504}

    def __init__(
        self,
        project_service: ProjectService,
        job_service: JobService,
        oauth_service: YouTubeOAuthService,
        logger: logging.Logger | None = None,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
        sleeper: Callable[[float], None] = time.sleep,
        media_upload_factory: Callable[..., object] | None = None,
        settings: AppSettings | None = None,
    ) -> None:
        self.project_service = project_service
        self.job_service = job_service
        self.oauth_service = oauth_service
        self.logger = logger or logging.getLogger("ai_video_factory.youtube")
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.sleeper = sleeper
        self.media_upload_factory = media_upload_factory
        self.settings = settings or AppSettings()

    def upload_project(
        self,
        project: ProjectInfo,
        retry: bool = False,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
    ) -> YouTubeUploadResult:
        project = self.project_service.load_project(project.path)
        upload_state = dict(project.youtube_upload or {})
        if upload_state.get("video_id"):
            raise YouTubeDuplicateUploadError("このプロジェクトは既にYouTube動画IDが保存されているため、再アップロードしません。")
        if retry and upload_state.get("status") == "uploaded":
            raise YouTubeDuplicateUploadError("アップロード成功済みのため、Retry Uploadは実行できません。")

        final_mp4 = self.validate_final_mp4(project)
        self._set_upload_state(project, {"status": "uploading", "last_error": "", "updated_at": self._now()})
        self._emit(progress_callback, "uploading", "upload started", 0, retrying=False, retry_count=0)
        self.logger.info("upload start project_id=%s file=%s", project.name, final_mp4.name)

        try:
            youtube = self.oauth_service.build_youtube_client()
            result = self._upload_with_retries(project, youtube, final_mp4, progress_callback, should_cancel)
        except YouTubeUploadError as exc:
            self._record_failure(project, exc)
            raise
        except Exception as exc:
            wrapped = YouTubeUploadError("YouTubeアップロードに失敗しました。", retryable=False)
            self._record_failure(project, wrapped, detail=str(exc))
            raise wrapped from exc

        playlist_result = self._add_to_category_playlist(project, youtube, result.video_id)
        self._set_upload_state(
            project,
            {
                "status": "uploaded",
                "video_id": result.video_id,
                "url": result.url,
                "upload_timestamp": result.upload_timestamp,
                "retry_count": result.retry_count,
                **playlist_result,
                "last_error": "",
                "updated_at": self._now(),
            },
        )
        self.job_service.set_status(self.project_service.load_project(project.path), "youtube_uploaded")
        self._emit(progress_callback, "uploaded", "upload completed", 100, retrying=False, retry_count=result.retry_count)
        self.logger.info("upload success project_id=%s video_id=%s retries=%s", project.name, result.video_id, result.retry_count)
        return result

    def validate_final_mp4(self, project: ProjectInfo) -> Path:
        final_mp4 = project.path / "video" / "final.mp4"
        try:
            project_root = project.path.resolve()
            resolved = final_mp4.resolve()
        except OSError as exc:
            raise YouTubeValidationError("アップロード対象動画のパスを確認できません。") from exc
        if project_root not in resolved.parents:
            raise YouTubeValidationError("対象プロジェクト外の動画はアップロードできません。")
        if resolved.name != "final.mp4" or resolved.suffix.lower() != ".mp4":
            raise YouTubeValidationError("YouTubeへアップロードできるのはfinal.mp4だけです。")
        if not resolved.exists():
            raise YouTubeValidationError("final.mp4が見つかりません。動画生成後にアップロードしてください。")
        if resolved.stat().st_size <= 0:
            raise YouTubeValidationError("final.mp4のファイルサイズが0です。")
        try:
            header = resolved.read_bytes()[:64]
        except OSError as exc:
            raise YouTubeValidationError("final.mp4を読み取れません。") from exc
        if b"ftyp" not in header:
            raise YouTubeValidationError("final.mp4を動画ファイルとして確認できません。")
        return resolved

    def _upload_with_retries(
        self,
        project: ProjectInfo,
        youtube,
        final_mp4: Path,
        progress_callback: ProgressCallback | None,
        should_cancel: CancelCallback | None,
    ) -> YouTubeUploadResult:
        body = self._video_body(project)
        media = self._media_upload(str(final_mp4), mimetype="video/mp4", chunksize=8 * 1024 * 1024, resumable=True)
        request = youtube.videos().insert(part="snippet,status", body=body, media_body=media)
        response = None
        retry_count = 0
        while response is None:
            if should_cancel and should_cancel():
                raise YouTubeUploadCancelled("YouTubeアップロードを中断しました。", retryable=True)
            try:
                status, response = request.next_chunk()
                if status:
                    percent = int(status.progress() * 100)
                    self._emit(progress_callback, "uploading", "upload progress", percent, retrying=False, retry_count=retry_count)
                    self.logger.info("upload progress project_id=%s progress=%s%%", project.name, percent)
            except Exception as exc:
                if isinstance(exc, YouTubeAuthError):
                    raise
                http_status = self._http_status(exc)
                if not self._is_retryable(exc, http_status):
                    raise YouTubeUploadError(self._error_message_for_status(http_status), retryable=False) from exc
                retry_count += 1
                if retry_count > self.max_retries:
                    raise YouTubeUploadError("一時的な通信エラーが続いたため、YouTubeアップロードを停止しました。", retryable=True) from exc
                delay = self._backoff_delay(retry_count)
                self._set_upload_state(project, {"status": "failed", "retry_count": retry_count, "last_error": "一時的な通信エラー。再試行中です。", "updated_at": self._now()})
                self._emit(progress_callback, "uploading", f"retry {retry_count}", None, retrying=True, retry_count=retry_count)
                self.logger.info("retry project_id=%s retry_count=%s http_status=%s delay=%.2f", project.name, retry_count, http_status, delay)
                self.sleeper(delay)
        video_id = str(response.get("id", "") if isinstance(response, dict) else "")
        if not video_id:
            raise YouTubeUploadError("YouTubeアップロード結果からvideo IDを取得できませんでした。", retryable=False)
        timestamp = self._now()
        return YouTubeUploadResult(
            video_id=video_id,
            url=f"https://www.youtube.com/watch?v={video_id}",
            upload_timestamp=timestamp,
            retry_count=retry_count,
        )

    def _video_body(self, project: ProjectInfo) -> dict[str, object]:
        title = (project.title or project.topic or project.name).strip() or "AI Video Factory Upload"
        description = self._read_text(project.path / "script.txt").strip()
        if self.settings.youtube_voicevox_credit_enabled:
            description = self._append_voicevox_credit(description)
        tags = project.youtube_tags or project.tags
        return {
            "snippet": {
                "title": title[:100],
                "description": description,
                "tags": tags,
                "categoryId": self._youtube_category_id(),
            },
            "status": {
                "privacyStatus": "private",
                "selfDeclaredMadeForKids": False,
                "containsSyntheticMedia": bool(self.settings.youtube_ai_disclosure_enabled),
            },
        }

    def _append_voicevox_credit(self, description: str) -> str:
        if VOICEVOX_CREDIT_LINE in description:
            return description
        if not description:
            return VOICEVOX_CREDIT_LINE
        return f"{description.rstrip()}\n\n{VOICEVOX_CREDIT_LINE}"

    def _youtube_category_id(self) -> str:
        category_id = str(getattr(self.settings, "youtube_category_id", "") or "").strip()
        return category_id if category_id.isdigit() else DEFAULT_YOUTUBE_CATEGORY_ID

    def _add_to_category_playlist(self, project: ProjectInfo, youtube, video_id: str) -> dict[str, object]:
        if not getattr(self.settings, "youtube_add_to_category_playlist", True):
            return {"playlist_status": "disabled"}
        playlist_title = (project.category or "Uncategorized").strip() or "Uncategorized"
        try:
            playlist_id = self._find_playlist_id(youtube, playlist_title)
            created = False
            if not playlist_id:
                if not getattr(self.settings, "youtube_create_playlist_if_missing", True):
                    return {
                        "playlist_status": "skipped",
                        "playlist_title": playlist_title,
                        "playlist_error": "playlist not found",
                    }
                playlist_id = self._create_playlist(youtube, playlist_title)
                created = True
            youtube.playlistItems().insert(
                part="snippet",
                body={
                    "snippet": {
                        "playlistId": playlist_id,
                        "resourceId": {
                            "kind": "youtube#video",
                            "videoId": video_id,
                        },
                    }
                },
            ).execute()
            self.logger.info("playlist add success project_id=%s playlist_title=%s created=%s", project.name, playlist_title, created)
            return {
                "playlist_status": "added",
                "playlist_id": playlist_id,
                "playlist_title": playlist_title,
                "playlist_created": created,
                "playlist_error": "",
            }
        except Exception as exc:
            safe_error = self._safe_error(str(exc))
            self.logger.warning("playlist add failed project_id=%s playlist_title=%s error=%s", project.name, playlist_title, safe_error)
            return {
                "playlist_status": "failed",
                "playlist_title": playlist_title,
                "playlist_error": safe_error,
            }

    def _find_playlist_id(self, youtube, playlist_title: str) -> str:
        page_token = None
        while True:
            kwargs = {"part": "snippet", "mine": True, "maxResults": 50}
            if page_token:
                kwargs["pageToken"] = page_token
            response = youtube.playlists().list(**kwargs).execute()
            items = response.get("items", []) if isinstance(response, dict) else []
            for item in items:
                snippet = item.get("snippet", {}) if isinstance(item, dict) else {}
                if str(snippet.get("title") or "") == playlist_title:
                    return str(item.get("id") or "")
            page_token = response.get("nextPageToken") if isinstance(response, dict) else None
            if not page_token:
                return ""

    def _create_playlist(self, youtube, playlist_title: str) -> str:
        privacy = str(getattr(self.settings, "youtube_playlist_privacy_status", "private") or "private").strip()
        if privacy not in VALID_PLAYLIST_PRIVACY_STATUSES:
            privacy = "private"
        response = youtube.playlists().insert(
            part="snippet,status",
            body={
                "snippet": {"title": playlist_title},
                "status": {"privacyStatus": privacy},
            },
        ).execute()
        playlist_id = str(response.get("id") or "") if isinstance(response, dict) else ""
        if not playlist_id:
            raise YouTubeUploadError("YouTube playlist ID was not returned.", retryable=False)
        return playlist_id

    def _set_upload_state(self, project: ProjectInfo, updates: dict[str, object]) -> None:
        metadata = dict(project.youtube_upload or {})
        metadata.update(updates)
        metadata.setdefault("status", "pending")
        self.project_service.update_metadata(project.path, {"youtube_upload": metadata})

    def _record_failure(self, project: ProjectInfo, exc: Exception, detail: str = "") -> None:
        message = str(exc) or "YouTubeアップロードに失敗しました。"
        self._set_upload_state(
            project,
            {
                "status": "failed",
                "last_error": message,
                "updated_at": self._now(),
            },
        )
        self.logger.warning("upload failure project_id=%s error=%s detail=%s", project.name, self._safe_error(message), self._safe_error(detail))

    def _emit(
        self,
        progress_callback: ProgressCallback | None,
        status: str,
        message: str,
        percent: int | None,
        retrying: bool,
        retry_count: int,
    ) -> None:
        if progress_callback:
            progress_callback(
                {
                    "status": status,
                    "message": message,
                    "percent": percent,
                    "retrying": retrying,
                    "retry_count": retry_count,
                }
            )

    def _http_status(self, exc: Exception) -> int | None:
        resp = getattr(exc, "resp", None)
        status = getattr(resp, "status", None)
        try:
            return int(status) if status is not None else None
        except (TypeError, ValueError):
            return None

    def _is_retryable(self, exc: Exception, http_status: int | None) -> bool:
        if http_status in self.RETRYABLE_HTTP_STATUSES:
            return True
        if http_status in {401, 403, 400, 404}:
            return False
        return isinstance(exc, (TimeoutError, ConnectionError))

    def _error_message_for_status(self, http_status: int | None) -> str:
        if http_status in {401, 403}:
            return "YouTube認証または権限が不足しています。"
        if http_status == 400:
            return "YouTubeアップロード内容が正しくありません。"
        if http_status == 404:
            return "YouTubeアップロードセッションが無効になりました。再度アップロードを開始してください。"
        return "YouTubeアップロードに失敗しました。"

    def _backoff_delay(self, retry_count: int) -> float:
        jitter = random.uniform(0, 0.2)
        return self.backoff_base_seconds * (2 ** (retry_count - 1)) + jitter

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""

    def _media_upload(self, *args, **kwargs):
        if self.media_upload_factory:
            return self.media_upload_factory(*args, **kwargs)
        try:
            from googleapiclient.http import MediaFileUpload
        except Exception as exc:
            raise YouTubeUploadError("google-api-python-clientを読み込めません。") from exc
        return MediaFileUpload(*args, **kwargs)

    def _safe_error(self, text: str) -> str:
        return (text or "").replace("\n", " ")[:500]

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
