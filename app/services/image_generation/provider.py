from __future__ import annotations

from abc import ABC, abstractmethod

from .models import GeneratedImage, ImageGenerationSettings, ModelInfo, ProviderStatus, UsageEstimate


class ImageGenerationProvider(ABC):
    """Small provider boundary so UI and project services stay provider-neutral."""

    @abstractmethod
    def validate_configuration(self) -> ProviderStatus:
        raise NotImplementedError

    @abstractmethod
    def get_model_info(self, model: str) -> ModelInfo:
        raise NotImplementedError

    @abstractmethod
    def validate_model_settings(self, settings: ImageGenerationSettings) -> None:
        raise NotImplementedError

    @abstractmethod
    def estimate_usage(self, request_count: int, settings: ImageGenerationSettings) -> UsageEstimate:
        raise NotImplementedError

    @abstractmethod
    def generate_image(self, prompt: str, settings: ImageGenerationSettings, should_cancel=None) -> GeneratedImage:
        raise NotImplementedError
