from __future__ import annotations

from services.production_orchestrator.models import ProductionOptions, ProductionRun, ProductionStep


def test_production_run_serialization_and_interrupted_restore() -> None:
    run = ProductionRun.create("run1", "project1", "normal", ProductionOptions(upload_youtube=True))
    step = run.step("generate_images")
    assert step is not None
    step.status = "running"
    run.status = "running"

    restored = ProductionRun.from_dict(run.to_dict())

    assert restored.status == "interrupted"
    assert restored.step("generate_images").status == "interrupted"
    assert restored.step("generate_images").retryable is True


def test_step_progress_is_clamped() -> None:
    step = ProductionStep.from_dict({"step_id": "x", "progress": 999, "status": "succeeded"})

    assert step.progress == 100
    assert step.to_dict()["progress"] == 100


def test_options_keep_uploads_off_by_default() -> None:
    options = ProductionOptions()

    assert options.export_story is True
    assert options.upload_youtube is False
    assert options.upload_tiktok is False
    assert options.is_enabled("validate_story") is True
