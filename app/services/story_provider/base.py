from __future__ import annotations

from abc import ABC, abstractmethod

from .models import (
    CancellationToken,
    ConfigurationResult,
    ProgressCallback,
    ProviderCapabilities,
    StoryCostEstimate,
    StoryGenerationRequest,
    StoryGenerationResult,
)


class StoryAIProvider(ABC):
    @property
    @abstractmethod
    def provider_id(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_name(self) -> str:
        raise NotImplementedError

    @property
    @abstractmethod
    def provider_version(self) -> str:
        raise NotImplementedError

    @abstractmethod
    def capabilities(self) -> ProviderCapabilities:
        raise NotImplementedError

    @abstractmethod
    def validate_configuration(self) -> ConfigurationResult:
        raise NotImplementedError

    @abstractmethod
    def estimate_cost(self, request: StoryGenerationRequest) -> StoryCostEstimate:
        raise NotImplementedError

    @abstractmethod
    def generate_story(
        self,
        request: StoryGenerationRequest,
        cancellation_token: CancellationToken | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> StoryGenerationResult:
        raise NotImplementedError
