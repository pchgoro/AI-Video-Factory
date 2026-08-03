from __future__ import annotations

from typing import Any

from .models import SCENE_TYPES, Scene, Story, ValidationResult


MIN_SCENES = 3
MAX_SCENES = 20
MAX_JSON_BYTES = 256 * 1024
MAX_STRING_LENGTH = 6000
MAX_METADATA_DEPTH = 4
SCENE_TIME_TOLERANCE_SECONDS = 0.1
TOTAL_DURATION_WARNING_SECONDS = 5.0
TOTAL_DURATION_ERROR_SECONDS = 20.0


class StoryValidationError(ValueError):
    """Raised when a pasted Story JSON cannot be parsed safely."""


class StoryValidator:
    def validate_raw_size(self, raw: str) -> None:
        if len(raw.encode("utf-8")) > MAX_JSON_BYTES:
            raise StoryValidationError("Story JSONが大きすぎます。")

    def validate_payload_shape(self, data: Any) -> None:
        if not isinstance(data, dict):
            raise StoryValidationError("Story JSONはオブジェクト形式で入力してください。")
        scenes = data.get("scenes", [])
        if scenes is not None and not isinstance(scenes, list):
            raise StoryValidationError("scenesは配列で入力してください。")
        if isinstance(scenes, list) and len(scenes) > MAX_SCENES:
            raise StoryValidationError(f"scene数が上限{MAX_SCENES}を超えています。")
        self._validate_string_lengths(data)
        self._validate_metadata(data.get("metadata", {}), 0)

    def validate(self, story: Story) -> ValidationResult:
        result = ValidationResult()
        scene_indices: set[int] = set()
        ordered_indices: list[int] = []
        total_duration = 0.0

        if not story.title.strip():
            result.add("error", "titleが空です。", "title")
        if not story.description.strip():
            result.add("warning", "descriptionが空です。", "description")
        if not story.tags:
            result.add("warning", "tagsが空です。", "tags")
        if not story.scenes:
            result.add("error", "sceneがありません。", "scenes")
            story.validation = result
            return result
        if len(story.scenes) < MIN_SCENES or len(story.scenes) > MAX_SCENES:
            result.add("warning", f"scene数は推奨範囲{MIN_SCENES}〜{MAX_SCENES}外です。", "scenes")

        has_hook = False
        has_ending = False
        for scene in story.scenes:
            scene.validation = ValidationResult()
            ordered_indices.append(scene.scene_index)
            if scene.scene_index in scene_indices:
                self._add_scene_issue(result, scene, "error", "scene_indexが重複しています。", "scene_index")
            scene_indices.add(scene.scene_index)
            if scene.scene_index <= 0:
                self._add_scene_issue(result, scene, "error", "scene_indexは1以上にしてください。", "scene_index")
            if scene.scene_type not in SCENE_TYPES:
                scene.scene_type = "custom"
                self._add_scene_issue(result, scene, "warning", "未知のscene_typeはcustomとして扱います。", "scene_type")
            has_hook = has_hook or scene.scene_type == "hook"
            has_ending = has_ending or scene.scene_type == "ending"
            self._validate_scene_time(result, scene)
            if not scene.narration.strip():
                self._add_scene_issue(result, scene, "error", "narrationが空です。", "narration")
            if not scene.image_prompt.strip():
                self._add_scene_issue(result, scene, "error", "image_promptが空です。", "image_prompt")
            if not scene.subtitle.strip():
                self._add_scene_issue(result, scene, "warning", "subtitleが空です。", "subtitle")
            total_duration += max(0.0, scene.duration)

        if ordered_indices != sorted(ordered_indices):
            result.add("error", "scene_indexが順番通りではありません。", "scenes")
        if not has_hook:
            result.add("warning", "hook sceneがありません。", "scenes")
        if not has_ending:
            result.add("warning", "ending sceneがありません。", "scenes")

        diff = abs(total_duration - float(story.estimated_duration or 0.0))
        if diff > TOTAL_DURATION_ERROR_SECONDS:
            result.add("error", "scene合計時間とestimated_durationの差が大きすぎます。", "estimated_duration")
        elif diff > TOTAL_DURATION_WARNING_SECONDS:
            result.add("warning", "scene合計時間とestimated_durationに差があります。", "estimated_duration")
        result.status = "invalid" if result.errors else "valid"
        story.validation = result
        return result

    def _validate_scene_time(self, result: ValidationResult, scene: Scene) -> None:
        if scene.start_time < 0 or scene.end_time < 0 or scene.duration < 0:
            self._add_scene_issue(result, scene, "error", "負の時間は使用できません。", "time")
        if scene.end_time <= scene.start_time:
            self._add_scene_issue(result, scene, "error", "end_timeはstart_timeより後にしてください。", "end_time")
        expected = scene.end_time - scene.start_time
        if abs(expected - scene.duration) > SCENE_TIME_TOLERANCE_SECONDS:
            self._add_scene_issue(result, scene, "warning", "durationとend-startに差があります。", "duration")

    def _add_scene_issue(self, result: ValidationResult, scene: Scene, severity: str, message: str, field: str) -> None:
        result.add(severity, message, field, scene.scene_index)
        scene.validation.add(severity, message, field, scene.scene_index)

    def _validate_string_lengths(self, value: Any) -> None:
        if isinstance(value, str):
            if len(value) > MAX_STRING_LENGTH:
                raise StoryValidationError("Story JSON内の文字列が長すぎます。")
            return
        if isinstance(value, list):
            for item in value:
                self._validate_string_lengths(item)
            return
        if isinstance(value, dict):
            for item in value.values():
                self._validate_string_lengths(item)

    def _validate_metadata(self, value: Any, depth: int) -> None:
        if depth > MAX_METADATA_DEPTH:
            raise StoryValidationError("metadataの階層が深すぎます。")
        if isinstance(value, dict):
            if len(value) > 50:
                raise StoryValidationError("metadataの項目数が多すぎます。")
            for item in value.values():
                self._validate_metadata(item, depth + 1)
        elif isinstance(value, list):
            if len(value) > 100:
                raise StoryValidationError("metadataの配列が大きすぎます。")
            for item in value:
                self._validate_metadata(item, depth + 1)
