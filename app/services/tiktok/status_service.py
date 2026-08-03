from __future__ import annotations

import logging
from datetime import datetime

from models import ProjectInfo
from services.project_service import ProjectService
from services.tiktok.api_client import TikTokApiClient
from services.tiktok.models import TikTokStatusResult, TikTokUploadError
from services.tiktok.oauth_service import TikTokOAuthService


TIKTOK_STATUS_URL = "https://open.tiktokapis.com/v2/post/publish/status/fetch/"


class TikTokStatusService:
    REMOTE_TO_LOCAL = {
        "PROCESSING_UPLOAD": "processing",
        "PROCESSING_DOWNLOAD": "processing",
        "SEND_TO_USER_INBOX": "action_required",
        "PUBLISH_COMPLETE": "uploaded",
        "FAILED": "failed",
    }

    def __init__(
        self,
        project_service: ProjectService,
        oauth_service: TikTokOAuthService,
        api_client: TikTokApiClient | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.project_service = project_service
        self.oauth_service = oauth_service
        self.api_client = api_client or TikTokApiClient()
        self.logger = logger or logging.getLogger("ai_video_factory.tiktok")

    def check_project(self, project: ProjectInfo) -> TikTokStatusResult:
        project = self.project_service.load_project(project.path)
        state = dict(project.tiktok_upload or {})
        publish_id = str(state.get("publish_id") or "")
        if not publish_id:
            raise TikTokUploadError("TikTok publish IDがないため、状態確認できません。")
        access_token = self.oauth_service.get_access_token()
        response = self.api_client.post_json(TIKTOK_STATUS_URL, access_token, {"publish_id": publish_id})
        data = response.data.get("data") if isinstance(response.data, dict) else {}
        if not isinstance(data, dict):
            raise TikTokUploadError("TikTok状態確認APIの応答形式が正しくありません。")
        remote_status = str(data.get("status") or "")
        local_status = self.REMOTE_TO_LOCAL.get(remote_status, "processing")
        uploaded_bytes = int(data.get("uploaded_bytes") or 0)
        fail_reason = str(data.get("fail_reason") or "")
        updates = {
            "status": local_status,
            "remote_status": remote_status or "UNKNOWN",
            "last_checked_at": self._now(),
            "error_code": "",
        }
        if fail_reason:
            updates["last_error"] = fail_reason
        elif local_status != "failed":
            updates["last_error"] = ""
        self._set_upload_state(project, updates)
        self.logger.info(
            "status check project_id=%s publish_id=%s remote_status=%s local_status=%s",
            project.name,
            publish_id,
            remote_status or "UNKNOWN",
            local_status,
        )
        return TikTokStatusResult(
            publish_id=publish_id,
            remote_status=remote_status or "UNKNOWN",
            local_status=local_status,
            uploaded_bytes=uploaded_bytes,
            fail_reason=fail_reason,
        )

    def local_status_for_remote(self, remote_status: str) -> str:
        return self.REMOTE_TO_LOCAL.get(remote_status, "processing")

    def _set_upload_state(self, project: ProjectInfo, updates: dict[str, object]) -> None:
        metadata = dict(project.tiktok_upload or {})
        metadata.update(updates)
        metadata.setdefault("status", "pending")
        self.project_service.update_metadata(project.path, {"tiktok_upload": metadata})

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
