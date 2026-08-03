from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from models import AppSettings, ProjectInfo
from services.image_generation.models import ImageGenerationSettings
from services.production_orchestrator.artifact_service import ArtifactService
from services.production_orchestrator.models import ProductionOptions, StepResult


ProgressCallback = Callable[[dict[str, object]], None]
CancelCallback = Callable[[], bool]


@dataclass
class StepContext:
    project: ProjectInfo
    settings: AppSettings
    image_settings: ImageGenerationSettings
    options: ProductionOptions
    artifact_service: ArtifactService
    input_snapshot: dict
    progress_callback: ProgressCallback | None = None
    should_cancel: CancelCallback | None = None
    dry_run: bool = False

    @property
    def project_dir(self) -> Path:
        return self.project.path


class ProductionStepAdapter:
    step_id = ""

    def run(self, context: StepContext) -> StepResult:
        raise NotImplementedError

    def sanitize_error(self, exc: Exception) -> str:
        text = str(exc) or exc.__class__.__name__
        forbidden = ["Authorization", "Bearer ", "access_token", "refresh_token", "client_secret"]
        for value in forbidden:
            text = text.replace(value, "[redacted]")
        return text[:2000]

    def emit(self, context: StepContext, progress: int, message: str) -> None:
        if context.progress_callback:
            context.progress_callback({"step_id": self.step_id, "progress": max(0, min(100, int(progress))), "message": message})

    def is_cancelled(self, context: StepContext) -> bool:
        return bool(context.should_cancel and context.should_cancel())

    def cancelled(self) -> StepResult:
        return StepResult("cancelled", "Cancelled by user.", 0, True, "cancelled", {})

    def relative_path(self, context: StepContext, path: Path | None) -> str:
        if path is None:
            return ""
        try:
            return str(path.resolve().relative_to(context.project_dir.resolve())).replace("\\", "/")
        except ValueError:
            return path.name
