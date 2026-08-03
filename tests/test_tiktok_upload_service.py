from __future__ import annotations

from pathlib import Path

import pytest

from config import AppPaths
from services.project_service import ProjectService
from services.tiktok.api_client import TikTokApiResponse
from services.tiktok.models import TikTokDuplicateUploadError, TikTokUploadError, TikTokValidationError
from services.tiktok.upload_service import TikTokUploadService
from services.tiktok.video_validator import TikTokVideoValidator


class FakeOAuth:
    def __init__(self) -> None:
        self.calls = 0

    def get_access_token(self) -> str:
        self.calls += 1
        return "access-token"


class FakeApiClient:
    def __init__(self, init_errors: list[Exception] | None = None, transfer_errors: list[Exception] | None = None) -> None:
        self.init_errors = list(init_errors or [])
        self.transfer_errors = list(transfer_errors or [])
        self.post_calls: list[dict[str, object]] = []
        self.put_calls: list[dict[str, object]] = []

    def post_json(self, url: str, access_token: str, payload: dict[str, object], timeout: int = 60) -> TikTokApiResponse:
        self.post_calls.append({"url": url, "access_token": access_token, "payload": payload, "timeout": timeout})
        if "status/fetch" in url:
            return TikTokApiResponse({"data": {"status": "SEND_TO_USER_INBOX", "uploaded_bytes": 123}}, {})
        if self.init_errors:
            raise self.init_errors.pop(0)
        return TikTokApiResponse({"data": {"publish_id": "pub123", "upload_url": "https://upload.example/session"}}, {})

    def put_bytes(self, url: str, access_token: str, data: bytes, content_range: str, timeout: int = 120) -> TikTokApiResponse:
        self.put_calls.append({"url": url, "access_token": access_token, "data": data, "content_range": content_range, "timeout": timeout})
        if self.transfer_errors:
            raise self.transfer_errors.pop(0)
        return TikTokApiResponse({}, {})


class FakeValidator:
    def validate_final_mp4(self, project):
        return project.path / "video" / "final.mp4"


def _project(tmp_path: Path):
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("Black Hole", "space", "60s", 3, "prompt", tags=["space"])
    final_mp4 = project.path / "video" / "final.mp4"
    final_mp4.write_bytes(b"\x00\x00\x00\x18ftypisomvideo-data")
    return project_service, project_service.load_project(project.path)


def _service(project_service, api_client=None, oauth=None, **kwargs) -> TikTokUploadService:
    return TikTokUploadService(
        project_service,
        oauth or FakeOAuth(),
        api_client=api_client or FakeApiClient(),
        video_validator=FakeValidator(),
        max_retries=kwargs.pop("max_retries", 3),
        backoff_base_seconds=0,
        sleeper=lambda _delay: None,
        **kwargs,
    )


def test_upload_success_saves_state_without_upload_url(tmp_path) -> None:
    project_service, project = _project(tmp_path)
    api_client = FakeApiClient()
    service = _service(project_service, api_client=api_client)

    result = service.upload_project(project)

    assert result.publish_id == "pub123"
    reloaded = project_service.load_project(project.path)
    assert reloaded.tiktok_upload["publish_id"] == "pub123"
    assert reloaded.tiktok_upload["status"] == "action_required"
    assert reloaded.tiktok_upload["remote_status"] == "SEND_TO_USER_INBOX"
    assert "upload_url" not in reloaded.tiktok_upload
    assert api_client.put_calls[0]["content_range"].startswith("bytes 0-")


def test_retry_succeeds_after_transient_init_error(tmp_path) -> None:
    project_service, project = _project(tmp_path)
    api_client = FakeApiClient(init_errors=[TikTokUploadError("temporary", retryable=True, error_code="rate_limit_exceeded")])
    events = []
    service = _service(project_service, api_client=api_client)

    result = service.upload_project(project, progress_callback=events.append)

    assert result.publish_id == "pub123"
    assert len(api_client.post_calls) >= 2
    assert any(event["retrying"] for event in events)


def test_retry_limit_records_failure_without_changing_job(tmp_path) -> None:
    project_service, project = _project(tmp_path)
    project_service.update_metadata(project.path, {"job": {"status": "video_ready"}})
    project = project_service.load_project(project.path)
    api_client = FakeApiClient(
        init_errors=[
            TikTokUploadError("temporary", retryable=True, error_code="server_error"),
            TikTokUploadError("temporary", retryable=True, error_code="server_error"),
        ]
    )
    service = _service(project_service, api_client=api_client, max_retries=1)

    with pytest.raises(TikTokUploadError):
        service.upload_project(project, retry=True)

    reloaded = project_service.load_project(project.path)
    assert reloaded.tiktok_upload["status"] == "failed"
    assert reloaded.job["status"] == "video_ready"


def test_auth_error_is_not_retried(tmp_path) -> None:
    project_service, project = _project(tmp_path)
    api_client = FakeApiClient(init_errors=[TikTokUploadError("auth", retryable=False, error_code="scope_not_authorized")])
    service = _service(project_service, api_client=api_client, max_retries=3)

    with pytest.raises(TikTokUploadError):
        service.upload_project(project)

    assert len(api_client.post_calls) == 1


def test_duplicate_prevention_blocks_existing_publish_id(tmp_path) -> None:
    project_service, project = _project(tmp_path)
    project_service.update_metadata(project.path, {"tiktok_upload": {"status": "action_required", "publish_id": "pub123"}})
    project = project_service.load_project(project.path)
    oauth = FakeOAuth()
    service = _service(project_service, oauth=oauth)

    with pytest.raises(TikTokDuplicateUploadError):
        service.upload_project(project)

    assert oauth.calls == 0


def test_video_validator_rejects_missing_final_mp4(tmp_path) -> None:
    project_service, project = _project(tmp_path)
    (project.path / "video" / "final.mp4").unlink()
    validator = TikTokVideoValidator()

    with pytest.raises(TikTokValidationError):
        validator.validate_final_mp4(project)


def test_upload_service_does_not_use_direct_post_endpoint() -> None:
    source = Path("app/services/tiktok/upload_service.py").read_text(encoding="utf-8")

    assert "/v2/post/publish/video/init/" not in source
    assert "/v2/post/publish/inbox/video/init/" in source
