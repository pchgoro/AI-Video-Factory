from __future__ import annotations

from services.production_orchestrator.models import StepResult
from services.video_render_service import VideoRenderService

from .base import ProductionStepAdapter, StepContext


class RenderVideoStep(ProductionStepAdapter):
    step_id = "render_video"

    def __init__(self, video_render_service: VideoRenderService) -> None:
        self.video_render_service = video_render_service

    def run(self, context: StepContext) -> StepResult:
        if self.is_cancelled(context):
            return self.cancelled()
        if context.options.reuse_existing_artifacts:
            status = context.artifact_service.video_status(context.project)
            if status.get("state") == "fresh":
                return StepResult.skipped("Existing final.mp4 was reused.", {"reused": True, **status})
        if context.dry_run:
            for key, checker in [
                ("images", context.artifact_service.images_status),
                ("audio", context.artifact_service.audio_status),
                ("subtitles", context.artifact_service.subtitle_status),
            ]:
                if checker(context.project).get("state") not in {"fresh", "stale"}:
                    return StepResult.failed(f"{key} artifact is not ready.", f"{key}_missing", False)
            return StepResult.succeeded("Video render can run.", {"dry_run": True})
        subtitles_path = context.project_dir / "video" / "subtitles.ass"
        result = self.video_render_service.render_project(
            context.project,
            subtitles_path=subtitles_path if subtitles_path.exists() else None,
            generate_subtitles=False,
        )
        if result.success:
            return StepResult.succeeded("Video rendered.", {"output_path": self.relative_path(context, result.output_path)})
        return StepResult.failed(result.message, "video_render_failed", True)
