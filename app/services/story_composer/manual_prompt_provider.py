from __future__ import annotations

import json
from datetime import datetime
from json import JSONDecodeError

from .models import (
    MANUAL_PROVIDER_ID,
    MANUAL_PROVIDER_VERSION,
    STORY_PROMPT_VERSION,
    STORY_SCHEMA_VERSION,
    Scene,
    Story,
    StoryPromptRequest,
    StoryPromptResult,
)
from .provider import StoryProvider
from .schema import STORY_JSON_SCHEMA
from .validator import StoryValidationError, StoryValidator


class ManualPromptProvider(StoryProvider):
    """Builds manual copy/paste prompts and parses returned Story JSON without network calls."""

    def __init__(self, validator: StoryValidator | None = None) -> None:
        self.validator = validator or StoryValidator()

    @property
    def provider_id(self) -> str:
        return MANUAL_PROVIDER_ID

    @property
    def provider_version(self) -> str:
        return MANUAL_PROVIDER_VERSION

    def build_prompt(self, request: StoryPromptRequest) -> StoryPromptResult:
        now = datetime.now().isoformat(timespec="seconds")
        scene_count = min(max(int(request.scene_count), 3), 20)
        duration = float(request.duration_seconds or 60.0)
        prompt = (
            "あなたはYouTube Shorts / TikTok向けの短尺動画構成作家です。\n"
            "次のテーマから、動画制作に使うStory JSONだけを作成してください。\n\n"
            f"Theme: {request.theme}\n"
            f"Genre: {request.genre}\n"
            f"Category: {request.category}\n"
            f"Target duration: {duration:.1f} seconds\n"
            f"Scene count: {scene_count}\n"
            f"Language: {request.language}\n\n"
            "Rules:\n"
            "- Output JSON only.\n"
            "- Do not use Markdown code fences.\n"
            "- Do not add explanations before or after JSON.\n"
            "- Follow the schema exactly.\n"
            "- scene_index must start at 1 and be sequential.\n"
            "- narration, subtitle, and image_prompt must not be empty.\n"
            "- duration must match start_time/end_time.\n"
            "- Avoid excessive clickbait.\n"
            "- Separate facts from speculation.\n"
            "- image_prompt should be visual, concrete, and suitable for vertical documentary video.\n\n"
            "Expected schema:\n"
            f"{json.dumps(STORY_JSON_SCHEMA, ensure_ascii=False, indent=2)}"
        )
        return StoryPromptResult(
            provider=self.provider_id,
            provider_version=self.provider_version,
            schema_version=STORY_SCHEMA_VERSION,
            story_prompt_version=STORY_PROMPT_VERSION,
            prompt=prompt,
            created_at=now,
        )

    def parse_response(self, raw_response: str, project_id: str = "") -> Story:
        self.validator.validate_raw_size(raw_response)
        text = self._strip_simple_code_fence(raw_response.strip())
        if not text:
            raise StoryValidationError("Story JSONが空です。")
        try:
            data = json.loads(text)
        except JSONDecodeError as exc:
            raise StoryValidationError(f"Story JSONの形式が正しくありません: {exc.msg}") from exc
        self.validator.validate_payload_shape(data)
        story = self._story_from_payload(data, project_id)
        story.validation = self.validator.validate(story)
        story.status = "invalid" if story.validation.has_errors else "valid"
        story.touch()
        return story

    def _strip_simple_code_fence(self, text: str) -> str:
        if text.startswith("```json") and text.endswith("```"):
            return text[7:-3].strip()
        if text.startswith("```") and text.endswith("```"):
            return text[3:-3].strip()
        return text

    def _story_from_payload(self, data: dict, project_id: str) -> Story:
        raw_scenes = data.get("scenes", [])
        scenes = [Scene.from_dict(item) for item in raw_scenes if isinstance(item, dict)] if isinstance(raw_scenes, list) else []
        story = Story(
            project_id=project_id,
            theme=str(data.get("theme") or ""),
            title=str(data.get("title") or ""),
            description=str(data.get("description") or ""),
            hook=str(data.get("hook") or ""),
            summary=str(data.get("summary") or ""),
            estimated_duration=float(data.get("estimated_duration", 60.0) or 60.0),
            provider=self.provider_id,
            provider_version=self.provider_version,
            schema_version=STORY_SCHEMA_VERSION,
            story_prompt_version=STORY_PROMPT_VERSION,
            language=str(data.get("language") or "ja"),
            status="json_imported",
            tags=[str(item).strip() for item in data.get("tags", []) if str(item).strip()] if isinstance(data.get("tags", []), list) else [],
            memo=str(data.get("memo") or ""),
            scenes=scenes,
            metadata=dict(data.get("metadata", {})) if isinstance(data.get("metadata"), dict) else {},
        )
        story.touch()
        return story
