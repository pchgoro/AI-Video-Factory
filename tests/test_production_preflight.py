from __future__ import annotations

import json
from pathlib import Path

from PySide6.QtGui import QImage

from config import AppPaths
from models import AppSettings
from services.image_generation import ImageGenerationService, ImageGenerationSettings
from services.image_generation.models import ModelInfo, ProviderStatus, UsageEstimate
from services.image_generation.provider import ImageGenerationProvider
from services.image_generation.usage_service import ImageGenerationUsageService
from services.production_orchestrator import ArtifactService, ProductionOptions, ProductionPreflightService
from services.project_service import ProjectService
from services.story_composer import StoryService


class ConfiguredProvider(ImageGenerationProvider):
    def validate_configuration(self) -> ProviderStatus:
        return ProviderStatus(True, "Configured")

    def get_model_info(self, model: str) -> ModelInfo:
        return ModelInfo("cloudflare_workers_ai", model, 2048, {"prompt", "steps"}, {"steps": 4}, "test")

    def validate_model_settings(self, settings: ImageGenerationSettings) -> None:
        return None

    def estimate_usage(self, request_count: int, settings: ImageGenerationSettings) -> UsageEstimate:
        return UsageEstimate(settings.provider, settings.model, request_count, settings.steps, 0.0, "test")

    def generate_image(self, prompt: str, settings: ImageGenerationSettings, should_cancel=None):
        raise AssertionError("preflight must not call provider")


def _story_payload() -> dict:
    return {
        "title": "Title",
        "description": "Description",
        "hook": "Hook",
        "summary": "Summary",
        "estimated_duration": 18.0,
        "tags": ["space"],
        "memo": "",
        "scenes": [
            {"scene_index": 1, "start_time": 0, "end_time": 6, "duration": 6, "scene_type": "hook", "narration": "n1", "subtitle": "s1", "image_prompt": "p1"},
            {"scene_index": 2, "start_time": 6, "end_time": 12, "duration": 6, "scene_type": "fact", "narration": "n2", "subtitle": "s2", "image_prompt": "p2"},
            {"scene_index": 3, "start_time": 12, "end_time": 18, "duration": 6, "scene_type": "ending", "narration": "n3", "subtitle": "s3", "image_prompt": "p3"},
        ],
    }


def _project(tmp_path: Path):
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("topic", "genre", "60", 3, "prompt")
    story_service = StoryService(project_service)
    story_service.import_story_json(project, json.dumps(_story_payload()))
    story_service.export_to_factory(project_service.load_project(project.path))
    image_service = ImageGenerationService(project_service, ConfiguredProvider(), ImageGenerationUsageService(tmp_path / "usage.json"))
    artifact_service = ArtifactService(AppSettings(ffmpeg_path="ffmpeg"))
    preflight = ProductionPreflightService(story_service, image_service, artifact_service)
    return project_service, project_service.load_project(project.path), preflight


def test_preflight_detects_missing_artifact_when_step_disabled(tmp_path: Path) -> None:
    _project_service, project, preflight = _project(tmp_path)

    result = preflight.check(project, ProductionOptions(generate_images=False, render_video=True), ImageGenerationSettings())

    assert result.has_errors
    assert any(issue.code == "images_missing" for issue in result.issues)


def test_preflight_allows_render_when_valid_images_reused(tmp_path: Path) -> None:
    _project_service, project, preflight = _project(tmp_path)
    for index in range(1, 4):
        image = QImage(320, 320, QImage.Format_RGB32)
        image.fill(0x224466)
        image.save(str(project.path / "images" / f"{index:03d}.png"), "PNG")

    result = preflight.check(project, ProductionOptions(generate_images=False, render_video=False), ImageGenerationSettings(), dry_run=True)

    assert not any(issue.code == "images_missing" for issue in result.issues)
    assert result.artifact_status["images"]["state"] == "fresh"
