from __future__ import annotations

import pytest

from services.story_composer.manual_prompt_provider import ManualPromptProvider
from services.story_provider import GeminiStoryProvider, MockStoryProvider, OpenAIStoryProvider, StoryGenerationRequest, StoryProviderManager
from services.story_provider.manager import ManualPromptProviderAdapter


def test_manager_registers_manual_mock_and_openai() -> None:
    manager = StoryProviderManager(
        [
            ManualPromptProviderAdapter(ManualPromptProvider()),
            GeminiStoryProvider(client_factory=lambda: object()),
            MockStoryProvider(),
            OpenAIStoryProvider(client_factory=lambda: object()),
        ],
        default_provider="gemini",
    )

    assert {"manual_prompt", "mock", "openai", "gemini"}.issubset(set(manager.provider_ids()))
    assert manager.capabilities("openai").structured_outputs is True
    assert manager.capabilities("gemini").free_tier_guard is True
    assert manager.capabilities("manual_prompt").structured_outputs is False
    assert manager.default_provider == "gemini"


def test_manager_rejects_unknown_provider() -> None:
    manager = StoryProviderManager([MockStoryProvider()])

    with pytest.raises(KeyError):
        manager.get("missing")


def test_manual_adapter_does_not_call_ai_generation() -> None:
    manager = StoryProviderManager([ManualPromptProviderAdapter(ManualPromptProvider())])
    result = manager.get("manual_prompt").generate_story(StoryGenerationRequest(project_id="p1", theme="space"))

    assert result.status == "failed"
    assert result.error_code == "manual_prompt_only"
