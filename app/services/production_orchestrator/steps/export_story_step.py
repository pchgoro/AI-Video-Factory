from __future__ import annotations

from services.production_orchestrator.models import StepResult
from services.story_composer import StoryService

from .base import ProductionStepAdapter, StepContext


class ExportStoryStep(ProductionStepAdapter):
    step_id = "export_story"

    def __init__(self, story_service: StoryService) -> None:
        self.story_service = story_service

    def run(self, context: StepContext) -> StepResult:
        if self.is_cancelled(context):
            return self.cancelled()
        if context.options.reuse_existing_artifacts:
            status = context.artifact_service.factory_export_status(context.project)
            if status.get("state") == "fresh" and not context.options.export_story:
                return StepResult.skipped("Existing Factory export files were reused.", {"reused": True})
        if context.dry_run:
            preview = self.story_service.export_preview(context.project)
            return StepResult.succeeded(
                "Story export can run.",
                {"target_files": preview.target_files, "dry_run": True},
            )
        result = self.story_service.export_to_factory(context.project)
        return StepResult.succeeded(
            "Story exported to Factory files.",
            {
                "exported_at": result.exported_at,
                "backup_dir": self.relative_path(context, result.backup_dir),
                "files": result.files,
            },
        )
