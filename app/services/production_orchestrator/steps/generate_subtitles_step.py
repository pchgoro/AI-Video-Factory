from __future__ import annotations

from services.production_orchestrator.models import StepResult
from services.subtitle_service import SubtitleService

from .base import ProductionStepAdapter, StepContext


class GenerateSubtitlesStep(ProductionStepAdapter):
    step_id = "generate_subtitles"

    def __init__(self, subtitle_service: SubtitleService) -> None:
        self.subtitle_service = subtitle_service

    def run(self, context: StepContext) -> StepResult:
        if self.is_cancelled(context):
            return self.cancelled()
        if context.options.reuse_existing_artifacts:
            status = context.artifact_service.subtitle_status(context.project)
            if status.get("state") == "fresh":
                return StepResult.skipped("Existing subtitles.ass was reused.", {"reused": True, **status})
        if context.dry_run:
            source = context.project_dir / "subtitles.txt"
            if not source.exists():
                return StepResult.failed("subtitles.txt is missing.", "missing_subtitles", False)
            return StepResult.succeeded("Subtitle generation can run.", {"dry_run": True})
        path = self.subtitle_service.generate_for_project(context.project_dir, context.settings)
        if path is None:
            return StepResult.skipped("Subtitles are disabled or no subtitle data exists.", {"reused": False})
        status = context.artifact_service.subtitle_status(context.project)
        if status.get("state") != "fresh":
            return StepResult.failed("Generated subtitles.ass could not be validated.", "subtitle_invalid", False)
        return StepResult.succeeded("subtitles.ass generated.", {"output_path": self.relative_path(context, path)})
