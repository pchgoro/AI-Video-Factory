from __future__ import annotations

import pytest

from services.story_composer import Scene, Story, StoryValidationError, StoryValidator


def _valid_story() -> Story:
    return Story(
        title="ブラックホールとは？",
        description="ブラックホールを短く説明する",
        hook="ブラックホールは本当に穴なのでしょうか。",
        summary="重力が強すぎる天体の解説",
        estimated_duration=18.0,
        tags=["宇宙"],
        scenes=[
            Scene(1, 0.0, 6.0, 6.0, "hook", "ナレーション1", "字幕1", "prompt 1"),
            Scene(2, 6.0, 12.0, 6.0, "explanation", "ナレーション2", "字幕2", "prompt 2"),
            Scene(3, 12.0, 18.0, 6.0, "ending", "ナレーション3", "字幕3", "prompt 3"),
        ],
    )


def test_valid_story_has_no_errors() -> None:
    story = _valid_story()

    result = StoryValidator().validate(story)

    assert result.status == "valid"
    assert result.errors == []


def test_validation_errors_block_export_conditions() -> None:
    story = Story(
        title="",
        estimated_duration=10.0,
        scenes=[
            Scene(1, -1.0, 0.0, 1.0, "hook", "", "", ""),
            Scene(1, 0.0, 0.0, 0.0, "ending", "n", "s", "p"),
        ],
    )

    result = StoryValidator().validate(story)

    fields = {issue.field for issue in result.errors}
    assert "title" in fields
    assert "scene_index" in fields
    assert "time" in fields
    assert "end_time" in fields
    assert "narration" in fields
    assert "image_prompt" in fields


def test_validation_warnings_are_separate_from_errors() -> None:
    story = _valid_story()
    story.description = ""
    story.tags = []
    story.scenes[1].subtitle = ""
    story.estimated_duration = 24.0

    result = StoryValidator().validate(story)

    assert not result.has_errors
    assert result.warnings
    assert {issue.field for issue in result.warnings} >= {"description", "tags", "subtitle", "estimated_duration"}


def test_duration_mismatch_uses_tolerance() -> None:
    story = _valid_story()
    story.scenes[0].duration = 6.05

    result = StoryValidator().validate(story)

    assert not any(issue.field == "duration" for issue in result.warnings)


def test_payload_limits_reject_arrays_and_oversized_metadata() -> None:
    validator = StoryValidator()

    with pytest.raises(StoryValidationError):
        validator.validate_payload_shape([])

    with pytest.raises(StoryValidationError):
        validator.validate_payload_shape({"metadata": {"a": {"b": {"c": {"d": {"e": "too deep"}}}}}})
