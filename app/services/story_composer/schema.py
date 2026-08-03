from __future__ import annotations

from .models import SCENE_TYPES, STORY_SCHEMA_VERSION


STORY_JSON_SCHEMA: dict[str, object] = {
    "schema_version": STORY_SCHEMA_VERSION,
    "type": "object",
    "required": ["title", "hook", "summary", "estimated_duration", "scenes"],
    "properties": {
        "title": "string",
        "description": "string",
        "hook": "string",
        "summary": "string",
        "estimated_duration": "number",
        "tags": ["string"],
        "memo": "string",
        "scenes": [
            {
                "scene_index": "integer, starts at 1",
                "start_time": "number seconds",
                "end_time": "number seconds",
                "duration": "number seconds",
                "scene_type": sorted(SCENE_TYPES),
                "narration": "string",
                "subtitle": "string",
                "image_prompt": "string",
                "notes": "string",
            }
        ],
    },
}


def story_structured_output_schema(max_scenes: int = 10) -> dict[str, object]:
    """JSON Schema used by AI Story providers for strict Structured Outputs."""
    max_scenes = max(3, min(20, int(max_scenes or 10)))
    string_2k = {"type": "string", "maxLength": 2000}
    string_4k = {"type": "string", "maxLength": 4000}
    scene_schema: dict[str, object] = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "scene_index",
            "start_time",
            "end_time",
            "duration",
            "scene_type",
            "narration",
            "subtitle",
            "image_prompt",
            "notes",
        ],
        "properties": {
            "scene_index": {"type": "integer", "minimum": 1, "maximum": 20},
            "start_time": {"type": "number", "minimum": 0},
            "end_time": {"type": "number", "minimum": 0},
            "duration": {"type": "number", "minimum": 0.1, "maximum": 600},
            "scene_type": {"type": "string", "enum": sorted(SCENE_TYPES)},
            "narration": string_2k,
            "subtitle": {"type": "string", "maxLength": 500},
            "image_prompt": string_2k,
            "notes": {"type": "string", "maxLength": 1000},
        },
    }
    return {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "schema_version",
            "story_prompt_version",
            "theme",
            "title",
            "description",
            "hook",
            "summary",
            "estimated_duration",
            "language",
            "tags",
            "memo",
            "scenes",
            "metadata",
        ],
        "properties": {
            "schema_version": {"type": "string", "const": STORY_SCHEMA_VERSION},
            "story_prompt_version": {"type": "string", "maxLength": 20},
            "theme": {"type": "string", "maxLength": 500},
            "title": {"type": "string", "maxLength": 200},
            "description": string_2k,
            "hook": {"type": "string", "maxLength": 500},
            "summary": string_4k,
            "estimated_duration": {"type": "number", "minimum": 5, "maximum": 600},
            "language": {"type": "string", "maxLength": 20},
            "tags": {"type": "array", "maxItems": 20, "items": {"type": "string", "maxLength": 80}},
            "memo": string_2k,
            "scenes": {"type": "array", "minItems": 3, "maxItems": max_scenes, "items": scene_schema},
            "metadata": {
                "type": "object",
                "additionalProperties": {"type": ["string", "number", "boolean", "null"]},
                "maxProperties": 20,
            },
        },
    }
