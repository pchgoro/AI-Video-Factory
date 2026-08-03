from __future__ import annotations

import json
from pathlib import Path

from config import AppPaths
from services.project_service import ProjectService


def test_existing_project_without_image_generation_is_backward_compatible(tmp_path: Path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    service = ProjectService(paths)
    project = service.create_project("topic", "genre", "60秒", 3, "prompt")

    metadata = json.loads((project.path / "project.json").read_text(encoding="utf-8"))
    metadata.pop("image_generation", None)
    (project.path / "project.json").write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

    loaded = service.load_project(project.path)

    assert loaded.image_generation == {}
    assert loaded.youtube_upload == {}
    assert loaded.tiktok_upload == {}
