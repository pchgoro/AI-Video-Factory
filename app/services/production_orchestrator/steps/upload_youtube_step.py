from __future__ import annotations

from services.production_orchestrator.models import StepResult
from services.youtube.upload_service import YouTubeUploadService

from .base import ProductionStepAdapter, StepContext


class UploadYouTubeStep(ProductionStepAdapter):
    step_id = "upload_youtube"

    def __init__(self, upload_service: YouTubeUploadService) -> None:
        self.upload_service = upload_service

    def run(self, context: StepContext) -> StepResult:
        if self.is_cancelled(context):
            return self.cancelled()
        status = context.artifact_service.youtube_status(context.project)
        if status.get("duplicate"):
            return StepResult.skipped("Existing YouTube video ID prevents duplicate upload.", {"reused": True, **status})
        if context.dry_run:
            video_status = context.artifact_service.video_status(context.project)
            if video_status.get("state") != "fresh":
                return StepResult.failed("final.mp4 is not ready.", "missing_final_mp4", False)
            return StepResult.succeeded("YouTube upload can run.", {"dry_run": True})
        result = self.upload_service.upload_project(
            context.project,
            retry=False,
            progress_callback=context.progress_callback,
            should_cancel=context.should_cancel,
        )
        return StepResult.succeeded(
            "YouTube upload completed.",
            {"video_id": result.video_id, "url": result.url, "upload_timestamp": result.upload_timestamp},
        )
