from __future__ import annotations

from config import AppPaths
from services.project_service import ProjectService


def test_existing_project_without_tiktok_upload_is_backward_compatible(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("topic", "genre", "60s", 3, "prompt")

    loaded = project_service.load_project(project.path)

    assert loaded.tiktok_upload == {}
