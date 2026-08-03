from __future__ import annotations

from services.image_generation import ImageGenerationService
from services.production_orchestrator.models import StepResult

from .base import ProductionStepAdapter, StepContext


class GenerateImagesStep(ProductionStepAdapter):
    step_id = "generate_images"

    def __init__(self, image_generation_service: ImageGenerationService) -> None:
        self.image_generation_service = image_generation_service

    def run(self, context: StepContext) -> StepResult:
        if self.is_cancelled(context):
            return self.cancelled()
        if context.options.reuse_existing_artifacts:
            status = context.artifact_service.images_status(context.project)
            if status.get("state") == "fresh":
                return StepResult.skipped("Existing valid images were reused.", {"reused": True, **status})
        if context.dry_run:
            summary = self.image_generation_service.summarize_project(context.project, context.image_settings)
            return StepResult.succeeded(
                "Image generation preflight succeeded.",
                {
                    "missing_indices": summary.get("missing_indices", []),
                    "existing_indices": summary.get("existing_indices", []),
                    "dry_run": True,
                },
            )
        result = self.image_generation_service.generate_missing(
            context.project,
            context.image_settings,
            progress_callback=context.progress_callback,
            should_cancel=context.should_cancel,
        )
        if result.status in {"completed", "partially_completed"} and not result.failed_indices:
            return StepResult.succeeded(
                "Image generation completed.",
                {
                    "generated_indices": result.generated_indices,
                    "skipped_existing_indices": result.skipped_existing_indices,
                    "completed_count": result.completed_count,
                },
            )
        if result.status == "cancelled":
            return StepResult("cancelled", result.last_error or "Image generation cancelled.", 0, True, "cancelled")
        return StepResult.failed(result.last_error or "Image generation failed.", "image_generation_failed", True)
