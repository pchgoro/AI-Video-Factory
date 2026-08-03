from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest
from PySide6.QtGui import QImage

from config import AppPaths
from models import ProjectInfo
from services.image_generation import ImageGenerationService, ImageGenerationSettings
from services.image_generation.models import GeneratedImage, ImageGenerationError, ModelInfo, ProviderStatus, UsageEstimate
from services.image_generation.provider import ImageGenerationProvider
from services.image_generation.usage_service import ImageGenerationUsageService
from services.project_service import ProjectService


class FakeProvider(ImageGenerationProvider):
    def __init__(self, failures: list[ImageGenerationError] | None = None) -> None:
        self.calls: list[str] = []
        self.failures = failures or []

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
        if settings.steps < 1 or settings.steps > 8:
            raise ImageGenerationError("invalid steps", "invalid_parameter", False)

    def estimate_usage(self, request_count: int, settings: ImageGenerationSettings) -> UsageEstimate:
        return UsageEstimate(settings.provider, settings.model, request_count, settings.steps, request_count * 43.2, "test")

    def generate_image(self, prompt: str, settings: ImageGenerationSettings, should_cancel=None) -> GeneratedImage:
        self.calls.append(prompt)
        if self.failures:
            raise self.failures.pop(0)
        return GeneratedImage(_png_bytes(), "image/png", "req123")


def _png_bytes(width: int = 320, height: int = 320) -> bytes:
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(0x336699)
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as file:
        path = Path(file.name)
    try:
        image.save(str(path), "PNG")
        return path.read_bytes()
    finally:
        path.unlink(missing_ok=True)


def _project(tmp_path: Path, image_count: int = 3, prompts: int = 3) -> tuple[ProjectService, ProjectInfo]:
    paths = AppPaths(tmp_path)
    paths.ensure()
    service = ProjectService(paths)
    project = service.create_project("topic", "genre", "60秒", image_count, "prompt", "template", [], "series", "category")
    (project.path / "image_prompts.txt").write_text("\n\n".join(f"prompt {i}" for i in range(1, prompts + 1)), encoding="utf-8")
    return service, service.load_project(project.path)


def _service(tmp_path: Path, provider: FakeProvider | None = None) -> tuple[ImageGenerationService, FakeProvider]:
    project_service, _ = _project(tmp_path)
    fake = provider or FakeProvider()
    usage = ImageGenerationUsageService(tmp_path / "image_generation_usage.json")
    return ImageGenerationService(project_service, fake, usage), fake


def test_generates_missing_images_and_saves_state_manifest(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path, image_count=3, prompts=3)
    fake = FakeProvider()
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))

    result = service.generate_missing(project, ImageGenerationSettings())

    assert result.status == "completed"
    assert [path.name for path in sorted((project.path / "images").glob("*.png"))] == ["001.png", "002.png", "003.png"]
    generated_image = QImage(str(project.path / "images" / "001.png"))
    assert generated_image.width() == 1080
    assert generated_image.height() == 1920
    reloaded = project_service.load_project(project.path)
    assert reloaded.image_generation["provider"] == "cloudflare_workers_ai"
    assert reloaded.image_generation["model"] == "@cf/black-forest-labs/flux-1-schnell"
    assert reloaded.image_generation["completed_count"] == 3
    assert reloaded.youtube_upload == {}
    assert reloaded.tiktok_upload == {}
    manifest = json.loads((project.path / "image_generation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["1"]["source_prompt"] == "prompt 1"
    assert manifest["1"]["original_prompt"] == "prompt 1"
    assert manifest["1"]["optimized_prompt"] == fake.calls[0]
    assert manifest["1"]["optimizer_enabled"] is True
    assert manifest["1"]["was_truncated"] is False
    assert "Authorization" not in json.dumps(manifest)


def test_existing_valid_images_are_skipped(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path, image_count=3, prompts=3)
    images_dir = project.path / "images"
    images_dir.mkdir(exist_ok=True)
    (images_dir / "001.png").write_bytes(_png_bytes(1080, 1920))
    fake = FakeProvider()
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))

    result = service.generate_missing(project, ImageGenerationSettings())

    assert result.skipped_existing_indices == [1]
    assert result.generated_indices == [2, 3]
    assert len(fake.calls) == 2


def test_optimizer_off_sends_original_prompt_exactly(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path, image_count=1, prompts=1)
    (project.path / "image_prompts.txt").write_text("No Text custom prompt", encoding="utf-8")
    fake = FakeProvider()
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))

    result = service.generate_missing(project_service.load_project(project.path), ImageGenerationSettings(prompt_optimizer_enabled=False))

    assert result.status == "completed"
    assert fake.calls == ["No Text custom prompt"]
    manifest = json.loads((project.path / "image_generation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["1"]["optimized_prompt"] == "No Text custom prompt"
    assert manifest["1"]["optimizer_enabled"] is False


def test_missing_prompts_stop_before_api_call(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path, image_count=5, prompts=3)
    fake = FakeProvider()
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))

    with pytest.raises(ImageGenerationError, match="不足"):
        service.generate_missing(project, ImageGenerationSettings())

    assert fake.calls == []


def test_prompt_too_long_stops_before_api_call(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path, image_count=3, prompts=3)
    (project.path / "image_prompts.txt").write_text("x" * 2100 + "\n\nok\n\nok", encoding="utf-8")
    fake = FakeProvider()
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))

    with pytest.raises(ImageGenerationError, match="上限"):
        service.generate_missing(project_service.load_project(project.path), ImageGenerationSettings())

    assert fake.calls == []


def test_optimizer_compacts_added_terms_before_api_call(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path, image_count=1, prompts=1)
    original = "ブラックホール"
    (project.path / "image_prompts.txt").write_text(original, encoding="utf-8")
    fake = FakeProvider()
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))
    fake.get_model_info = lambda model: ModelInfo(  # type: ignore[method-assign]
        provider="cloudflare_workers_ai",
        model="@cf/black-forest-labs/flux-1-schnell",
        prompt_max_length=len(original) + 55,
        allowed_parameters={"prompt", "steps"},
        default_parameters={"steps": 4},
        portrait_note="test",
    )

    result = service.generate_missing(project_service.load_project(project.path), ImageGenerationSettings())

    assert result.status == "completed"
    assert fake.calls[0].startswith(original)
    assert len(fake.calls[0]) <= len(original) + 55
    manifest = json.loads((project.path / "image_generation_manifest.json").read_text(encoding="utf-8"))
    assert manifest["1"]["was_compacted"] is True
    assert manifest["1"]["removed_rules"]


@pytest.mark.parametrize("count", [3, 4, 5, 6, 8])
def test_project_image_count_is_respected(tmp_path: Path, count: int) -> None:
    project_service, project = _project(tmp_path, image_count=count, prompts=count)
    fake = FakeProvider()
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))

    result = service.generate_missing(project, ImageGenerationSettings())

    assert result.completed_count == count
    assert len(fake.calls) == count


def test_transient_error_retries_then_succeeds(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path, image_count=1, prompts=1)
    fake = FakeProvider([ImageGenerationError("temporary", "rate_limited", True)])
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))

    result = service.generate_missing(project, ImageGenerationSettings(max_retries_per_image=1))

    assert result.status == "completed"
    assert len(fake.calls) == 2


def test_non_retryable_error_preserves_partial_success(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path, image_count=2, prompts=2)
    fake = FakeProvider([ImageGenerationError("bad token", "auth_or_permission_error", False)])
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))

    result = service.generate_missing(project, ImageGenerationSettings())

    assert result.status == "failed"
    assert result.failed_indices == [1, 2]
    assert not (project.path / "images" / "001.png").exists()
    reloaded = project_service.load_project(project.path)
    assert reloaded.youtube_upload == {}
    assert reloaded.tiktok_upload == {}


def test_daily_limit_blocks_before_api_call(tmp_path: Path) -> None:
    project_service, project = _project(tmp_path, image_count=3, prompts=3)
    fake = FakeProvider()
    service = ImageGenerationService(project_service, fake, ImageGenerationUsageService(tmp_path / "usage.json"))

    with pytest.raises(ImageGenerationError, match="上限"):
        service.generate_missing(project, ImageGenerationSettings(daily_request_limit=2))

    assert fake.calls == []
