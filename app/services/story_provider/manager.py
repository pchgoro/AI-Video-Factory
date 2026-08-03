from __future__ import annotations

from typing import Any

from .base import StoryAIProvider
from .models import (
    CancellationToken,
    ConfigurationResult,
    DEFAULT_STORY_PROVIDER,
    ProgressCallback,
    ProviderCapabilities,
    StoryCostEstimate,
    StoryGenerationRequest,
    StoryGenerationResult,
)


class ManualPromptProviderAdapter:
    def __init__(self, provider: Any) -> None:
        self.provider = provider

    @property
    def provider_id(self) -> str:
        return self.provider.provider_id

    @property
    def provider_name(self) -> str:
        return "Manual Prompt"

    @property
    def provider_version(self) -> str:
        return self.provider.provider_version

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(structured_outputs=False, reasoning_effort=False, temperature=False, streaming=False)

    def validate_configuration(self) -> ConfigurationResult:
        return ConfigurationResult(True, "Manual Prompt configured")

    def estimate_cost(self, request: StoryGenerationRequest) -> StoryCostEstimate:
        return StoryCostEstimate(model=request.model, estimated_cost_usd=0.0, message="Manual Prompt uses no API billing.")

    def generate_story(
        self,
        request: StoryGenerationRequest,
        cancellation_token: CancellationToken | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> StoryGenerationResult:
        return StoryGenerationResult(
            status="failed",
            provider=self.provider_id,
            provider_version=self.provider_version,
            model=request.model,
            error_code="manual_prompt_only",
            error_message="Manual Prompt Provider does not perform AI story generation.",
        )


class StoryProviderManager:
    def __init__(self, providers: list[StoryAIProvider | ManualPromptProviderAdapter] | None = None, default_provider: str = DEFAULT_STORY_PROVIDER) -> None:
        self.default_provider = default_provider
        self._providers: dict[str, StoryAIProvider | ManualPromptProviderAdapter] = {}
        for provider in providers or []:
            self.register(provider)

    def register(self, provider: StoryAIProvider | ManualPromptProviderAdapter) -> None:
        self._providers[provider.provider_id] = provider

    def provider_ids(self) -> list[str]:
        return sorted(self._providers)

    def get(self, provider_id: str | None = None):
        selected = provider_id or self.default_provider
        if selected not in self._providers:
            raise KeyError(f"Unknown story provider: {selected}")
        return self._providers[selected]

    def validate_configuration(self, provider_id: str | None = None) -> ConfigurationResult:
        return self.get(provider_id).validate_configuration()

    def capabilities(self, provider_id: str | None = None) -> ProviderCapabilities:
        return self.get(provider_id).capabilities()

    def estimate_cost(self, provider_id: str, request: StoryGenerationRequest) -> StoryCostEstimate:
        return self.get(provider_id).estimate_cost(request)
