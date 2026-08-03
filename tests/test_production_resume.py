from __future__ import annotations

from pathlib import Path

import pytest

from config import AppPaths
from models import AppSettings
from services.production_orchestrator import ArtifactService, ProductionOptions, ProductionOrchestratorService, ProductionRunRepository
from services.production_orchestrator.models import ProductionRun, StepResult
from services.production_orchestrator.steps.base import ProductionStepAdapter
from services.project_service import ProjectService

from test_production_orchestrator import FakePreflight, RecordingStep


def _project(tmp_path: Path):
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("topic", "genre", "60", 3, "prompt")
    return project_service, project


def test_running_run_restores_as_interrupted(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path)
    repository = ProductionRunRepository()
    run = ProductionRun.create("run1", project.name, "normal", ProductionOptions())
    run.status = "running"
    run.step("generate_images").status = "running"
    repository.save(project.path, run, force=True)

    restored = repository.load(project.path)

    assert restored.status == "interrupted"
    assert restored.step("generate_images").status == "interrupted"


def test_retry_failed_step_reruns_first_retryable_step(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path)
    calls: list[str] = []
    adapters = {step_id: RecordingStep(step_id, calls) for step_id in [
        "validate_story",
        "export_story",
        "generate_images",
        "generate_voice",
        "generate_subtitles",
        "render_video",
        "upload_youtube",
        "upload_tiktok",
    ]}
    service = ProductionOrchestratorService(project_service, AppSettings(), FakePreflight(), adapters, artifact_service=ArtifactService(AppSettings()))
    run = ProductionRun.create("run1", project.name, "normal", ProductionOptions())
    run.step("validate_story").status = "succeeded"
    run.step("export_story").status = "failed"
    run.step("export_story").retryable = True
    service.repository.save(project.path, run, force=True)

    retried = service.retry_failed_step(project)

    assert "export_story" in calls
    assert retried.step("export_story").status == "succeeded"


def test_attempt_limit_blocks_retry(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path)
    service = ProductionOrchestratorService(project_service, AppSettings(), FakePreflight(), {}, artifact_service=ArtifactService(AppSettings()))
    run = ProductionRun.create("run1", project.name, "normal", ProductionOptions())
    step = run.step("validate_story")
    step.status = "failed"
    step.retryable = True
    step.attempt_count = 3
    service.repository.save(project.path, run, force=True)

    with pytest.raises(ValueError):
        service.retry_failed_step(project)


def test_cancel_request_is_persisted(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path)
    service = ProductionOrchestratorService(project_service, AppSettings(), FakePreflight(), {}, artifact_service=ArtifactService(AppSettings()))
    run = ProductionRun.create("run1", project.name, "normal", ProductionOptions())
    service.repository.save(project.path, run, force=True)

    service.request_cancel(project)

    assert service.repository.load(project.path).cancel_requested is True
