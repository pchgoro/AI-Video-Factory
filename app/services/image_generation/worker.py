from __future__ import annotations

from dataclasses import asdict

from PySide6.QtCore import QObject, Signal

from models import ProjectInfo

from .image_generation_service import ImageGenerationService
from .models import ImageGenerationSettings


class ImageGenerationWorker(QObject):
    """Run image generation service calls outside the UI thread."""

    progress = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(
        self,
        service: ImageGenerationService,
        project: ProjectInfo,
        settings: ImageGenerationSettings,
        retry_failed: bool = False,
    ) -> None:
        super().__init__()
        self.service = service
        self.project = project
        self.settings = settings
        self.retry_failed = retry_failed
        self._cancel_requested = False

    def cancel(self) -> None:
        self._cancel_requested = True

    def _should_cancel(self) -> bool:
        return self._cancel_requested

    def run(self) -> None:
        try:
            if self.retry_failed:
                result = self.service.retry_failed(
                    self.project,
                    self.settings,
                    progress_callback=self.progress.emit,
                    should_cancel=self._should_cancel,
                )
            else:
                result = self.service.generate_missing(
                    self.project,
                    self.settings,
                    progress_callback=self.progress.emit,
                    should_cancel=self._should_cancel,
                )
            payload = asdict(result)
            if payload.get("manifest_path") is not None:
                payload["manifest_path"] = str(payload["manifest_path"])
            self.finished.emit(payload)
        except Exception as exc:
            self.failed.emit(str(exc))
