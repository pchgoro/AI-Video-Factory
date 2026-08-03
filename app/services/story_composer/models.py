from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import uuid4


STORY_SCHEMA_VERSION = "1.0"
STORY_PROMPT_VERSION = "1.0"
MANUAL_PROVIDER_ID = "manual_prompt"
MANUAL_PROVIDER_VERSION = "1.0"

STORY_STATUSES = {
    "draft",
    "prompt_ready",
    "json_imported",
    "validating",
    "valid",
    "invalid",
    "exported_to_factory",
    "failed",
}

SCENE_TYPES = {
    "hook",
    "introduction",
    "explanation",
    "comparison",
    "fact",
    "transition",
    "climax",
    "ending",
    "custom",
}


@dataclass
class ValidationIssue:
    severity: str
    message: str
    field: str = ""
    scene_index: int | None = None

    def to_dict(self) -> dict[str, object]:
        data: dict[str, object] = {"severity": self.severity, "message": self.message}
        if self.field:
            data["field"] = self.field
        if self.scene_index is not None:
            data["scene_index"] = self.scene_index
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationIssue":
        return cls(
            severity=str(data.get("severity") or "info"),
            message=str(data.get("message") or ""),
            field=str(data.get("field") or ""),
            scene_index=data.get("scene_index") if isinstance(data.get("scene_index"), int) else None,
        )


@dataclass
class ValidationResult:
    status: str = "valid"
    errors: list[ValidationIssue] = field(default_factory=list)
    warnings: list[ValidationIssue] = field(default_factory=list)
    infos: list[ValidationIssue] = field(default_factory=list)

    @property
    def has_errors(self) -> bool:
        return bool(self.errors)

    def add(self, severity: str, message: str, field: str = "", scene_index: int | None = None) -> None:
        issue = ValidationIssue(severity, message, field, scene_index)
        if severity == "error":
            self.errors.append(issue)
        elif severity == "warning":
            self.warnings.append(issue)
        else:
            self.infos.append(issue)
        self.status = "invalid" if self.errors else "valid"

    def to_dict(self) -> dict[str, object]:
        return {
            "status": self.status,
            "errors": [item.to_dict() for item in self.errors],
            "warnings": [item.to_dict() for item in self.warnings],
            "infos": [item.to_dict() for item in self.infos],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ValidationResult":
        result = cls(status=str(data.get("status") or "valid"))
        result.errors = [ValidationIssue.from_dict(item) for item in data.get("errors", []) if isinstance(item, dict)]
        result.warnings = [ValidationIssue.from_dict(item) for item in data.get("warnings", []) if isinstance(item, dict)]
        result.infos = [ValidationIssue.from_dict(item) for item in data.get("infos", []) if isinstance(item, dict)]
        result.status = "invalid" if result.errors else str(data.get("status") or "valid")
        return result


@dataclass
class Scene:
    scene_index: int
    start_time: float
    end_time: float
    duration: float
    scene_type: str = "custom"
    narration: str = ""
    subtitle: str = ""
    image_prompt: str = ""
    notes: str = ""
    validation: ValidationResult = field(default_factory=ValidationResult)

    def to_dict(self) -> dict[str, object]:
        return {
            "scene_index": self.scene_index,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration": self.duration,
            "scene_type": self.scene_type,
            "narration": self.narration,
            "subtitle": self.subtitle,
            "image_prompt": self.image_prompt,
            "notes": self.notes,
            "validation": self.validation.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Scene":
        scene_type = str(data.get("scene_type") or "custom")
        if scene_type not in SCENE_TYPES:
            scene_type = "custom"
        return cls(
            scene_index=int(data.get("scene_index", 0) or 0),
            start_time=float(data.get("start_time", 0.0) or 0.0),
            end_time=float(data.get("end_time", 0.0) or 0.0),
            duration=float(data.get("duration", 0.0) or 0.0),
            scene_type=scene_type,
            narration=str(data.get("narration") or ""),
            subtitle=str(data.get("subtitle") or ""),
            image_prompt=str(data.get("image_prompt") or ""),
            notes=str(data.get("notes") or ""),
            validation=ValidationResult.from_dict(data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}),
        )


@dataclass
class Story:
    story_id: str = field(default_factory=lambda: uuid4().hex)
    project_id: str = ""
    theme: str = ""
    title: str = ""
    description: str = ""
    hook: str = ""
    summary: str = ""
    estimated_duration: float = 60.0
    provider: str = MANUAL_PROVIDER_ID
    provider_version: str = MANUAL_PROVIDER_VERSION
    schema_version: str = STORY_SCHEMA_VERSION
    story_prompt_version: str = STORY_PROMPT_VERSION
    language: str = "ja"
    status: str = "draft"
    created_at: str = ""
    updated_at: str = ""
    tags: list[str] = field(default_factory=list)
    memo: str = ""
    scenes: list[Scene] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    validation: ValidationResult = field(default_factory=ValidationResult)

    def touch(self) -> None:
        now = datetime.now().isoformat(timespec="seconds")
        if not self.created_at:
            self.created_at = now
        self.updated_at = now

    def to_dict(self) -> dict[str, object]:
        return {
            "story_id": self.story_id,
            "project_id": self.project_id,
            "theme": self.theme,
            "title": self.title,
            "description": self.description,
            "hook": self.hook,
            "summary": self.summary,
            "estimated_duration": self.estimated_duration,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "schema_version": self.schema_version,
            "story_prompt_version": self.story_prompt_version,
            "language": self.language,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "tags": self.tags,
            "memo": self.memo,
            "scenes": [scene.to_dict() for scene in self.scenes],
            "metadata": self.metadata,
            "validation": self.validation.to_dict(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Story":
        raw_scenes = data.get("scenes", [])
        scenes = [Scene.from_dict(item) for item in raw_scenes if isinstance(item, dict)] if isinstance(raw_scenes, list) else []
        status = str(data.get("status") or "draft")
        if status not in STORY_STATUSES:
            status = "draft"
        tags = data.get("tags", [])
        metadata = data.get("metadata", {})
        return cls(
            story_id=str(data.get("story_id") or uuid4().hex),
            project_id=str(data.get("project_id") or ""),
            theme=str(data.get("theme") or ""),
            title=str(data.get("title") or ""),
            description=str(data.get("description") or ""),
            hook=str(data.get("hook") or ""),
            summary=str(data.get("summary") or ""),
            estimated_duration=float(data.get("estimated_duration", 60.0) or 60.0),
            provider=str(data.get("provider") or MANUAL_PROVIDER_ID),
            provider_version=str(data.get("provider_version") or MANUAL_PROVIDER_VERSION),
            schema_version=str(data.get("schema_version") or STORY_SCHEMA_VERSION),
            story_prompt_version=str(data.get("story_prompt_version") or STORY_PROMPT_VERSION),
            language=str(data.get("language") or "ja"),
            status=status,
            created_at=str(data.get("created_at") or ""),
            updated_at=str(data.get("updated_at") or ""),
            tags=[str(item).strip() for item in tags if str(item).strip()] if isinstance(tags, list) else [],
            memo=str(data.get("memo") or ""),
            scenes=scenes,
            metadata=dict(metadata) if isinstance(metadata, dict) else {},
            validation=ValidationResult.from_dict(data.get("validation", {}) if isinstance(data.get("validation"), dict) else {}),
        )


@dataclass
class StoryPromptRequest:
    project_id: str
    theme: str
    genre: str = ""
    category: str = ""
    duration_seconds: float = 60.0
    scene_count: int = 5
    language: str = "ja"


@dataclass
class StoryPromptResult:
    provider: str
    provider_version: str
    schema_version: str
    story_prompt_version: str
    prompt: str
    created_at: str
