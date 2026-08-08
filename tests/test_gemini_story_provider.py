from __future__ import annotations

import json
from types import SimpleNamespace

from services.story_provider import CancellationToken, StoryGenerationRequest
from services.story_provider.gemini_free_tier_policy import api_key_fingerprint
from services.story_provider.gemini_provider import GeminiStoryProvider, GeminiUsageStore
from services.story_provider.gemini_model_catalog import default_gemini_model, gemini_model_catalog, validate_gemini_model_id


def _story_data() -> dict:
    return {
        "schema_version": "1.0",
        "story_prompt_version": "1.0",
        "theme": "space",
        "title": "Space mystery",
        "description": "Short description",
        "hook": "A strong hook",
        "summary": "A concise summary",
        "estimated_duration": 18.0,
        "language": "ja",
        "tags": ["space"],
        "memo": "",
        "metadata": {},
        "scenes": [
            {
                "scene_index": 1,
                "start_time": 0,
                "end_time": 6,
                "duration": 6,
                "scene_type": "hook",
                "narration": "Narration one",
                "subtitle": "Subtitle one",
                "image_prompt": "cinematic space scene one",
                "notes": "",
            },
            {
                "scene_index": 2,
                "start_time": 6,
                "end_time": 12,
                "duration": 6,
                "scene_type": "explanation",
                "narration": "Narration two",
                "subtitle": "Subtitle two",
                "image_prompt": "cinematic space scene two",
                "notes": "",
            },
            {
                "scene_index": 3,
                "start_time": 12,
                "end_time": 18,
                "duration": 6,
                "scene_type": "ending",
                "narration": "Narration three",
                "subtitle": "Subtitle three",
                "image_prompt": "cinematic space scene three",
                "notes": "",
            },
        ],
    }


class FakeModels:
    def __init__(self, response=None, failures=None) -> None:
        self.response = response
        self.failures = list(failures or [])
        self.calls: list[dict] = []

    def generate_content(self, **payload):
        self.calls.append(payload)
        if self.failures:
            raise self.failures.pop(0)
        return self.response


class FakeClient:
    def __init__(self, models: FakeModels) -> None:
        self.models = models


def _response(**kwargs):
    return SimpleNamespace(
        parsed=kwargs.get("parsed", _story_data()),
        text=kwargs.get("text", ""),
        candidates=kwargs.get("candidates", [SimpleNamespace(finish_reason="STOP")]),
        prompt_feedback=kwargs.get("prompt_feedback", None),
        usage_metadata=SimpleNamespace(
            prompt_token_count=101,
            candidates_token_count=202,
            thoughts_token_count=12,
            cached_content_token_count=4,
            total_token_count=315,
        ),
        response_id="gemini-response-1",
        model_version="gemini-test-version",
    )


def _request(**overrides) -> StoryGenerationRequest:
    options = {
        "free_tier_only": True,
        "project_free_tier_confirmed": True,
        "billing_disabled_confirmed": True,
        "confirmation_key_fingerprint": api_key_fingerprint("test-gemini-key"),
        "local_daily_request_cap": 10,
        "temperature": 0.7,
    }
    options.update(overrides.pop("provider_options", {}))
    return StoryGenerationRequest(
        project_id="p1",
        theme="space",
        model=overrides.pop("model", "gemini-3.5-flash-lite"),
        provider_options=options,
        **overrides,
    )


def _provider(fake_models: FakeModels, usage_store=None) -> GeminiStoryProvider:
    provider = GeminiStoryProvider(client_factory=lambda: FakeClient(fake_models), sleep_func=lambda _delay: None, usage_store=usage_store or GeminiUsageStore())
    provider._import_genai = lambda: (object(), object())  # type: ignore[method-assign]
    return provider


def test_model_catalog_has_confirmed_default_and_flash_models() -> None:
    catalog = gemini_model_catalog()

    assert default_gemini_model() == "gemini-3.5-flash-lite"
    assert {"gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash"}.issubset(catalog)
    assert catalog["gemini-3.5-flash-lite"].structured_outputs is True
    assert catalog["gemini-3.5-flash-lite"].free_tier_status == "available"
    assert catalog["gemini-3.5-flash-lite"].metadata_checked_at


def test_custom_model_is_rejected_in_free_tier_catalog_validation() -> None:
    try:
        validate_gemini_model_id("custom-model")
    except ValueError as exc:
        assert "catalog" in str(exc)
    else:
        raise AssertionError("custom model should be rejected")


def test_gemini_provider_uses_google_genai_structured_outputs(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    fake_models = FakeModels(_response())

    result = _provider(fake_models).generate_story(_request())

    assert result.status == "completed"
    assert result.story is not None
    payload = fake_models.calls[0]
    assert payload["model"] == "gemini-3.5-flash-lite"
    assert payload["config"]["response_mime_type"] == "application/json"
    assert "response_json_schema" in payload["config"]
    assert "response_format" not in payload["config"]
    assert "temperature" in payload["config"]
    assert result.metrics.input_tokens == 101
    assert result.metrics.thoughts_tokens == 12
    assert result.metrics.estimated_cost_usd is None
    assert result.metrics.charge_expected is False


def test_missing_api_key_makes_no_request(monkeypatch) -> None:
    monkeypatch.setattr("services.story_provider.gemini_provider.load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    fake_models = FakeModels(_response())

    result = _provider(fake_models).generate_story(_request())

    assert result.status == "failed"
    assert result.error_code == "missing_api_key"
    assert fake_models.calls == []


def test_project_confirmation_is_required_before_request(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    fake_models = FakeModels(_response())

    result = _provider(fake_models).generate_story(_request(provider_options={"project_free_tier_confirmed": False}))

    assert result.status == "failed"
    assert result.error_code == "gemini_project_tier_unconfirmed"
    assert fake_models.calls == []


def test_safety_block_and_empty_response_are_not_saved_as_story(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    safety = _response(candidates=[SimpleNamespace(finish_reason="SAFETY")])
    empty = _response(parsed=None, text="", candidates=[SimpleNamespace(finish_reason="STOP")])

    assert _provider(FakeModels(safety)).generate_story(_request()).error_code == "gemini_safety_block"
    result = _provider(FakeModels(empty)).generate_story(_request())
    assert result.status == "failed"
    assert result.story is None
    assert result.error_code == "gemini_empty_response"


def test_retryable_error_retries_once_and_quota_does_not_retry(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    temporary = RuntimeError("temporary")
    temporary.code = 503  # type: ignore[attr-defined]
    fake_models = FakeModels(_response(), failures=[temporary])

    result = _provider(fake_models).generate_story(_request(retry_count=1))

    assert result.status == "completed"
    assert result.retry_count == 1
    assert len(fake_models.calls) == 2

    quota = RuntimeError("quota exhausted")
    quota.code = 429  # type: ignore[attr-defined]
    quota_models = FakeModels(_response(), failures=[quota])
    quota_result = _provider(quota_models).generate_story(_request(retry_count=2))
    assert quota_result.error_code == "gemini_quota_exhausted"
    assert len(quota_models.calls) == 1


def test_cancellation_stops_before_request(monkeypatch) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    fake_models = FakeModels(_response())
    token = CancellationToken()
    token.cancel()

    result = _provider(fake_models).generate_story(_request(), token)

    assert result.status == "cancelled"
    assert fake_models.calls == []


def test_local_usage_cap_blocks_request(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("GEMINI_API_KEY", "test-gemini-key")
    usage = GeminiUsageStore(tmp_path / "usage.json")
    usage.record_attempt()
    fake_models = FakeModels(_response())

    result = _provider(fake_models, usage).generate_story(_request(provider_options={"local_daily_request_cap": 1}))

    assert result.error_code == "gemini_local_daily_cap_reached"
    assert fake_models.calls == []
