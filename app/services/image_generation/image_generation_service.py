from __future__ import annotations

import hashlib
import json
import logging
import re
import time
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QImage

from models import ProjectInfo
from services.project_service import ProjectService

from .models import (
    GeneratedImage,
    ImageGenerationCancelled,
    ImageGenerationError,
    ImageGenerationResult,
    ImageGenerationSettings,
    UsageEstimate,
)
from .provider import ImageGenerationProvider
from .prompt_library import PromptLibraryService, TemplatePromptSegments, TemplateSelectionResult
from .prompt_optimizer import PromptOptimizationResult, PromptOptimizer
from .usage_service import ImageGenerationUsageService


class ImageGenerationService:
    """Generate only missing project images from image_prompts.txt."""

    MANIFEST_NAME = "image_generation_manifest.json"
    TMP_SUFFIX = ".tmp"
    MIN_DIMENSION = 256

    def __init__(
        self,
        project_service: ProjectService,
        provider: ImageGenerationProvider,
        usage_service: ImageGenerationUsageService,
        prompt_library_service: PromptLibraryService | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.project_service = project_service
        self.provider = provider
        self.usage_service = usage_service
        self.logger = logger or logging.getLogger("ai_video_factory.image_generation")
        self.prompt_library_service = prompt_library_service
        self.prompt_optimizer = PromptOptimizer()

    def provider_status(self) -> dict[str, object]:
        status = self.provider.validate_configuration()
        return {"configured": status.configured, "message": status.message}

    def summarize_project(self, project: ProjectInfo, settings: ImageGenerationSettings) -> dict[str, object]:
        prompts = self.load_prompts(project)
        template_selection = self.resolve_template(project, prompts, settings)
        existing = self.valid_existing_indices(project)
        failed = list((project.image_generation or {}).get("failed_indices", [])) if hasattr(project, "image_generation") else []
        required = int(project.image_count)
        missing = [index for index in range(1, required + 1) if index not in existing]
        estimate = self.provider.estimate_usage(len(missing), settings)
        usage = self.usage_service.summary(project.name)
        return {
            "prompt_count": len(prompts),
            "required_count": required,
            "existing_indices": existing,
            "missing_indices": missing,
            "failed_indices": failed,
            "estimate": estimate,
            "usage": usage,
            "template_selection": template_selection,
        }

    def generate_missing(
        self,
        project: ProjectInfo,
        settings: ImageGenerationSettings,
        progress_callback=None,
        should_cancel=None,
        target_indices: list[int] | None = None,
    ) -> ImageGenerationResult:
        project_dir = project.path.resolve()
        images_dir = (project_dir / "images").resolve()
        self._ensure_inside_project(project_dir, images_dir)
        images_dir.mkdir(parents=True, exist_ok=True)
        self._cleanup_tmp(images_dir)

        self.provider.validate_model_settings(settings)
        prompts = self.load_prompts(project)
        required_count = int(project.image_count)
        self._validate_prompts(project, prompts, required_count, settings)
        template_selection = self.resolve_template(project, prompts, settings)
        existing = self.valid_existing_indices(project)
        if target_indices is None:
            planned = [index for index in range(1, required_count + 1) if index not in existing]
        else:
            planned = [index for index in target_indices if 1 <= int(index) <= required_count and int(index) not in existing]
        planned = list(dict.fromkeys(int(index) for index in planned))
        skipped_existing = [index for index in range(1, required_count + 1) if index in existing]
        estimate = self.provider.estimate_usage(len(planned), settings)
        usage_decision = self.usage_service.check_limits(
            project.name,
            len(planned),
            settings.max_images_per_run,
            settings.daily_request_limit,
            settings.per_project_image_limit,
        )
        if not usage_decision.allowed:
            raise ImageGenerationError(usage_decision.message, "usage_limit", False)
        if not planned:
            state = self._state(
                status="completed" if len(existing) >= required_count else "pending",
                project=project,
                settings=settings,
                requested_count=required_count,
                generated_indices=[],
                failed_indices=[],
                skipped_existing_indices=skipped_existing,
                completed_count=len(existing),
                current_index=0,
                estimated_usage=estimate,
                template_selection=template_selection,
            )
            self.project_service.update_metadata(project_dir, {"image_generation": state})
            return ImageGenerationResult(state["status"], skipped_existing_indices=skipped_existing, completed_count=len(existing), manifest_path=project_dir / self.MANIFEST_NAME)

        start_state = self._state(
            status="generating",
            project=project,
            settings=settings,
            requested_count=required_count,
            generated_indices=[],
            failed_indices=[],
            skipped_existing_indices=skipped_existing,
            completed_count=len(existing),
            current_index=planned[0],
            estimated_usage=estimate,
            started_at=self._now(),
            template_selection=template_selection,
        )
        self.project_service.update_metadata(project_dir, {"image_generation": start_state})
        self.logger.info(
            "generation start project=%s provider=%s model=%s steps=%s count=%s",
            project.name,
            settings.provider,
            settings.model,
            settings.steps,
            len(planned),
        )

        generated: list[int] = []
        failed: list[int] = []
        last_error = ""
        manifest = self._load_manifest(project_dir)
        try:
            for index in planned:
                if should_cancel and should_cancel():
                    raise ImageGenerationCancelled("画像生成をキャンセルしました。", "cancelled", False)
                if progress_callback:
                    progress_callback({"status": "generating", "current_index": index, "message": f"画像{index}を生成中"})
                optimization = self.build_prompt_optimization(prompts[index - 1], index, settings, project, prompts)
                final_prompt = optimization.optimized_prompt
                image, retry_count = self._generate_with_retry(final_prompt, settings, progress_callback, should_cancel, project.name, index)
                output_path = self._save_generated_image(project_dir, images_dir, index, image, settings)
                generated.append(index)
                self.usage_service.record_success(project.name, 1)
                manifest[str(index)] = {
                    "index": index,
                    "source_prompt": prompts[index - 1],
                    "final_prompt": final_prompt,
                    "original_prompt": optimization.original_prompt,
                    "optimized_prompt": optimization.optimized_prompt,
                    "optimizer_enabled": optimization.optimizer_enabled,
                    "optimizer_version": optimization.optimizer_version,
                    "scene_index": optimization.scene_index,
                    "scene_composition": optimization.scene_composition,
                    "applied_rules": optimization.applied_rules,
                    "skipped_rules": optimization.skipped_rules,
                    "removed_rules": optimization.removed_rules,
                    "original_length": optimization.original_length,
                    "optimized_length": optimization.optimized_length,
                    "max_prompt_length": optimization.max_prompt_length,
                    "was_compacted": optimization.was_compacted,
                    "was_truncated": optimization.was_truncated,
                    "selected_template": optimization.selected_template,
                    "template_version": optimization.template_version,
                    "template_mode": optimization.template_mode,
                    "manual_template": optimization.manual_template,
                    "detected_keywords": optimization.detected_keywords,
                    "matched_sources": optimization.matched_sources,
                    "candidate_scores": optimization.candidate_scores,
                    "resolution_reason": optimization.resolution_reason,
                    "inherited_templates": optimization.inherited_templates,
                    "selected_scene": optimization.selected_scene,
                    "scene_rule_applied": optimization.scene_rule_applied,
                    "skipped_scene_reason": optimization.skipped_scene_reason,
                    "applied_template_rules": optimization.applied_template_rules,
                    "skipped_template_rules": optimization.skipped_template_rules,
                    "template_warnings": optimization.template_warnings,
                    "provider": settings.provider,
                    "model": settings.model,
                    "steps": settings.steps,
                    "status": "completed",
                    "output_path": str(output_path.relative_to(project_dir)),
                    "generated_at": self._now(),
                    "error_code": "",
                    "retry_count": retry_count,
                    "request_id": image.request_id,
                }
                self._save_manifest(project_dir, manifest)
                existing = self.valid_existing_indices(self.project_service.load_project(project_dir))
                state = self._state(
                    status="generating",
                    project=project,
                    settings=settings,
                    requested_count=required_count,
                    generated_indices=generated,
                    failed_indices=failed,
                    skipped_existing_indices=skipped_existing,
                    completed_count=len(existing),
                    current_index=index,
                    estimated_usage=estimate,
                    started_at=start_state["started_at"],
                    retry_count=sum(int(item.get("retry_count", 0) or 0) for item in manifest.values() if isinstance(item, dict)),
                    template_selection=template_selection,
                )
                self.project_service.update_metadata(project_dir, {"image_generation": state})
                self.logger.info("generation success project=%s index=%s request_id=%s", project.name, index, image.request_id)
        except ImageGenerationCancelled as exc:
            final_state = self._final_state(project, settings, required_count, generated, failed, skipped_existing, estimate, "cancelled", str(exc), start_state["started_at"], template_selection)
            self.project_service.update_metadata(project_dir, {"image_generation": final_state})
            self.logger.info("generation cancelled project=%s completed=%s", project.name, len(generated))
            return ImageGenerationResult("cancelled", generated, failed, skipped_existing, final_state["completed_count"], str(exc), project_dir / self.MANIFEST_NAME)
        except ImageGenerationError as exc:
            last_error = str(exc)
            failed.extend(index for index in planned if index not in generated and index not in failed)
            for failed_index in failed:
                manifest.setdefault(str(failed_index), {})
                if isinstance(manifest[str(failed_index)], dict):
                    manifest[str(failed_index)].update(
                        {
                            "index": failed_index,
                            "source_prompt": prompts[failed_index - 1] if failed_index - 1 < len(prompts) else "",
                            "final_prompt": "",
                            "original_prompt": prompts[failed_index - 1] if failed_index - 1 < len(prompts) else "",
                            "optimized_prompt": "",
                            "optimizer_enabled": settings.prompt_optimizer_enabled,
                            "optimizer_version": PromptOptimizer.VERSION,
                            "scene_index": failed_index,
                            "scene_composition": "",
                            "applied_rules": [],
                            "skipped_rules": [],
                            "removed_rules": [],
                            "original_length": len(prompts[failed_index - 1]) if failed_index - 1 < len(prompts) else 0,
                            "optimized_length": 0,
                            "max_prompt_length": self.provider.get_model_info(settings.model).prompt_max_length,
                            "was_compacted": False,
                            "was_truncated": False,
                            "selected_template": template_selection.selected_template if template_selection else "",
                            "template_version": template_selection.template_version if template_selection else "",
                            "template_mode": template_selection.template_mode if template_selection else settings.prompt_template_mode,
                            "manual_template": template_selection.manual_template if template_selection else settings.manual_prompt_template,
                            "detected_keywords": template_selection.detected_keywords if template_selection else [],
                            "matched_sources": template_selection.matched_sources if template_selection else [],
                            "candidate_scores": template_selection.candidate_scores if template_selection else {},
                            "resolution_reason": template_selection.resolution_reason if template_selection else "",
                            "inherited_templates": template_selection.inherited_templates if template_selection else [],
                            "selected_scene": "",
                            "scene_rule_applied": False,
                            "skipped_scene_reason": "generation failed before scene completion",
                            "applied_template_rules": [],
                            "skipped_template_rules": [],
                            "template_warnings": template_selection.template_warnings if template_selection else [],
                            "provider": settings.provider,
                            "model": settings.model,
                            "steps": settings.steps,
                            "status": "failed",
                            "output_path": "",
                            "generated_at": "",
                            "error_code": exc.code,
                            "retry_count": 0,
                            "request_id": "",
                        }
                    )
            self._save_manifest(project_dir, manifest)
            status = "partially_completed" if generated else "failed"
            final_state = self._final_state(project, settings, required_count, generated, failed, skipped_existing, estimate, status, last_error, start_state["started_at"], template_selection)
            self.project_service.update_metadata(project_dir, {"image_generation": final_state})
            self.logger.info("generation failure project=%s code=%s retryable=%s", project.name, exc.code, exc.retryable)
            return ImageGenerationResult(status, generated, failed, skipped_existing, final_state["completed_count"], last_error, project_dir / self.MANIFEST_NAME)

        existing = self.valid_existing_indices(self.project_service.load_project(project_dir))
        status = "completed" if len(existing) >= required_count else "partially_completed"
        final_state = self._final_state(project, settings, required_count, generated, failed, skipped_existing, estimate, status, "", start_state["started_at"], template_selection)
        self.project_service.update_metadata(project_dir, {"image_generation": final_state})
        return ImageGenerationResult(status, generated, failed, skipped_existing, final_state["completed_count"], "", project_dir / self.MANIFEST_NAME)

    def retry_failed(self, project: ProjectInfo, settings: ImageGenerationSettings, progress_callback=None, should_cancel=None) -> ImageGenerationResult:
        failed = [int(index) for index in (project.image_generation or {}).get("failed_indices", []) if str(index).isdigit()]
        if not failed:
            raise ImageGenerationError("再試行する失敗画像がありません。", "no_failed_indices", False)
        return self.generate_missing(project, settings, progress_callback, should_cancel, failed)

    def load_prompts(self, project: ProjectInfo) -> list[str]:
        path = project.path / "image_prompts.txt"
        text = path.read_text(encoding="utf-8") if path.exists() else ""
        prompts = [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]
        if not prompts:
            prompts = [line.strip() for line in text.splitlines() if line.strip()]
        return prompts

    def valid_existing_indices(self, project: ProjectInfo) -> list[int]:
        images_dir = project.path / "images"
        valid = []
        for index in range(1, int(project.image_count) + 1):
            path = images_dir / f"{index:03d}.png"
            if path.exists() and self._is_valid_image(path, 1080, 1920):
                valid.append(index)
        return valid

    def _validate_prompts(self, project: ProjectInfo, prompts: list[str], required_count: int, settings: ImageGenerationSettings) -> None:
        if len(prompts) < required_count:
            missing = ", ".join(str(index) for index in range(len(prompts) + 1, required_count + 1))
            raise ImageGenerationError(f"画像プロンプトが不足しています。足りない番号: {missing}", "missing_prompts", False)
        model_info = self.provider.get_model_info(settings.model)
        for index, prompt in enumerate(prompts[:required_count], start=1):
            if not prompt.strip():
                raise ImageGenerationError(f"画像{index}のプロンプトが空です。", "empty_prompt", False)
            optimization = self.build_prompt_optimization(prompt, index, settings, project, prompts)
            if optimization.optimized_length > model_info.prompt_max_length:
                raise ImageGenerationError(f"画像{index}のプロンプトがCloudflare上限{model_info.prompt_max_length}文字を超えています。", "prompt_too_long", False)

    def _generate_with_retry(self, prompt: str, settings: ImageGenerationSettings, progress_callback, should_cancel, project_id: str, index: int) -> tuple[GeneratedImage, int]:
        retry_count = 0
        while True:
            try:
                image = self.provider.generate_image(prompt, settings, should_cancel)
                return image, retry_count
            except ImageGenerationCancelled:
                raise
            except ImageGenerationError as exc:
                if not exc.retryable or retry_count >= int(settings.max_retries_per_image):
                    raise
                retry_count += 1
                retry_after = float(getattr(exc, "retry_after", 0.0) or 0.0)
                delay = retry_after if retry_after > 0 else min(2 ** retry_count, 10)
                self.logger.info("generation retry project=%s index=%s retry=%s code=%s", project_id, index, retry_count, exc.code)
                if progress_callback:
                    progress_callback({"status": "retrying", "current_index": index, "retry_count": retry_count, "message": f"画像{index}を再試行中"})
                end = time.monotonic() + delay
                while time.monotonic() < end:
                    if should_cancel and should_cancel():
                        raise ImageGenerationCancelled("画像生成をキャンセルしました。", "cancelled", False)
                    time.sleep(0.1)

    def _save_generated_image(self, project_dir: Path, images_dir: Path, index: int, image: GeneratedImage, settings: ImageGenerationSettings) -> Path:
        target_path = (images_dir / f"{index:03d}.png").resolve()
        self._ensure_inside_project(project_dir, target_path)
        if target_path.exists() and self._is_valid_image(target_path, settings.target_width, settings.target_height):
            return target_path
        temp_path = target_path.with_suffix(".png" + self.TMP_SUFFIX)
        try:
            temp_path.write_bytes(image.image_bytes)
            loaded = QImage(str(temp_path))
            if loaded.isNull() or loaded.width() < self.MIN_DIMENSION or loaded.height() < self.MIN_DIMENSION:
                raise ImageGenerationError("生成画像が壊れている、または小さすぎます。", "invalid_generated_image", False)
            normalized = self._normalize_to_target(loaded, int(settings.target_width), int(settings.target_height))
            if not normalized.save(str(temp_path), "PNG"):
                raise ImageGenerationError("生成画像のPNG保存に失敗しました。", "disk_error", False)
            temp_path.replace(target_path)
        except ImageGenerationError:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise
        except OSError as exc:
            if temp_path.exists():
                temp_path.unlink(missing_ok=True)
            raise ImageGenerationError("生成画像の保存に失敗しました。", "disk_error", False) from exc
        return target_path

    def _normalize_to_target(self, image: QImage, target_width: int, target_height: int) -> QImage:
        width = target_width if target_width >= self.MIN_DIMENSION else 1080
        height = target_height if target_height >= self.MIN_DIMENSION else 1920
        scaled = image.scaled(width, height, Qt.KeepAspectRatioByExpanding, Qt.SmoothTransformation)
        x = max(0, (scaled.width() - width) // 2)
        y = max(0, (scaled.height() - height) // 2)
        cropped = scaled.copy(QRect(x, y, width, height))
        if cropped.format() != QImage.Format_ARGB32:
            cropped = cropped.convertToFormat(QImage.Format_ARGB32)
        return cropped

    def _is_valid_image(self, path: Path, target_width: int | None = None, target_height: int | None = None) -> bool:
        image = QImage(str(path))
        if image.isNull() or image.width() < self.MIN_DIMENSION or image.height() < self.MIN_DIMENSION:
            return False
        if target_width and target_height:
            expected_ratio = target_width / target_height
            actual_ratio = image.width() / image.height()
            return abs(actual_ratio - expected_ratio) <= 0.08
        return True

    def resolve_template(self, project: ProjectInfo, prompts: list[str], settings: ImageGenerationSettings) -> TemplateSelectionResult | None:
        if self.prompt_library_service is None:
            return None
        state = project.image_generation or {}
        mode = settings.prompt_template_mode
        manual = settings.manual_prompt_template
        if isinstance(state, dict):
            mode = str(state.get("prompt_template_mode") or state.get("template_mode") or mode)
            if not manual and isinstance(state.get("manual_prompt_template"), str):
                manual = str(state.get("manual_prompt_template"))
            if not manual and isinstance(state.get("prompt_template"), str):
                manual = str(state.get("prompt_template"))
        return self.prompt_library_service.select_template(project, prompts, mode, manual)

    def build_prompt_optimization(
        self,
        prompt: str,
        scene_index: int,
        settings: ImageGenerationSettings,
        project: ProjectInfo | None = None,
        prompts: list[str] | None = None,
    ) -> PromptOptimizationResult:
        model_info = self.provider.get_model_info(settings.model)
        template_selection = None
        template_segments = None
        if project is not None and prompts is not None and self.prompt_library_service is not None:
            template_selection = self.resolve_template(project, prompts, settings)
            if template_selection is not None:
                template = self.prompt_library_service.get_template(template_selection.selected_template)
                template_segments = self.prompt_library_service.build_segments(template)
                if not self._prompt_matches_template(prompt, template):
                    template_segments.scientific_required = []
                    template_segments.scientific_optional = []
                    template_segments.negative_theme_specific = []
                    template_selection.skipped_template_rules.append("theme_specific_rules: no_keyword_in_prompt")
                scene = self.prompt_library_service.scene_for_index(template, scene_index)
                if scene is not None:
                    template_selection.selected_scene = scene.id
                    scene_values = [*scene.camera, *scene.lighting, *scene.composition]
                    template_segments.scene = list(scene_values)
                    template_segments.scene_short = list(scene.short or scene_values[:1])
                else:
                    template_selection.selected_scene = ""
                    template_selection.skipped_scene_reason = "no scene template"
        try:
            return self.prompt_optimizer.optimize(
                prompt,
                scene_index=scene_index,
                max_prompt_length=model_info.prompt_max_length,
                enabled=bool(settings.prompt_optimizer_enabled),
                template_segments=template_segments if settings.prompt_optimizer_enabled else None,
                template_selection=template_selection,
            )
        except ValueError as exc:
            raise ImageGenerationError(str(exc), "prompt_too_long", False) from exc

    def _prompt_matches_template(self, prompt: str, template) -> bool:
        if getattr(template, "id", "") == "generic_space":
            return True
        text = prompt.casefold()
        return any(str(keyword).casefold() in text for keyword in getattr(template, "keywords", ()) if keyword)

    def _state(
        self,
        status: str,
        project: ProjectInfo,
        settings: ImageGenerationSettings,
        requested_count: int,
        generated_indices: list[int],
        failed_indices: list[int],
        skipped_existing_indices: list[int],
        completed_count: int,
        current_index: int,
        estimated_usage: UsageEstimate,
        started_at: str | None = None,
        retry_count: int = 0,
        last_error: str | None = None,
        template_selection: TemplateSelectionResult | None = None,
    ) -> dict[str, object]:
        state = {
            "status": status,
            "provider": settings.provider,
            "model": settings.model,
            "requested_count": requested_count,
            "completed_count": completed_count,
            "generated_indices": generated_indices,
            "failed_indices": failed_indices,
            "skipped_existing_indices": skipped_existing_indices,
            "current_index": current_index,
            "started_at": started_at,
            "completed_at": self._now() if status == "completed" else None,
            "cancelled_at": self._now() if status == "cancelled" else None,
            "retry_count": retry_count,
            "last_error": last_error,
            "estimated_usage": estimated_usage.__dict__,
            "prompt_template_mode": settings.prompt_template_mode,
            "manual_prompt_template": settings.manual_prompt_template,
        }
        if template_selection is not None:
            state["resolved_prompt_template"] = template_selection.selected_template
        return state

    def _final_state(
        self,
        project: ProjectInfo,
        settings: ImageGenerationSettings,
        requested_count: int,
        generated: list[int],
        failed: list[int],
        skipped_existing: list[int],
        estimate: UsageEstimate,
        status: str,
        last_error: str,
        started_at: str | None,
        template_selection: TemplateSelectionResult | None = None,
    ) -> dict[str, object]:
        existing = self.valid_existing_indices(self.project_service.load_project(project.path))
        return self._state(
            status=status,
            project=project,
            settings=settings,
            requested_count=requested_count,
            generated_indices=generated,
            failed_indices=failed,
            skipped_existing_indices=skipped_existing,
            completed_count=len(existing),
            current_index=0,
            estimated_usage=estimate,
            started_at=started_at,
            retry_count=0,
            last_error=last_error,
            template_selection=template_selection,
        )

    def _load_manifest(self, project_dir: Path) -> dict[str, object]:
        path = project_dir / self.MANIFEST_NAME
        if not path.exists():
            return {}
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _save_manifest(self, project_dir: Path, manifest: dict[str, object]) -> None:
        path = project_dir / self.MANIFEST_NAME
        temp_path = path.with_suffix(path.suffix + ".tmp")
        temp_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(path)

    def _cleanup_tmp(self, images_dir: Path) -> None:
        for path in images_dir.glob(f"*.png{self.TMP_SUFFIX}"):
            path.unlink(missing_ok=True)

    def _ensure_inside_project(self, project_dir: Path, target: Path) -> None:
        try:
            target.resolve().relative_to(project_dir.resolve())
        except ValueError as exc:
            raise ImageGenerationError("保存先がプロジェクト外です。", "path_traversal", False) from exc

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
