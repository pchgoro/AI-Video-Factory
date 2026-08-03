from __future__ import annotations

import json
import hashlib
import shutil
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from models import ProjectInfo
from services.project_service import ProjectService
from services.story_provider import (
    CancellationToken,
    GeminiStoryProvider,
    MockStoryProvider,
    OpenAIStoryProvider,
    StoryGenerationRequest,
    StoryGenerationResult,
    StoryGenerationState,
    StoryProviderManager,
)
from services.story_provider.manager import ManualPromptProviderAdapter

from .factory_adapter import FactoryExportPreview, FactoryExportResult, StoryFactoryAdapter
from .manual_prompt_provider import ManualPromptProvider
from .models import Story, StoryPromptRequest, StoryPromptResult, ValidationResult
from .validator import StoryValidationError, StoryValidator


STORY_FILE = "story.json"
STORY_MANIFEST_FILE = "story_manifest.json"
STORY_GENERATION_FILE = "story_generation.json"
STORY_GENERATED_CANDIDATE_FILE = "story_generated_candidate.json"
MAX_RAW_RESPONSE_BYTES = 256 * 1024


class StoryService:
    def __init__(
        self,
        project_service: ProjectService,
        provider: ManualPromptProvider | None = None,
        validator: StoryValidator | None = None,
        adapter: StoryFactoryAdapter | None = None,
        provider_manager: StoryProviderManager | None = None,
        logger=None,
    ) -> None:
        self.project_service = project_service
        self.validator = validator or StoryValidator()
        self.provider = provider or ManualPromptProvider(self.validator)
        self.adapter = adapter or StoryFactoryAdapter(project_service)
        self.provider_manager = provider_manager or StoryProviderManager(
            [
                ManualPromptProviderAdapter(self.provider),
                GeminiStoryProvider(logger=logger),
                MockStoryProvider(),
                OpenAIStoryProvider(logger=logger),
            ]
        )
        self.logger = logger

    def build_prompt(self, project: ProjectInfo, scene_count: int, duration_seconds: float | None = None) -> StoryPromptResult:
        request = StoryPromptRequest(
            project_id=project.name,
            theme=project.topic or project.title,
            genre=project.genre,
            category=project.category,
            duration_seconds=duration_seconds or self._duration_seconds(project.duration),
            scene_count=scene_count,
        )
        result = self.provider.build_prompt(request)
        manifest = self.load_manifest(project)
        now = self._now()
        manifest.update(
            {
                "provider": result.provider,
                "provider_version": result.provider_version,
                "schema_version": result.schema_version,
                "story_prompt_version": result.story_prompt_version,
                "prompt": result.prompt,
                "updated_at": now,
            }
        )
        manifest.setdefault("created_at", now)
        self.save_manifest(project, manifest)
        return result

    def import_story_json(self, project: ProjectInfo, raw_response: str) -> Story:
        story = self.provider.parse_response(raw_response, project_id=project.name)
        if not story.theme:
            story.theme = project.topic or project.title
        self.save_story(project, story)
        manifest = self.load_manifest(project)
        now = self._now()
        manifest.update(
            {
                "provider": story.provider,
                "provider_version": story.provider_version,
                "schema_version": story.schema_version,
                "story_prompt_version": story.story_prompt_version,
                "raw_response": self._limited_raw(raw_response),
                "validation": story.validation.to_dict(),
                "last_imported_at": now,
                "last_validated_at": now,
                "updated_at": now,
            }
        )
        manifest.setdefault("created_at", now)
        self.save_manifest(project, manifest)
        return story

    def validate_story(self, project: ProjectInfo, story: Story | None = None) -> ValidationResult:
        story = story or self.load_story(project)
        if story is None:
            result = ValidationResult(status="invalid")
            result.add("error", "story.jsonがありません。", "story")
            return result
        result = self.validator.validate(story)
        story.status = "invalid" if result.has_errors else "valid"
        story.touch()
        self.save_story(project, story)
        manifest = self.load_manifest(project)
        now = self._now()
        manifest.update({"validation": result.to_dict(), "last_validated_at": now, "updated_at": now})
        manifest.setdefault("created_at", now)
        self.save_manifest(project, manifest)
        return result

    def save_story(self, project: ProjectInfo, story: Story) -> Story:
        story.project_id = story.project_id or project.name
        story.touch()
        self._atomic_json(project.path / STORY_FILE, story.to_dict())
        return story

    def load_story(self, project: ProjectInfo) -> Story | None:
        path = project.path / STORY_FILE
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise StoryValidationError("story.jsonの形式が正しくありません。")
        story = Story.from_dict(data)
        if not story.validation.errors and not story.validation.warnings and not story.validation.infos:
            story.validation = self.validator.validate(story)
        return story

    def load_manifest(self, project: ProjectInfo) -> dict[str, Any]:
        path = project.path / STORY_MANIFEST_FILE
        if not path.exists():
            now = self._now()
            return {
                "provider": self.provider.provider_id,
                "provider_version": self.provider.provider_version,
                "schema_version": "1.0",
                "story_prompt_version": "1.0",
                "prompt": "",
                "validation": {"status": "valid", "errors": [], "warnings": [], "infos": []},
                "raw_response": "",
                "last_imported_at": None,
                "last_validated_at": None,
                "last_exported_at": None,
                "created_at": now,
                "updated_at": now,
            }
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}

    def save_manifest(self, project: ProjectInfo, manifest: dict[str, Any]) -> None:
        self._atomic_json(project.path / STORY_MANIFEST_FILE, manifest)

    def load_generation_state(self, project: ProjectInfo) -> StoryGenerationState | None:
        path = project.path / STORY_GENERATION_FILE
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            state = StoryGenerationState(project_id=project.name, status="failed", error_code="corrupt_generation_state")
            state.last_error = "story_generation.jsonを読み取れません。"
            return state
        if not isinstance(data, dict):
            return StoryGenerationState(project_id=project.name, status="failed", error_code="invalid_generation_state")
        state = StoryGenerationState.from_dict(data)
        if state.status == "interrupted":
            self.save_generation_state(project, state)
        return state

    def save_generation_state(self, project: ProjectInfo, state: StoryGenerationState) -> None:
        state.updated_at = self._now()
        self._atomic_json(project.path / STORY_GENERATION_FILE, state.to_dict(), fsync=True)

    def load_generated_candidate(self, project: ProjectInfo) -> Story | None:
        path = project.path / STORY_GENERATED_CANDIDATE_FILE
        if not path.exists():
            return None
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise StoryValidationError("生成候補Storyの形式が正しくありません。")
        story = Story.from_dict(data)
        story.validation = self.validator.validate(story)
        return story

    def generate_story(
        self,
        project: ProjectInfo,
        request: StoryGenerationRequest,
        provider_id: str = "openai",
        resume_from_generation_id: str | None = None,
        cancellation_token: CancellationToken | None = None,
        progress_callback=None,
    ) -> StoryGenerationResult:
        request.project_id = project.name
        request.validate()
        provider = self.provider_manager.get(provider_id)
        state = StoryGenerationState(
            project_id=project.name,
            provider=provider.provider_id,
            provider_version=provider.provider_version,
            model=request.model,
            status="pending",
            resume_from_generation_id=resume_from_generation_id,
            request_snapshot=request.safe_snapshot(self._hash_text(request.theme)),
            free_tier_only=request.provider_options.get("free_tier_only") if isinstance(request.provider_options.get("free_tier_only"), bool) else None,
            model_free_tier_status=request.provider_options.get("model_free_tier_status") if isinstance(request.provider_options.get("model_free_tier_status"), str) else None,
            project_tier_status=request.provider_options.get("project_tier_status") if isinstance(request.provider_options.get("project_tier_status"), str) else None,
            billing_status=request.provider_options.get("billing_status") if isinstance(request.provider_options.get("billing_status"), str) else None,
            charge_risk=request.provider_options.get("charge_risk") if isinstance(request.provider_options.get("charge_risk"), str) else None,
        )
        self.save_generation_state(project, state)
        started = time.monotonic()
        state.status = "running"
        state.started_at = self._now()
        state.attempt_count = 1
        self.save_generation_state(project, state)
        if self.logger:
            self.logger.info(
                "story generation start generation_id=%s project=%s provider=%s model=%s",
                state.generation_id,
                project.name,
                provider.provider_id,
                request.model,
            )
        try:
            if progress_callback:
                progress_callback("Story生成を開始しました", 5)
            result = provider.generate_story(request, cancellation_token, progress_callback)
            state.retry_count = result.retry_count
            state.metrics = result.metrics
            state.provider_version = result.provider_version or state.provider_version
            state.duration_ms = int((time.monotonic() - started) * 1000)
            if result.status == "cancelled":
                state.status = "cancelled"
                state.completed_at = self._now()
                self.save_generation_state(project, state)
                if self.logger:
                    self.logger.info("story generation cancelled generation_id=%s project=%s", state.generation_id, project.name)
                return result
            if result.status != "completed" or result.story is None:
                state.status = "failed"
                state.last_error = result.error_message or "Story生成に失敗しました。"
                state.error_code = result.error_code or "generation_failed"
                state.completed_at = self._now()
                self.save_generation_state(project, state)
                if self.logger:
                    self.logger.info(
                        "story generation failed generation_id=%s project=%s error_code=%s retry_count=%s",
                        state.generation_id,
                        project.name,
                        state.error_code,
                        state.retry_count,
                    )
                return result
            story = result.story
            story.project_id = project.name
            validation = self.validator.validate(story)
            story.validation = validation
            if validation.has_errors:
                state.status = "failed"
                state.error_code = "story_validation_error"
                state.last_error = "生成StoryにValidation errorがあります。"
                state.completed_at = self._now()
                self.save_generation_state(project, state)
                if self.logger:
                    self.logger.info(
                        "story generation validation failed generation_id=%s project=%s",
                        state.generation_id,
                        project.name,
                    )
                return StoryGenerationResult(
                    story=story,
                    status="failed",
                    provider=result.provider,
                    provider_version=result.provider_version,
                    model=result.model,
                    metrics=result.metrics,
                    error_code=state.error_code,
                    error_message=state.last_error,
                    retry_count=result.retry_count,
                )
            story.status = "valid"
            story.touch()
            self._atomic_json(project.path / STORY_GENERATED_CANDIDATE_FILE, story.to_dict(), fsync=True)
            state.status = "completed"
            state.completed_at = self._now()
            self.save_generation_state(project, state)
            if self.logger:
                self.logger.info(
                    "story generation completed generation_id=%s project=%s model=%s input_tokens=%s output_tokens=%s cost=%s",
                    state.generation_id,
                    project.name,
                    request.model,
                    state.metrics.input_tokens,
                    state.metrics.output_tokens,
                    state.metrics.estimated_cost_usd,
                )
            if progress_callback:
                progress_callback("生成候補Storyを保存しました", 100)
            return result
        except Exception as exc:
            state.status = "failed"
            state.error_code = "unexpected_error"
            state.last_error = self._sanitize_error(str(exc))
            state.duration_ms = int((time.monotonic() - started) * 1000)
            state.completed_at = self._now()
            self.save_generation_state(project, state)
            if self.logger:
                self.logger.info("story generation failed project=%s error=%s", project.name, state.error_code)
            return StoryGenerationResult(
                status="failed",
                provider=provider.provider_id,
                provider_version=provider.provider_version,
                model=request.model,
                error_code=state.error_code,
                error_message=state.last_error,
            )

    def use_generated_story(self, project: ProjectInfo) -> Story:
        candidate = self.load_generated_candidate(project)
        if candidate is None:
            raise StoryValidationError("採用できる生成候補Storyがありません。")
        validation = self.validator.validate(candidate)
        if validation.has_errors:
            raise StoryValidationError("生成候補StoryにValidation errorがあるため採用できません。")
        story_path = project.path / STORY_FILE
        if story_path.exists():
            backup_dir = project.path / "backups" / f"story_ai_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            backup_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(story_path, backup_dir / STORY_FILE)
        candidate.status = "valid"
        self.save_story(project, candidate)
        manifest = self.load_manifest(project)
        now = self._now()
        manifest.update(
            {
                "provider": candidate.provider,
                "provider_version": candidate.provider_version,
                "validation": validation.to_dict(),
                "last_imported_at": now,
                "last_validated_at": now,
                "updated_at": now,
            }
        )
        self.save_manifest(project, manifest)
        return candidate

    def reset(self, project: ProjectInfo) -> None:
        for name in (STORY_FILE, STORY_MANIFEST_FILE):
            (project.path / name).unlink(missing_ok=True)

    def export_preview(self, project: ProjectInfo) -> FactoryExportPreview:
        story = self._require_story(project)
        return self.adapter.preview(project, story)

    def export_to_factory(self, project: ProjectInfo) -> FactoryExportResult:
        story = self._require_story(project)
        result = self.validator.validate(story)
        if result.has_errors:
            raise StoryValidationError("Validation errorがあるためExportできません。")
        export_result = self.adapter.export(project, story)
        story.status = "exported_to_factory"
        story.touch()
        self.save_story(project, story)
        manifest = self.load_manifest(project)
        now = self._now()
        manifest.update(
            {
                "validation": result.to_dict(),
                "last_validated_at": now,
                "last_exported_at": now,
                "content_source": "story_composer",
                "content_exported_at": now,
                "updated_at": now,
            }
        )
        self.save_manifest(project, manifest)
        return export_result

    def _require_story(self, project: ProjectInfo) -> Story:
        story = self.load_story(project)
        if story is None:
            raise StoryValidationError("Storyが保存されていません。")
        return story

    def _limited_raw(self, raw: str) -> str:
        if len(raw.encode("utf-8")) > MAX_RAW_RESPONSE_BYTES:
            raise StoryValidationError("Story JSONが大きすぎます。")
        return raw

    def _atomic_json(self, path: Path, data: dict[str, Any], fsync: bool = False) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            if fsync:
                import os

                os.fsync(file.fileno())
        tmp.replace(path)

    def _duration_seconds(self, duration: str) -> float:
        digits = "".join(ch for ch in str(duration) if ch.isdigit())
        return float(digits or 60)

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")

    def _hash_text(self, text: str) -> str:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()

    def _sanitize_error(self, message: str) -> str:
        return str(message).replace("\n", " ")[:600]
