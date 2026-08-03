from __future__ import annotations

import json

import pytest

from services.story_composer import ManualPromptProvider, StoryPromptRequest, StoryValidationError


def _story_payload() -> dict:
    return {
        "title": "宇宙はひとつではない？",
        "description": "多次元宇宙の解説",
        "hook": "もし宇宙が無数にあるなら？",
        "summary": "多次元宇宙の考え方を説明する",
        "estimated_duration": 18.0,
        "tags": ["宇宙", "多次元宇宙"],
        "memo": "日本語を保持",
        "scenes": [
            {
                "scene_index": 1,
                "start_time": 0.0,
                "end_time": 6.0,
                "duration": 6.0,
                "scene_type": "hook",
                "narration": "もし宇宙がひとつではないとしたら？",
                "subtitle": "宇宙はひとつではない？",
                "image_prompt": "multiple universes in deep space",
                "notes": "",
            },
            {
                "scene_index": 2,
                "start_time": 6.0,
                "end_time": 12.0,
                "duration": 6.0,
                "scene_type": "explanation",
                "narration": "この考えは多次元宇宙と呼ばれます。",
                "subtitle": "多次元宇宙という考え",
                "image_prompt": "cosmic bubbles documentary style",
                "notes": "",
            },
            {
                "scene_index": 3,
                "start_time": 12.0,
                "end_time": 18.0,
                "duration": 6.0,
                "scene_type": "ending",
                "narration": "まだ証明されていない大きな謎です。",
                "subtitle": "まだ証明されていない謎",
                "image_prompt": "wide final shot of deep space",
                "notes": "",
            },
        ],
    }


def test_build_prompt_requests_json_only_and_versions() -> None:
    provider = ManualPromptProvider()

    result = provider.build_prompt(StoryPromptRequest(project_id="p1", theme="多次元宇宙", scene_count=5))

    assert result.provider == "manual_prompt"
    assert result.provider_version == "1.0"
    assert result.schema_version == "1.0"
    assert "Output JSON only" in result.prompt
    assert "Do not use Markdown code fences" in result.prompt
    assert "OpenAI" not in result.prompt
    assert "Claude" not in result.prompt


def test_parse_response_accepts_plain_and_simple_fenced_json() -> None:
    provider = ManualPromptProvider()
    raw = json.dumps(_story_payload(), ensure_ascii=False)

    story = provider.parse_response(f"```json\n{raw}\n```", project_id="project-a")

    assert story.project_id == "project-a"
    assert story.title == "宇宙はひとつではない？"
    assert story.memo == "日本語を保持"
    assert story.status == "valid"


def test_parse_response_rejects_broken_json_and_trailing_comma() -> None:
    provider = ManualPromptProvider()

    with pytest.raises(StoryValidationError):
        provider.parse_response('{"title": "bad",}', project_id="p")


def test_parse_response_rejects_json_array() -> None:
    provider = ManualPromptProvider()

    with pytest.raises(StoryValidationError):
        provider.parse_response("[]", project_id="p")
