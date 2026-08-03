from __future__ import annotations

from services.story_composer.models import Scene, Story
from services.story_composer.validator import StoryValidator

from .base import StoryAIProvider
from .cost_estimator import StoryCostEstimator
from .models import (
    CancellationToken,
    ConfigurationResult,
    ProgressCallback,
    ProviderCapabilities,
    StoryCostEstimate,
    StoryGenerationRequest,
    StoryGenerationResult,
    StoryProviderMetrics,
)


class MockStoryProvider(StoryAIProvider):
    @property
    def provider_id(self) -> str:
        return "mock"

    @property
    def provider_name(self) -> str:
        return "Mock Story Provider"

    @property
    def provider_version(self) -> str:
        return "1.0"

    def capabilities(self) -> ProviderCapabilities:
        return ProviderCapabilities(structured_outputs=True, reasoning_effort=False, temperature=False, streaming=False)

    def validate_configuration(self) -> ConfigurationResult:
        return ConfigurationResult(True, "Mock provider configured")

    def estimate_cost(self, request: StoryGenerationRequest) -> StoryCostEstimate:
        return StoryCostEstimator().estimate_pre_request(request)

    def generate_story(
        self,
        request: StoryGenerationRequest,
        cancellation_token: CancellationToken | None = None,
        progress_callback: ProgressCallback | None = None,
    ) -> StoryGenerationResult:
        if cancellation_token and cancellation_token.cancel_requested:
            return StoryGenerationResult(status="cancelled", provider=self.provider_id, provider_version=self.provider_version, model=request.model)
        if progress_callback:
            progress_callback("Mock Story生成中", 50)
        scene_count = max(request.min_scenes, min(request.max_scenes, 3))
        duration = float(request.target_duration_seconds) / scene_count
        scenes = []
        for index in range(1, scene_count + 1):
            start = round((index - 1) * duration, 1)
            end = round(index * duration, 1)
            scenes.append(
                Scene(
                    scene_index=index,
                    start_time=start,
                    end_time=end,
                    duration=round(end - start, 1),
                    scene_type="hook" if index == 1 else "ending" if index == scene_count else "explanation",
                    narration=f"{request.theme}について、重要なポイントを短く解説します。",
                    subtitle=f"{request.theme}のポイント",
                    image_prompt=f"vertical cinematic documentary scene about {request.theme}, scene {index}, no text",
                    notes="mock",
                )
            )
        story = Story(
            project_id=request.project_id,
            theme=request.theme,
            title=f"{request.theme}とは？",
            description=f"{request.theme}をショート動画向けに解説する構成です。",
            hook=f"{request.theme}を知ると、見方が変わります。",
            summary=f"{request.theme}の概要を短く説明します。",
            estimated_duration=request.target_duration_seconds,
            provider=self.provider_id,
            provider_version=self.provider_version,
            language=request.language,
            status="valid",
            tags=[request.theme],
            scenes=scenes,
        )
        story.validation = StoryValidator().validate(story)
        story.touch()
        return StoryGenerationResult(
            story=story,
            provider=self.provider_id,
            provider_version=self.provider_version,
            model=request.model,
            metrics=StoryProviderMetrics(input_tokens=0, output_tokens=0, total_tokens=0, estimated_cost_usd=0.0),
        )
