from __future__ import annotations

import json
from pathlib import Path

import pytest

from config import AppPaths
from models import ProjectInfo
from services.image_generation import ImageGenerationService, ImageGenerationSettings
from services.image_generation.models import GeneratedImage, ModelInfo, ProviderStatus, UsageEstimate
from services.image_generation.prompt_library import PromptLibraryService
from services.image_generation.provider import ImageGenerationProvider
from services.image_generation.usage_service import ImageGenerationUsageService
from services.project_service import ProjectService


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _library(tmp_path: Path) -> PromptLibraryService:
    root = tmp_path / "prompt_library"
    _write(
        root / "generic_space.yaml",
        """
id: generic_space
name: Generic Space
version: "1.0"
priority: 1
keywords: [space, 宇宙]
quality:
  required: [cinematic space documentary style, vertical 9:16 composition for short video]
  optional: [film still quality]
subject:
  required: [clear primary subject]
negative:
  default: [no text, no logo, no watermark]
  theme_specific: []
scientific_guidance:
  required: []
  optional: []
scenes:
  - id: establishing
    camera: [wide establishing shot]
    short: [wide shot]
  - id: close_up
    camera: [close subject detail]
    short: [close detail]
""",
    )
    _write(
        root / "themes" / "black_hole.yaml",
        """
id: black_hole
name: Black Hole
version: "1.0"
extends: generic_space
priority: 100
keywords: [black hole, ブラックホール, event horizon]
quality:
  required: [physically believable gravitational lensing]
  optional: [NASA-inspired realism]
negative:
  theme_specific: [no fantasy portal appearance]
scientific_guidance:
  required: [avoid depicting a black hole as a solid planet]
  optional: [gravitational lensing should appear plausible when visible]
scenes:
  - id: close_up
    camera: [close-up of the event horizon]
    short: [event horizon close-up]
""",
    )
    _write(
        root / "themes" / "planet.yaml",
        """
id: planet
name: Planet
version: "1.0"
extends: generic_space
priority: 70
keywords: [planet, 惑星]
quality:
  required: [realistic planetary lighting]
  optional: []
negative:
  theme_specific: []
scientific_guidance:
  required: []
  optional: []
scenes: []
""",
    )
    return PromptLibraryService(root)


def _project(**overrides) -> ProjectInfo:
    data = {
        "name": "project",
        "path": Path("project"),
        "topic": "",
        "title": "",
        "genre": "",
        "category": "",
        "series": "",
        "tags": [],
        "image_count": 3,
        "image_generation": {},
    }
    data.update(overrides)
    return ProjectInfo(**data)


def test_valid_templates_load_and_inherit(tmp_path: Path) -> None:
    service = _library(tmp_path)

    black_hole = service.get_template("black_hole")

    assert "generic_space" in service.templates
    assert "cinematic space documentary style" in black_hole.quality_required
    assert "physically believable gravitational lensing" in black_hole.quality_required
    assert "generic_space" in black_hole.inherited_templates
    assert service.scene_for_index(black_hole, 2).id == "close_up"


def test_invalid_yaml_and_unknown_parent_fallback(tmp_path: Path) -> None:
    root = tmp_path / "prompt_library"
    _write(root / "generic_space.yaml", "id: generic_space\nname: Generic\nversion: '1.0'\n")
    _write(root / "bad.yaml", "id: bad: [")
    _write(root / "orphan.yaml", "id: orphan\nname: Orphan\nversion: '1.0'\nextends: missing\n")

    service = PromptLibraryService(root)

    assert "generic_space" in service.templates
    assert any("bad.yaml" in key for key in service.invalid_templates)
    assert "orphan" in service.invalid_templates


def test_yaml_safety_ignores_symlink_hidden_and_temp(tmp_path: Path) -> None:
    root = tmp_path / "prompt_library"
    _write(root / "generic_space.yaml", "id: generic_space\nname: Generic\nversion: '1.0'\n")
    _write(root / ".hidden.yaml", "id: hidden\nname: Hidden\nversion: '1.0'\n")
    _write(root / "temp.yaml.tmp", "id: temp\nname: Temp\nversion: '1.0'\n")
    _write(root / "unsafe.yaml", "!!python/object/apply:os.system ['echo bad']")
    outside = tmp_path / "outside.yaml"
    _write(outside, "id: outside\nname: Outside\nversion: '1.0'\n")
    try:
        (root / "link.yaml").symlink_to(outside)
    except OSError:
        pass

    service = PromptLibraryService(root)

    assert "hidden" not in service.templates
    assert "temp" not in service.templates
    assert "outside" not in service.templates
    assert any("unsafe.yaml" in key for key in service.invalid_templates)


def test_auto_detection_uses_project_sources_before_image_prompts(tmp_path: Path) -> None:
    service = _library(tmp_path)
    project = _project(topic="ブラックホールとは", title="宇宙の話", tags=["planet"])

    result = service.select_template(project, ["planet floating in space"], "auto", None)

    assert result.selected_template == "black_hole"
    assert "topic" in result.matched_sources
    assert result.candidate_scores["black_hole"] > result.candidate_scores["planet"]


def test_auto_detection_falls_back_and_manual_overrides(tmp_path: Path) -> None:
    service = _library(tmp_path)
    project = _project(topic="unknown")

    auto = service.select_template(project, ["nothing matched"], "auto", None)
    manual = service.select_template(project, ["black hole"], "manual", "planet")
    invalid = service.select_template(project, ["black hole"], "manual", "missing")

    assert auto.selected_template == "generic_space"
    assert manual.selected_template == "planet"
    assert invalid.selected_template == "generic_space"
    assert invalid.manual_template == "missing"


def test_prompt_optimizer_integration_applies_template_and_preserves_original(tmp_path: Path) -> None:
    provider = _FakeProvider()
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("ブラックホール", "宇宙", "60秒", 1, "prompt", "template", [], "", "")
    (project.path / "image_prompts.txt").write_text("black hole close-up", encoding="utf-8")
    service = ImageGenerationService(project_service, provider, ImageGenerationUsageService(tmp_path / "usage.json"), _library(tmp_path))

    result = service.build_prompt_optimization(
        "black hole close-up",
        1,
        ImageGenerationSettings(),
        project_service.load_project(project.path),
        ["black hole close-up"],
    )

    assert result.original_prompt == "black hole close-up"
    assert result.selected_template == "black_hole"
    assert "cinematic space documentary style" in result.optimized_prompt
    assert result.skipped_scene_reason == "conflicted_with_original"


def test_optimizer_off_applies_no_template_rules(tmp_path: Path) -> None:
    provider = _FakeProvider()
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("ブラックホール", "宇宙", "60秒", 1, "prompt", "template", [], "", "")
    service = ImageGenerationService(project_service, provider, ImageGenerationUsageService(tmp_path / "usage.json"), _library(tmp_path))

    result = service.build_prompt_optimization(
        "black hole",
        1,
        ImageGenerationSettings(prompt_optimizer_enabled=False),
        project_service.load_project(project.path),
        ["black hole"],
    )

    assert result.optimized_prompt == "black hole"
    assert result.selected_template == "black_hole"
    assert "template rules not applied" in " ".join(result.template_warnings)


def test_generation_saves_template_manifest_and_state(tmp_path: Path) -> None:
    provider = _FakeProvider()
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("ブラックホール", "宇宙", "60秒", 1, "prompt", "template", [], "", "")
    (project.path / "image_prompts.txt").write_text("black hole", encoding="utf-8")
    service = ImageGenerationService(project_service, provider, ImageGenerationUsageService(tmp_path / "usage.json"), _library(tmp_path))

    result = service.generate_missing(project_service.load_project(project.path), ImageGenerationSettings())

    assert result.status == "completed"
    reloaded = project_service.load_project(project.path)
    assert reloaded.image_generation["prompt_template_mode"] == "auto"
    assert reloaded.image_generation["resolved_prompt_template"] == "black_hole"
    assert reloaded.youtube_upload == {}
    assert reloaded.tiktok_upload == {}
    manifest = json.loads((project.path / "image_generation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["1"]["selected_template"] == "black_hole"
    assert manifest["1"]["matched_sources"]
    assert manifest["1"]["candidate_scores"]["black_hole"] > 0
    assert "Authorization" not in json.dumps(manifest)


class _FakeProvider(ImageGenerationProvider):
    def validate_configuration(self) -> ProviderStatus:
        return ProviderStatus(True, "Configured")

    def get_model_info(self, model: str) -> ModelInfo:
        return ModelInfo(
            provider="cloudflare_workers_ai",
            model="@cf/black-forest-labs/flux-1-schnell",
            prompt_max_length=2048,
            allowed_parameters={"prompt", "steps"},
            default_parameters={"steps": 4},
            portrait_note="test",
        )

    def validate_model_settings(self, settings: ImageGenerationSettings) -> None:
        return None

    def estimate_usage(self, request_count: int, settings: ImageGenerationSettings) -> UsageEstimate:
        return UsageEstimate(settings.provider, settings.model, request_count, settings.steps, None, "test")

    def generate_image(self, prompt: str, settings: ImageGenerationSettings, should_cancel=None) -> GeneratedImage:
        from PySide6.QtGui import QImage

        image = QImage(1080, 1920, QImage.Format_RGB32)
        image.fill(0x112233)
        out = Path(settings.provider + "_test.png")
        image.save(str(out), "PNG")
        try:
            data = out.read_bytes()
        finally:
            out.unlink(missing_ok=True)
        return GeneratedImage(data, "image/png", "request-id")
