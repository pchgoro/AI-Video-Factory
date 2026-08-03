from __future__ import annotations

import json

from config import AppPaths
from services.job_service import JobService
from services.project_service import ProjectService


def test_existing_project_loads_without_job_keys(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_dir = paths.projects_dir / "old_project"
    (project_dir / "video").mkdir(parents=True)
    (project_dir / "project.json").write_text(json.dumps({"topic": "old"}, ensure_ascii=False), encoding="utf-8")

    project = ProjectService(paths).load_project(project_dir)

    assert project.job == {}
    assert project.youtube_upload == {}


def test_job_state_saves_and_restores(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    job_service = JobService(project_service)
    project = project_service.create_project("topic", "space", "60s", 3, "prompt")

    reloaded = job_service.set_status(project, "script_ready")

    assert reloaded.job["status"] == "script_ready"
    restored = project_service.load_project(project.path)
    assert restored.job["project_id"] == project.name
    assert restored.job["status"] == "script_ready"


def test_job_infers_video_ready_from_final_mp4(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    job_service = JobService(project_service)
    project = project_service.create_project("topic", "space", "60s", 3, "prompt")
    final_mp4 = project.path / "video" / "final.mp4"
    final_mp4.write_bytes(b"\x00\x00\x00\x18ftypisom")

    reloaded = job_service.ensure_job(project)

    assert reloaded.job["status"] == "video_ready"
