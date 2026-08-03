from __future__ import annotations

import json
from types import SimpleNamespace

from services.story_provider import CancellationToken, StoryGenerationRequest
from services.story_provider.openai_provider import OpenAIStoryProvider


def _story_json() -> str:
    return json.dumps(
        {
            "story_id": "s1",
            "project_id": "p1",
            "theme": "space",
            "title": "Space mystery",
            "description": "Short description",
            "hook": "What if space is stranger than expected?",
            "summary": "A concise story.",
            "estimated_duration": 18.0,
            "provider": "openai",
            "provider_version": "1.0",
            "schema_version": "1.0",
            "story_prompt_version": "1.0",
            "language": "ja",
            "status": "draft",
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
    )


class FakeResponses:
    def __init__(self, response=None, failures=None) -> None:
        self.response = response
        self.failures = list(failures or [])
        self.calls: list[dict] = []

    def create(self, **payload):
        self.calls.append(payload)
        if self.failures:
            raise self.failures.pop(0)
        return self.response


class FakeClient:
    def __init__(self, responses: FakeResponses) -> None:
        self.responses = responses


def _provider(fake_responses: FakeResponses) -> OpenAIStoryProvider:
    provider = OpenAIStoryProvider(client_factory=lambda: FakeClient(fake_responses), sleep_func=lambda _delay: None)
    provider._import_openai = lambda: object()  # type: ignore[method-assign]
    return provider


def _response(status: str = "completed"):
    return SimpleNamespace(
        id="resp_123",
        status=status,
        output_text=_story_json(),
        output=[],
        usage=SimpleNamespace(
            input_tokens=100,
            output_tokens=200,
            total_tokens=300,
            input_tokens_details=SimpleNamespace(cached_tokens=10),
            output_tokens_details=SimpleNamespace(reasoning_tokens=20),
        ),
    )


def test_openai_provider_uses_responses_api_structured_outputs(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    responses = FakeResponses(_response())
    provider = _provider(responses)

    result = provider.generate_story(StoryGenerationRequest(project_id="p1", theme="space", model="gpt-5.6-luna"))

    assert result.status == "completed"
    assert result.story is not None
    assert responses.calls
    payload = responses.calls[0]
    assert payload["model"] == "gpt-5.6-luna"
    assert payload["text"]["format"]["type"] == "json_schema"
    assert payload["text"]["format"]["strict"] is True
    assert "temperature" not in payload
    assert "chat.completions" not in str(payload).lower()
    assert result.metrics.input_tokens == 100
    assert result.metrics.response_id == "resp_123"


def test_openai_provider_missing_api_key_makes_no_request(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    responses = FakeResponses(_response())
    provider = _provider(responses)

    result = provider.generate_story(StoryGenerationRequest(project_id="p1", theme="space"))

    assert result.status == "failed"
    assert result.error_code == "missing_api_key"
    assert responses.calls == []


def test_openai_provider_refusal_is_not_saved_as_story(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    refusal = SimpleNamespace(type="refusal")
    response = SimpleNamespace(id="resp_refusal", status="completed", output=[SimpleNamespace(content=[refusal])], output_text="", usage=None)

    result = _provider(FakeResponses(response)).generate_story(StoryGenerationRequest(project_id="p1", theme="space"))

    assert result.status == "failed"
    assert result.story is None
    assert result.error_code == "provider_refusal"


def test_openai_provider_retries_retryable_http_error(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    error = RuntimeError("temporary")
    error.status_code = 500  # type: ignore[attr-defined]
    responses = FakeResponses(_response(), failures=[error])

    result = _provider(responses).generate_story(StoryGenerationRequest(project_id="p1", theme="space", retry_count=1))

    assert result.status == "completed"
    assert result.retry_count == 1
    assert len(responses.calls) == 2


def test_openai_provider_cancellation_stops_before_request(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    responses = FakeResponses(_response())
    token = CancellationToken()
    token.cancel()

    result = _provider(responses).generate_story(StoryGenerationRequest(project_id="p1", theme="space"), token)

    assert result.status == "cancelled"
    assert responses.calls == []
