from __future__ import annotations

from services.story_provider import StoryGenerationRequest, StoryGenerationState, StoryProviderMetrics
from services.story_provider.cost_estimator import StoryCostEstimator


def test_story_generation_request_defaults_and_validation() -> None:
    request = StoryGenerationRequest(project_id="p1", theme="black hole")

    request.validate()

    assert request.model == "gemini-3.5-flash-lite"
    assert request.reasoning_effort == "low"
    assert "theme_hash" in request.safe_snapshot("hash")
    assert "provider_options" not in request.safe_snapshot("hash")


def test_story_generation_state_serializes_without_secrets() -> None:
    state = StoryGenerationState(
        project_id="p1",
        status="running",
        provider="gemini",
        free_tier_only=True,
        model_free_tier_status="available",
        project_tier_status="user_confirmed_free",
        billing_status="user_confirmed_disabled",
        charge_risk="low",
    )
    state.metrics = StoryProviderMetrics(input_tokens=10, output_tokens=20, response_id="resp_123")

    data = state.to_dict()
    reloaded = StoryGenerationState.from_dict(data)

    assert "api_key" not in str(data).lower()
    assert "GEMINI_API_KEY" not in str(data)
    assert "prompt" not in data
    assert reloaded.status == "interrupted"
    assert reloaded.metrics.input_tokens == 10
    assert reloaded.provider == "gemini"
    assert reloaded.free_tier_only is True


def test_cost_estimator_handles_presets_and_unknown_models() -> None:
    estimator = StoryCostEstimator()
    request = StoryGenerationRequest(project_id="p1", theme="space", model="gpt-5.6-luna")
    known = estimator.estimate_pre_request(request)
    unknown = estimator.estimate_pre_request(StoryGenerationRequest(project_id="p1", theme="space", model="custom-model"))

    assert known.estimated_cost_usd is not None
    assert known.pricing_snapshot["pricing_table_version"]
    assert unknown.estimated_cost_usd is None
    assert "なし" in unknown.message or "unavailable" in unknown.message
