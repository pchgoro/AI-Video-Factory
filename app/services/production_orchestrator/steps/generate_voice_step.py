from __future__ import annotations

from services.production_orchestrator.models import StepResult
from services.voicevox_service import VoicevoxService

from .base import ProductionStepAdapter, StepContext


class GenerateVoiceStep(ProductionStepAdapter):
    step_id = "generate_voice"

    def __init__(self, voicevox_service: VoicevoxService) -> None:
        self.voicevox_service = voicevox_service

    def run(self, context: StepContext) -> StepResult:
        if self.is_cancelled(context):
            return self.cancelled()
        if context.options.reuse_existing_artifacts:
            status = context.artifact_service.audio_status(context.project)
            if status.get("state") == "fresh":
                return StepResult.skipped("Existing voice.wav was reused.", {"reused": True, **status})
        if context.dry_run:
            voice_file = context.project_dir / "voice.txt"
            if not voice_file.exists() or not voice_file.read_text(encoding="utf-8").strip():
                return StepResult.failed("voice.txt is missing or empty.", "missing_voice_text", False)
            return StepResult.succeeded("VOICEVOX generation can run.", {"dry_run": True})
        result = self.voicevox_service.synthesize_project(context.project_dir)
        if result.success:
            return StepResult.succeeded("VOICEVOX audio generated.", {"output_path": self.relative_path(context, result.output_path)})
        return StepResult.failed(result.message, "voice_generation_failed", True)
