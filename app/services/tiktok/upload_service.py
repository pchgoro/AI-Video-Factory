from __future__ import annotations

import logging
import random
import time
from datetime import datetime
from pathlib import Path
from typing import Callable

from PySide6.QtCore import QObject, Signal

from models import ProjectInfo
from services.project_service import ProjectService
from services.tiktok.api_client import TikTokApiClient
from services.tiktok.models import (
    TikTokDuplicateUploadError,
    TikTokUploadCancelled,
    TikTokUploadError,
    TikTokUploadResult,
)
from services.tiktok.oauth_service import TikTokOAuthService
from services.tiktok.status_service import TikTokStatusService
from services.tiktok.video_validator import TikTokVideoValidator


TIKTOK_UPLOAD_INIT_URL = "https://open.tiktokapis.com/v2/post/publish/inbox/video/init/"

ProgressCallback = Callable[[dict[str, object]], None]
CancelCallback = Callable[[], bool]


class TikTokConnectWorker(QObject):
    """Run TikTok OAuth outside the UI thread."""

    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, oauth_service: TikTokOAuthService) -> None:
        super().__init__()
        self.oauth_service = oauth_service

    def run(self) -> None:
        try:
            token = self.oauth_service.start_oauth_flow()
            self.finished.emit({"open_id": token.open_id, "scope": token.scope})
        except Exception as exc:
            self.failed.emit(str(exc))


class TikTokUploadWorker(QObject):
    """Run TikTok upload service calls outside the UI thread."""

    progress = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        service: "TikTokUploadService",
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
                    "publish_id": result.publish_id,
                    "uploaded_at": result.uploaded_at,
                    "remote_status": result.remote_status,
                    "retry_count": result.retry_count,
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class TikTokStatusWorker(QObject):
    """Run TikTok status checks outside the UI thread."""

    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, service: "TikTokUploadService", project: ProjectInfo) -> None:
        super().__init__()
        self.service = service
        self.project = project

    def run(self) -> None:
        try:
            result = self.service.check_status(self.project)
            self.finished.emit(
                {
                    "publish_id": result.publish_id,
                    "remote_status": result.remote_status,
                    "local_status": result.local_status,
                    "uploaded_bytes": result.uploaded_bytes,
                    "fail_reason": result.fail_reason,
                }
            )
        except Exception as exc:
            self.failed.emit(str(exc))


class TikTokUploadService:
    ACTIVE_STATUSES = {"authenticating", "initializing", "uploading", "processing", "action_required"}

    def __init__(
        self,
        project_service: ProjectService,
        oauth_service: TikTokOAuthService,
        status_service: TikTokStatusService | None = None,
        api_client: TikTokApiClient | None = None,
        video_validator: TikTokVideoValidator | None = None,
        logger: logging.Logger | None = None,
        max_retries: int = 3,
        backoff_base_seconds: float = 1.0,
        sleeper: Callable[[float], None] = time.sleep,
    ) -> None:
        self.project_service = project_service
        self.oauth_service = oauth_service
        self.api_client = api_client or TikTokApiClient()
        self.status_service = status_service or TikTokStatusService(project_service, oauth_service, self.api_client, logger)
        self.video_validator = video_validator or TikTokVideoValidator()
        self.logger = logger or logging.getLogger("ai_video_factory.tiktok")
        self.max_retries = max_retries
        self.backoff_base_seconds = backoff_base_seconds
        self.sleeper = sleeper

    def upload_project(
        self,
        project: ProjectInfo,
        retry: bool = False,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
    ) -> TikTokUploadResult:
        project = self.project_service.load_project(project.path)
        self._prevent_duplicate(project, retry=retry)
        final_mp4 = self.video_validator.validate_final_mp4(project)
        file_size = final_mp4.stat().st_size
        self._set_upload_state(project, {"status": "authenticating", "last_error": "", "error_code": "", "updated_at": self._now()})
        self._emit(progress_callback, "authenticating", "TikTok認証を確認しています。", 0, False, 0)
        access_token = self.oauth_service.get_access_token()
        if should_cancel and should_cancel():
            raise TikTokUploadCancelled("TikTokアップロードを中断しました。", retryable=True)

        self._set_upload_state(project, {"status": "initializing", "updated_at": self._now()})
        self._emit(progress_callback, "initializing", "TikTokアップロードを初期化しています。", 0, False, 0)
        self.logger.info("upload init project_id=%s file=%s size=%s", project.name, final_mp4.name, file_size)
        try:
            publish_id, upload_url, chunk_size, total_chunks = self._initialize_upload_with_retries(
                project,
                access_token,
                file_size,
                progress_callback,
                should_cancel,
            )
            self._set_upload_state(
                project,
                {
                    "status": "uploading",
                    "publish_id": publish_id,
                    "remote_status": "",
                    "updated_at": self._now(),
                },
            )
            retry_count = self._transfer_with_retries(
                project,
                access_token,
                final_mp4,
                upload_url,
                chunk_size,
                total_chunks,
                progress_callback,
                should_cancel,
            )
            uploaded_at = self._now()
            self._set_upload_state(
                project,
                {
                    "status": "processing",
                    "remote_status": "PROCESSING_UPLOAD",
                    "publish_id": publish_id,
                    "uploaded_at": uploaded_at,
                    "retry_count": retry_count,
                    "last_error": "",
                    "error_code": "",
                    "updated_at": self._now(),
                },
            )
            self._emit(progress_callback, "processing", "TikTokへ動画を転送しました。状態確認中です。", 100, False, retry_count)
            try:
                self.status_service.check_project(self.project_service.load_project(project.path))
            except TikTokUploadError as exc:
                if not exc.retryable:
                    raise
                self.logger.info("status check deferred project_id=%s error_code=%s", project.name, exc.error_code)
            self.logger.info("upload transfer success project_id=%s publish_id=%s retries=%s", project.name, publish_id, retry_count)
            return TikTokUploadResult(publish_id=publish_id, uploaded_at=uploaded_at, remote_status="PROCESSING_UPLOAD", retry_count=retry_count)
        except TikTokUploadError as exc:
            self._record_failure(project, exc)
            raise
        except Exception as exc:
            wrapped = TikTokUploadError("TikTokアップロードに失敗しました。", retryable=False)
            self._record_failure(project, wrapped)
            raise wrapped from exc

    def check_status(self, project: ProjectInfo):
        return self.status_service.check_project(project)

    def _initialize_upload_with_retries(
        self,
        project: ProjectInfo,
        access_token: str,
        file_size: int,
        progress_callback: ProgressCallback | None,
        should_cancel: CancelCallback | None,
    ) -> tuple[str, str, int, int]:
        chunk_size = self._chunk_size(file_size)
        total_chunks = self._total_chunks(file_size, chunk_size)
        payload = {
            "source_info": {
                "source": "FILE_UPLOAD",
                "video_size": file_size,
                "chunk_size": chunk_size,
                "total_chunk_count": total_chunks,
            }
        }
        retry_count = 0
        while True:
            if should_cancel and should_cancel():
                raise TikTokUploadCancelled("TikTokアップロードを中断しました。", retryable=True)
            try:
                response = self.api_client.post_json(TIKTOK_UPLOAD_INIT_URL, access_token, payload)
                data = response.data.get("data") if isinstance(response.data, dict) else {}
                if not isinstance(data, dict):
                    raise TikTokUploadError("TikTokアップロード初期化APIの応答形式が正しくありません。")
                publish_id = str(data.get("publish_id") or "")
                upload_url = str(data.get("upload_url") or "")
                if not publish_id or not upload_url:
                    raise TikTokUploadError("TikTokアップロード初期化APIの応答にpublish IDがありません。")
                return publish_id, upload_url, chunk_size, total_chunks
            except TikTokUploadError as exc:
                retry_count += 1
                if not exc.retryable or retry_count > self.max_retries:
                    raise
                delay = self._backoff_delay(retry_count)
                self._set_upload_state(
                    project,
                    {
                        "status": "initializing",
                        "retry_count": retry_count,
                        "last_error": "TikTok APIの一時エラーです。再試行中です。",
                        "error_code": exc.error_code,
                        "updated_at": self._now(),
                    },
                )
                self._emit(progress_callback, "initializing", "TikTok初期化を再試行しています。", None, True, retry_count)
                self.logger.info("retry init project_id=%s retry_count=%s error_code=%s delay=%.2f", project.name, retry_count, exc.error_code, delay)
                self.sleeper(delay)

    def _transfer_with_retries(
        self,
        project: ProjectInfo,
        access_token: str,
        final_mp4: Path,
        upload_url: str,
        chunk_size: int,
        total_chunks: int,
        progress_callback: ProgressCallback | None,
        should_cancel: CancelCallback | None,
    ) -> int:
        retry_count = 0
        file_size = final_mp4.stat().st_size
        with final_mp4.open("rb") as stream:
            for index in range(total_chunks):
                if should_cancel and should_cancel():
                    raise TikTokUploadCancelled("TikTokアップロードを中断しました。", retryable=True)
                start = index * chunk_size
                end = min(start + chunk_size, file_size) - 1
                length = end - start + 1
                stream.seek(start)
                data = stream.read(length)
                content_range = f"bytes {start}-{end}/{file_size}"
                while True:
                    try:
                        self.api_client.put_bytes(upload_url, access_token, data, content_range)
                        percent = int(((index + 1) / total_chunks) * 100)
                        self._emit(progress_callback, "uploading", "TikTokへ動画を転送しています。", percent, False, retry_count)
                        self.logger.info("upload progress project_id=%s progress=%s%%", project.name, percent)
                        break
                    except TikTokUploadError as exc:
                        retry_count += 1
                        if not exc.retryable or retry_count > self.max_retries:
                            raise
                        delay = self._backoff_delay(retry_count)
                        self._set_upload_state(
                            project,
                            {
                                "status": "uploading",
                                "retry_count": retry_count,
                                "last_error": "TikTok転送の一時エラーです。再試行中です。",
                                "error_code": exc.error_code,
                                "updated_at": self._now(),
                            },
                        )
                        self._emit(progress_callback, "uploading", "TikTok転送を再試行しています。", None, True, retry_count)
                        self.logger.info("retry transfer project_id=%s retry_count=%s error_code=%s delay=%.2f", project.name, retry_count, exc.error_code, delay)
                        self.sleeper(delay)
        return retry_count

    def _prevent_duplicate(self, project: ProjectInfo, retry: bool) -> None:
        state = dict(project.tiktok_upload or {})
        status = str(state.get("status") or "pending")
        publish_id = str(state.get("publish_id") or "")
        if status == "uploaded" or (publish_id and status in self.ACTIVE_STATUSES):
            raise TikTokDuplicateUploadError("既存のTikTok upload状態があるため、新しいアップロードは開始しません。")
        if retry and publish_id:
            raise TikTokDuplicateUploadError("既存のpublish IDがあるため、Retry Uploadでは新しいアップロードを開始しません。Check Statusを使ってください。")

    def _set_upload_state(self, project: ProjectInfo, updates: dict[str, object]) -> None:
        metadata = dict(project.tiktok_upload or {})
        metadata.update(updates)
        metadata.setdefault("status", "pending")
        self.project_service.update_metadata(project.path, {"tiktok_upload": metadata})

    def _record_failure(self, project: ProjectInfo, exc: TikTokUploadError) -> None:
        message = str(exc) or "TikTokアップロードに失敗しました。"
        state = {
            "status": "failed",
            "last_error": message,
            "error_code": exc.error_code,
            "updated_at": self._now(),
        }
        self._set_upload_state(project, state)
        self.logger.warning("upload failure project_id=%s retryable=%s error_code=%s", project.name, exc.retryable, exc.error_code)

    def _chunk_size(self, file_size: int) -> int:
        max_chunk = 64 * 1024 * 1024
        min_chunk = 5 * 1024 * 1024
        if file_size <= max_chunk:
            return file_size
        return max(min_chunk, max_chunk)

    def _total_chunks(self, file_size: int, chunk_size: int) -> int:
        return max(1, (file_size + chunk_size - 1) // chunk_size)

    def _backoff_delay(self, retry_count: int) -> float:
        return self.backoff_base_seconds * (2 ** (retry_count - 1)) + random.uniform(0, 0.2)

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

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
