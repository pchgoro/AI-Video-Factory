from __future__ import annotations

from pathlib import Path

from config import AppPaths
from models import AppSettings
from services.production_orchestrator import ArtifactService, ProductionOptions
from services.production_orchestrator.models import StepResult
from services.production_orchestrator.steps import RenderVideoStep, StepContext
from services.project_service import ProjectService
from video_editors.base import VideoEditResult


class FakeVideoRenderService:
    def __init__(self) -> None:
        self.calls = []

    def render_project(self, project, subtitles_path=None, generate_subtitles=True):
        self.calls.append({"subtitles_path": subtitles_path, "generate_subtitles": generate_subtitles})
        output = project.path / "video" / "final.mp4"
        output.parent.mkdir(exist_ok=True)
        output.write_bytes(b"\x00\x00\x00\x18ftypmp42")
        return VideoEditResult(True, "ok", output)


def _context(tmp_path: Path) -> StepContext:
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("topic", "genre", "60", 3, "prompt")
    (project.path / "video").mkdir(exist_ok=True)
    (project.path / "video" / "subtitles.ass").write_text("[Script Info]\n[Events]\n", encoding="utf-8")
    return StepContext(
        project=project,
        settings=AppSettings(),
        image_settings=None,
        options=ProductionOptions(reuse_existing_artifacts=False),
        artifact_service=ArtifactService(AppSettings()),
        input_snapshot={},
        dry_run=False,
    )


def test_render_adapter_reuses_existing_subtitles_without_regeneration(tmp_path: Path) -> None:
    context = _context(tmp_path)
    render_service = FakeVideoRenderService()
    adapter = RenderVideoStep(render_service)

    result = adapter.run(context)

    assert result.status == "succeeded"
    assert render_service.calls[0]["generate_subtitles"] is False
    assert render_service.calls[0]["subtitles_path"].name == "subtitles.ass"
