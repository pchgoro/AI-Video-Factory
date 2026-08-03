from __future__ import annotations

import os
import shutil
from pathlib import Path

from models import ProjectInfo
from services.image_generation import ImageGenerationService
from services.production_orchestrator.artifact_service import ArtifactService
from services.production_orchestrator.dependency import dependencies_for
from services.production_orchestrator.models import PreflightResult, ProductionOptions
from services.story_composer import StoryService


class ProductionPreflightService:
    def __init__(
        self,
        story_service: StoryService,
        image_generation_service: ImageGenerationService,
        artifact_service: ArtifactService,
    ) -> None:
        self.story_service = story_service
        self.image_generation_service = image_generation_service
        self.artifact_service = artifact_service

    def check(self, project: ProjectInfo, options: ProductionOptions, image_settings, dry_run: bool = False) -> PreflightResult:
        result = PreflightResult()
        project_dir = project.path
        if not project_dir.exists() or not project_dir.is_dir():
            result.add("error", "invalid_project_path", "Project path is missing or invalid.")
            return result
        if not self._is_inside_projects(project_dir):
            result.add("error", "project_outside_root", "Project path is outside the configured projects folder.")
        if not os.access(project_dir, os.R_OK):
            result.add("error", "project_not_readable", "Project folder is not readable.")
        if not os.access(project_dir, os.W_OK):
            result.add("error", "project_not_writable", "Project folder is not writable.")

        story = self.story_service.load_story(project)
        if story is None:
            result.add("error", "missing_story", "story.json is missing.", "validate_story")
        else:
            validation = self.story_service.validator.validate(story)
            if validation.has_errors:
                result.add("error", "story_validation_failed", "Story validation has errors.", "validate_story")
            for warning in validation.warnings:
                result.add("warning", "story_validation_warning", warning.message, "validate_story")

        artifacts = self.artifact_service.artifact_status(project)
        result.artifact_status = artifacts

        self._check_export(result, options, artifacts)
        self._check_images(project, result, options, image_settings, artifacts)
        self._check_voice(result, options, artifacts)
        self._check_subtitles(result, options, artifacts)
        self._check_render(result, options, artifacts)
        self._check_uploads(project, result, options, artifacts)
        self._check_dependencies(result, options, artifacts)
        self._check_disk_space(project, result)

        if dry_run:
            result.add("info", "dry_run", "Dry Run will not call APIs, VOICEVOX, subtitle generation, FFmpeg, or uploads.")
        return result

    def _check_export(self, result: PreflightResult, options: ProductionOptions, artifacts: dict) -> None:
        if options.export_story:
            return
        if artifacts.get("factory_export", {}).get("state") != "fresh":
            result.add("error", "factory_export_missing", "Factory export files are missing but Export Story is OFF.", "export_story")

    def _check_images(self, project: ProjectInfo, result: PreflightResult, options: ProductionOptions, image_settings, artifacts: dict) -> None:
        image_state = artifacts.get("images", {}).get("state")
        if options.generate_images:
            provider_status = self.image_generation_service.provider_status()
            if not provider_status.get("configured"):
                result.add("error", "cloudflare_not_configured", str(provider_status.get("message") or "Cloudflare is not configured."), "generate_images")
            try:
                summary = self.image_generation_service.summarize_project(project, image_settings)
                if int(summary.get("prompt_count", 0) or 0) < int(summary.get("required_count", project.image_count) or project.image_count):
                    result.add("error", "image_prompts_missing", "image_prompts.txt has fewer prompts than required images.", "generate_images")
            except Exception as exc:
                result.add("error", "image_preflight_failed", str(exc), "generate_images")
        elif image_state != "fresh":
            result.add("error", "images_missing", "Images are not ready and Generate Images is OFF.", "generate_images")

    def _check_voice(self, result: PreflightResult, options: ProductionOptions, artifacts: dict) -> None:
        if options.generate_voice:
            result.add("info", "voicevox_config", "VOICEVOX connection is checked during Normal Run; Dry Run does not synthesize audio.", "generate_voice")
        elif artifacts.get("audio", {}).get("state") != "fresh":
            result.add("error", "audio_missing", "voice.wav is not ready and Generate Voice is OFF.", "generate_voice")

    def _check_subtitles(self, result: PreflightResult, options: ProductionOptions, artifacts: dict) -> None:
        if options.generate_subtitles:
            return
        if artifacts.get("subtitles", {}).get("state") != "fresh":
            result.add("error", "subtitles_missing", "subtitles.ass is not ready and Generate Subtitles is OFF.", "generate_subtitles")

    def _check_render(self, result: PreflightResult, options: ProductionOptions, artifacts: dict) -> None:
        if options.render_video:
            if not self.artifact_service.ffmpeg_available():
                result.add("error", "ffmpeg_missing", "FFmpeg is not available.", "render_video")
            if not self.artifact_service.ffprobe_available():
                result.add("warning", "ffprobe_missing", "ffprobe is not available; video validation will be limited.", "render_video")
            return
        if options.upload_youtube or options.upload_tiktok:
            if artifacts.get("video", {}).get("state") != "fresh":
                result.add("error", "final_mp4_missing", "final.mp4 is not ready but Render Video is OFF.", "render_video")

    def _check_uploads(self, project: ProjectInfo, result: PreflightResult, options: ProductionOptions, artifacts: dict) -> None:
        if options.upload_youtube:
            if artifacts.get("youtube", {}).get("duplicate"):
                result.add("error", "youtube_duplicate", "YouTube video ID already exists; duplicate upload is blocked.", "upload_youtube")
            if not self._env_value("YOUTUBE_CLIENT_SECRETS_FILE"):
                result.add("warning", "youtube_auth_unknown", "YouTube OAuth settings are not fully configured or not loaded.", "upload_youtube")
        if options.upload_tiktok:
            if artifacts.get("tiktok", {}).get("duplicate"):
                result.add("error", "tiktok_duplicate", "TikTok publish ID already exists; duplicate upload is blocked.", "upload_tiktok")
            if not self._env_value("TIKTOK_CLIENT_KEY"):
                result.add("warning", "tiktok_auth_unknown", "TikTok OAuth settings are not fully configured or not loaded.", "upload_tiktok")
        if (options.upload_youtube or options.upload_tiktok) and artifacts.get("video", {}).get("state") not in {"fresh", "stale"} and not options.render_video:
            result.add("error", "upload_video_missing", "Upload requires final.mp4 or Render Video ON.")

    def _check_dependencies(self, result: PreflightResult, options: ProductionOptions, artifacts: dict) -> None:
        enabled = {step for step in dependencies_for("upload_tiktok")}
        enabled.update(step for step in dependencies_for("upload_youtube"))
        for step_id in [
            "render_video",
            "upload_youtube",
            "upload_tiktok",
        ]:
            if not options.is_enabled(step_id):
                continue
            for dependency in dependencies_for(step_id):
                if options.is_enabled(dependency):
                    continue
                artifact_key = {
                    "export_story": "factory_export",
                    "generate_images": "images",
                    "generate_voice": "audio",
                    "generate_subtitles": "subtitles",
                    "render_video": "video",
                }.get(dependency)
                if artifact_key and artifacts.get(artifact_key, {}).get("state") == "fresh":
                    continue
                result.add("error", "dependency_disabled", f"{step_id} requires {dependency}, but it is OFF and no valid artifact exists.", step_id)

    def _check_disk_space(self, project: ProjectInfo, result: PreflightResult) -> None:
        try:
            usage = shutil.disk_usage(project.path)
        except OSError:
            return
        minimum = 500 * 1024 * 1024
        if usage.free < minimum:
            result.add("error", "disk_space_low", "Less than 500MB disk space is available.")
        else:
            result.add("info", "disk_space", f"Free disk space: {usage.free // (1024 * 1024)}MB")

    def _is_inside_projects(self, project_dir: Path) -> bool:
        try:
            return project_dir.resolve().parent.name == "projects"
        except OSError:
            return False

    def _env_value(self, name: str) -> str:
        try:
            from dotenv import load_dotenv

            load_dotenv()
        except Exception:
            pass
        return os.environ.get(name, "").strip()
