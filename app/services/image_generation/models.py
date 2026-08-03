from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path


IMAGE_GENERATION_STATUSES = [
    "pending",
    "validating",
    "generating",
    "partially_completed",
    "completed",
    "cancelled",
    "failed",
]


class ImageGenerationError(Exception):
    """User-facing image generation error with a safe retry classification."""

    def __init__(self, message: str, code: str = "image_generation_error", retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.retryable = retryable


class ProviderConfigurationError(ImageGenerationError):
    """Raised before any API request when provider credentials/settings are missing."""


class ImageGenerationCancelled(ImageGenerationError):
    """Raised when a generation run is cancelled between requests."""


@dataclass(frozen=True)
class ImageGenerationSettings:
    provider: str = "cloudflare_workers_ai"
    model: str = "@cf/black-forest-labs/flux-1-schnell"
    steps: int = 4
    max_images_per_run: int = 8
    max_retries_per_image: int = 2
    daily_request_limit: int = 20
    per_project_image_limit: int = 40
    max_response_bytes: int = 12 * 1024 * 1024
    target_width: int = 1080
    target_height: int = 1920
    prompt_optimizer_enabled: bool = True
    prompt_template_mode: str = "auto"
    manual_prompt_template: str | None = None


@dataclass(frozen=True)
class ProviderStatus:
    configured: bool
    message: str


@dataclass(frozen=True)
class ModelInfo:
    provider: str
    model: str
    prompt_max_length: int
    allowed_parameters: set[str]
    default_parameters: dict[str, object]
    portrait_note: str
    license_url: str = ""


@dataclass(frozen=True)
class UsageEstimate:
    provider: str
    model: str
    request_count: int
    steps: int
    estimated_neurons: float | None = None
    note: str = ""


@dataclass(frozen=True)
class GeneratedImage:
    image_bytes: bytes
    content_type: str
    request_id: str = ""


@dataclass
class ImageGenerationResult:
    status: str
    generated_indices: list[int] = field(default_factory=list)
    failed_indices: list[int] = field(default_factory=list)
    skipped_existing_indices: list[int] = field(default_factory=list)
    completed_count: int = 0
    last_error: str = ""
    manifest_path: Path | None = None
