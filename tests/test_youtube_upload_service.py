from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from config import AppPaths
from services.job_service import JobService
from services.project_service import ProjectService
from services.youtube.models import YouTubeDuplicateUploadError, YouTubeTokenStorageError, YouTubeUploadError, YouTubeValidationError
from services.youtube.token_store import KeyringTokenStore
from services.youtube.upload_service import YouTubeUploadService


class FakeProgress:
    def __init__(self, value: float) -> None:
        self.value = value

    def progress(self) -> float:
        return self.value


class FakeHttpError(Exception):
    def __init__(self, status: int) -> None:
        self.resp = type("Resp", (), {"status": status})()


class FakeRequest:
    def __init__(self, outcomes: list[object]) -> None:
        self.outcomes = list(outcomes)

    def next_chunk(self):
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class FakeVideos:
    def __init__(self, request: FakeRequest, captured: dict[str, object]) -> None:
        self.request = request
        self.captured = captured

    def insert(self, **kwargs):
        self.captured.update(kwargs)
        return self.request


class FakeYouTube:
    def __init__(self, request: FakeRequest, captured: dict[str, object]) -> None:
        self.request = request
        self.captured = captured

    def videos(self) -> FakeVideos:
        return FakeVideos(self.request, self.captured)


class FakeOAuth:
    def __init__(self, youtube: FakeYouTube | None = None, error: Exception | None = None) -> None:
        self.youtube = youtube
        self.error = error
        self.calls = 0

    def build_youtube_client(self):
        self.calls += 1
        if self.error:
            raise self.error
        return self.youtube


def _project(tmp_path: Path):
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("Black Hole", "space", "60s", 3, "prompt", tags=["space"])
    project_service.save_preview_files(project, {"script.txt": "description"})
    return project_service, JobService(project_service), project_service.load_project(project.path)


def _write_final_mp4(project) -> Path:
    final_mp4 = project.path / "video" / "final.mp4"
    final_mp4.write_bytes(b"\x00\x00\x00\x18ftypisom\x00\x00video")
    return final_mp4


def _service(project_service, job_service, oauth, **kwargs):
    return YouTubeUploadService(
        project_service,
        job_service,
        oauth,
        max_retries=kwargs.pop("max_retries", 3),
        backoff_base_seconds=0,
        sleeper=lambda _delay: None,
        media_upload_factory=lambda *args, **media_kwargs: {"args": args, "kwargs": media_kwargs},
        **kwargs,
    )


def test_missing_final_mp4_does_not_upload(tmp_path) -> None:
    project_service, job_service, project = _project(tmp_path)
    oauth = FakeOAuth()
    service = _service(project_service, job_service, oauth)

    with pytest.raises(YouTubeValidationError):
        service.upload_project(project)

    assert oauth.calls == 0


def test_empty_final_mp4_does_not_upload(tmp_path) -> None:
    project_service, job_service, project = _project(tmp_path)
    (project.path / "video" / "final.mp4").write_bytes(b"")
    service = _service(project_service, job_service, FakeOAuth())

    with pytest.raises(YouTubeValidationError):
        service.upload_project(project)


def test_upload_uses_private_status_and_saves_video_id(tmp_path) -> None:
    project_service, job_service, project = _project(tmp_path)
    _write_final_mp4(project)
    captured: dict[str, object] = {}
    request = FakeRequest([(FakeProgress(1.0), {"id": "abc123"})])
    service = _service(project_service, job_service, FakeOAuth(FakeYouTube(request, captured)))

    result = service.upload_project(project)

    assert result.video_id == "abc123"
    body = captured["body"]
    assert body["status"]["privacyStatus"] == "private"
    assert body["status"]["selfDeclaredMadeForKids"] is False
    reloaded = project_service.load_project(project.path)
    assert reloaded.youtube_upload["video_id"] == "abc123"
    assert reloaded.youtube_upload["status"] == "uploaded"
    assert reloaded.job["status"] == "youtube_uploaded"


def test_retry_succeeds_after_transient_error(tmp_path) -> None:
    project_service, job_service, project = _project(tmp_path)
    _write_final_mp4(project)
    captured: dict[str, object] = {}
    request = FakeRequest([FakeHttpError(503), (FakeProgress(1.0), {"id": "retry123"})])
    events = []
    service = _service(project_service, job_service, FakeOAuth(FakeYouTube(request, captured)))

    result = service.upload_project(project, progress_callback=events.append)

    assert result.video_id == "retry123"
    assert result.retry_count == 1
    assert any(event["retrying"] for event in events)


def test_retry_limit_stops_upload(tmp_path) -> None:
    project_service, job_service, project = _project(tmp_path)
    _write_final_mp4(project)
    project = job_service.ensure_job(project)
    assert project.job["status"] == "video_ready"
    captured: dict[str, object] = {}
    request = FakeRequest([FakeHttpError(503), FakeHttpError(503)])
    service = _service(project_service, job_service, FakeOAuth(FakeYouTube(request, captured)), max_retries=1)

    with pytest.raises(YouTubeUploadError):
        service.upload_project(project, retry=True)

    reloaded = project_service.load_project(project.path)
    assert reloaded.youtube_upload["status"] == "failed"
    assert reloaded.job["status"] == "video_ready"


def test_auth_error_is_not_retried_forever(tmp_path) -> None:
    project_service, job_service, project = _project(tmp_path)
    _write_final_mp4(project)
    captured: dict[str, object] = {}
    request = FakeRequest([FakeHttpError(401)])
    service = _service(project_service, job_service, FakeOAuth(FakeYouTube(request, captured)), max_retries=3)

    with pytest.raises(YouTubeUploadError):
        service.upload_project(project)

    reloaded = project_service.load_project(project.path)
    assert reloaded.youtube_upload["status"] == "failed"


def test_duplicate_prevention_blocks_existing_video_id(tmp_path) -> None:
    project_service, job_service, project = _project(tmp_path)
    _write_final_mp4(project)
    project_service.update_metadata(project.path, {"youtube_upload": {"status": "uploaded", "video_id": "abc123"}})
    project = project_service.load_project(project.path)
    oauth = FakeOAuth()
    service = _service(project_service, job_service, oauth)

    with pytest.raises(YouTubeDuplicateUploadError):
        service.upload_project(project)

    assert oauth.calls == 0


def test_keyring_unavailable_does_not_store_plaintext(monkeypatch) -> None:
    def fail_import(name: str):
        if name == "keyring":
            raise ModuleNotFoundError("no keyring")
        return importlib.import_module(name)

    monkeypatch.setattr(importlib, "import_module", fail_import)
    store = KeyringTokenStore()

    with pytest.raises(YouTubeTokenStorageError):
        store.save_refresh_token("default", "dummy-refresh-token")
