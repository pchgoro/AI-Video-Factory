from __future__ import annotations

import json
from pathlib import Path

from config import AppPaths
from models import AppSettings
from services.production_orchestrator import ArtifactService, ProductionOptions, ProductionOrchestratorService, ProductionPreflightService
from services.production_orchestrator.models import StepResult
from services.production_orchestrator.steps.base import ProductionStepAdapter
from services.project_service import ProjectService
from services.story_composer import StoryService


class RecordingStep(ProductionStepAdapter):
    def __init__(self, step_id: str, calls: list[str], result: StepResult | None = None) -> None:
        self.step_id = step_id
        self.calls = calls
        self.result = result or StepResult.succeeded(f"{step_id} ok")

    def run(self, context):
        self.calls.append(self.step_id)
        return self.result


class FakePreflight(ProductionPreflightService):
    def __init__(self):
        pass

    def check(self, project, options, image_settings, dry_run=False):
        from services.production_orchestrator.models import PreflightResult

        return PreflightResult()


def _project(tmp_path: Path):
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("topic", "genre", "60", 3, "prompt")
    (project.path / "story.json").write_text("{}", encoding="utf-8")
    return project_service, project_service.load_project(project.path)


def _service(tmp_path: Path, calls: list[str], result_for: dict[str, StepResult] | None = None):
    project_service, project = _project(tmp_path)
    result_for = result_for or {}
    adapters = {step_id: RecordingStep(step_id, calls, result_for.get(step_id)) for step_id in [
        "validate_story",
        "export_story",
        "generate_images",
        "generate_voice",
        "generate_subtitles",
        "render_video",
        "upload_youtube",
        "upload_tiktok",
    ]}
    service = ProductionOrchestratorService(
        project_service,
        AppSettings(),
        FakePreflight(),
        adapters,
        artifact_service=ArtifactService(AppSettings()),
    )
    return service, project_service, project


def test_orchestrator_runs_steps_in_order_and_saves_run(tmp_path: Path) -> None:
    calls: list[str] = []
    service, _project_service, project = _service(tmp_path, calls)

    run = service.start(project, ProductionOptions(upload_youtube=True, upload_tiktok=True), mode="normal")

    assert run.status == "succeeded"
    assert calls == [
        "validate_story",
        "export_story",
        "generate_images",
        "generate_voice",
        "generate_subtitles",
        "render_video",
        "upload_youtube",
        "upload_tiktok",
    ]
    assert (project.path / "production_run.json").exists()


def test_failure_blocks_downstream_render_and_upload(tmp_path: Path) -> None:
    calls: list[str] = []
    service, _project_service, project = _service(
        tmp_path,
        calls,
        {"generate_voice": StepResult.failed("voice failed", "voice", True)},
    )

    run = service.start(project, ProductionOptions(upload_youtube=True), mode="normal")

    assert run.status == "partially_succeeded"
    assert "render_video" not in calls
    assert run.step("render_video").status == "blocked"


def test_youtube_failure_can_continue_to_tiktok(tmp_path: Path) -> None:
    calls: list[str] = []
    service, _project_service, project = _service(
        tmp_path,
        calls,
        {"upload_youtube": StepResult.failed("youtube failed", "youtube", True)},
    )

    run = service.start(
        project,
        ProductionOptions(upload_youtube=True, upload_tiktok=True, continue_independent_upload_steps=True),
        mode="normal",
    )

    assert "upload_tiktok" in calls
    assert run.step("upload_youtube").status == "failed"
    assert run.step("upload_tiktok").status == "succeeded"


def test_dry_run_records_run_without_factory_output_changes(tmp_path: Path) -> None:
    calls: list[str] = []
    service, _project_service, project = _service(tmp_path, calls)
    before = {path.name for path in project.path.iterdir()}

    run = service.start(project, ProductionOptions(), mode="dry_run")

    after = {path.name for path in project.path.iterdir()}
    assert run.mode == "dry_run"
    assert "production_run.json" in after - before
    assert not {"title2.txt", "unexpected.mp4"} & after


def test_outputs_are_sanitized(tmp_path: Path) -> None:
    calls: list[str] = []
    service, _project_service, project = _service(
        tmp_path,
        calls,
        {"validate_story": StepResult.succeeded("ok", {"access_token": "secret", "video_id": "abc"})},
    )

    run = service.start(project, ProductionOptions(export_story=False, generate_images=False, generate_voice=False, generate_subtitles=False, render_video=False), mode="normal")

    outputs = run.step("validate_story").outputs
    assert "access_token" not in outputs
    assert outputs["video_id"] == "abc"
