from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Any, Callable
from uuid import uuid4


STORY_PROVIDER_SCHEMA_VERSION = "1.0"
DEFAULT_STORY_PROVIDER = "gemini"
DEFAULT_STORY_MODEL = "gemini-3.5-flash-lite"
DEFAULT_OPENAI_STORY_MODEL = "gpt-5.6-luna"
DEFAULT_GEMINI_STORY_MODEL = "gemini-3.5-flash-lite"
STORY_MODEL_PRESETS = {
    "Economy": "gpt-5.6-luna",
    "Balanced": "gpt-5.6-terra",
    "Quality": "gpt-5.6-sol",
}
GEMINI_STORY_MODEL_PRESETS = {
    "Economy": "gemini-3.5-flash-lite",
    "Balanced": "gemini-3.5-flash",
    "Quality": "gemini-3.6-flash",
}
GENERATION_STATUSES = {"pending", "running", "completed", "failed", "cancelled", "interrupted"}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class ProviderCapabilities:
    structured_outputs: bool = True
    json_schema: bool = True
    reasoning_effort: bool = True
    temperature: bool = False
    streaming: bool = False
    thinking_config: bool = False
    free_tier_guard: bool = False

    def to_dict(self) -> dict[str, bool]:
        return asdict(self)


@dataclass
class ConfigurationResult:
    configured: bool
    message: str = ""
    error_code: str = ""


@dataclass
class StoryGenerationRequest:
    project_id: str
    theme: str
    language: str = "ja"
    target_duration_seconds: float = 60.0
    min_scenes: int = 3
    max_scenes: int = 10
    model: str = DEFAULT_STORY_MODEL
    reasoning_effort: str = "low"
    max_output_tokens: int = 4096
    retry_count: int = 2
    timeout_seconds: int = 60
    provider_options: dict[str, Any] = field(default_factory=dict)

    def validate(self) -> None:
        if not self.theme.strip():
            raise ValueError("Themeが空のためStory生成を開始できません。")
        if len(self.theme) > 500:
            raise ValueError("Themeが長すぎます。500文字以内にしてください。")
        if self.min_scenes < 1 or self.max_scenes < self.min_scenes or self.max_scenes > 20:
            raise ValueError("Scene数の範囲が正しくありません。")
        if self.max_output_tokens < 512 or self.max_output_tokens > 20000:
            raise ValueError("Max output tokensは512〜20000の範囲で指定してください。")
        if self.retry_count < 0 or self.retry_count > 5:
            raise ValueError("Retry countは0〜5の範囲で指定してください。")
        if self.timeout_seconds < 10 or self.timeout_seconds > 600:
            raise ValueError("Timeoutは10〜600秒の範囲で指定してください。")

    def safe_snapshot(self, theme_hash: str) -> dict[str, object]:
        return {
            "theme_hash": theme_hash,
            "language": self.language,
            "target_duration_seconds": self.target_duration_seconds,
            "min_scenes": self.min_scenes,
            "max_scenes": self.max_scenes,
            "reasoning_effort": self.reasoning_effort,
            "max_output_tokens": self.max_output_tokens,
        }


@dataclass
class StoryCostEstimate:
    model: str
    estimated_cost_usd: float | None = None
    currency: str = "USD"
    method: str = "pre_request_estimate"
    pricing_snapshot: dict[str, Any] = field(default_factory=dict)
    message: str = ""


@dataclass
class StoryProviderMetrics:
    input_tokens: int | None = None
    cached_input_tokens: int | None = None
    cached_tokens: int | None = None
    output_tokens: int | None = None
    reasoning_tokens: int | None = None
    thoughts_tokens: int | None = None
    total_tokens: int | None = None
    estimated_cost_usd: float | None = None
    pricing_snapshot: dict[str, Any] = field(default_factory=dict)
    pricing_mode: str | None = None
    charge_expected: bool | None = None
    billing_status: str | None = None
    finish_reason: str | None = None
    response_id: str | None = None
    model_version: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class StoryGenerationResult:
    story: Any | None = None
    status: str = "completed"
    provider: str = ""
    provider_version: str = ""
    model: str = DEFAULT_STORY_MODEL
    metrics: StoryProviderMetrics = field(default_factory=StoryProviderMetrics)
    error_code: str | None = None
    error_message: str | None = None
    retry_count: int = 0
    repair_applied: bool = False
    repair_rules: list[str] = field(default_factory=list)
    free_tier_only: bool | None = None
    model_free_tier_status: str | None = None
    project_tier_status: str | None = None
    billing_status: str | None = None
    charge_risk: str | None = None
    local_usage_snapshot: dict[str, Any] = field(default_factory=dict)


@dataclass
class StoryGenerationState:
    schema_version: str = STORY_PROVIDER_SCHEMA_VERSION
    generation_id: str = field(default_factory=lambda: uuid4().hex)
    project_id: str = ""
    provider: str = DEFAULT_STORY_PROVIDER
    provider_version: str = ""
    model: str = DEFAULT_STORY_MODEL
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    updated_at: str = field(default_factory=now_iso)
    duration_ms: int | None = None
    attempt_count: int = 0
    retry_count: int = 0
    resume_from_generation_id: str | None = None
    last_error: str | None = None
    error_code: str | None = None
    request_snapshot: dict[str, object] = field(default_factory=dict)
    metrics: StoryProviderMetrics = field(default_factory=StoryProviderMetrics)
    repair_applied: bool = False
    repair_rules: list[str] = field(default_factory=list)
    free_tier_only: bool | None = None
    model_free_tier_status: str | None = None
    project_tier_status: str | None = None
    billing_status: str | None = None
    charge_risk: str | None = None
    local_usage_snapshot: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "generation_id": self.generation_id,
            "project_id": self.project_id,
            "provider": self.provider,
            "provider_version": self.provider_version,
            "model": self.model,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "updated_at": self.updated_at,
            "duration_ms": self.duration_ms,
            "attempt_count": self.attempt_count,
            "retry_count": self.retry_count,
            "resume_from_generation_id": self.resume_from_generation_id,
            "last_error": self.last_error,
            "error_code": self.error_code,
            "request_snapshot": self.request_snapshot,
            "metrics": self.metrics.to_dict(),
            "repair_applied": self.repair_applied,
            "repair_rules": self.repair_rules,
            "free_tier_only": self.free_tier_only,
            "model_free_tier_status": self.model_free_tier_status,
            "project_tier_status": self.project_tier_status,
            "billing_status": self.billing_status,
            "charge_risk": self.charge_risk,
            "local_usage_snapshot": self.local_usage_snapshot,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "StoryGenerationState":
        metrics_data = data.get("metrics", {}) if isinstance(data.get("metrics"), dict) else {}
        status = str(data.get("status") or "pending")
        if status == "running":
            status = "interrupted"
        if status not in GENERATION_STATUSES:
            status = "pending"
        return cls(
            schema_version=str(data.get("schema_version") or STORY_PROVIDER_SCHEMA_VERSION),
            generation_id=str(data.get("generation_id") or uuid4().hex),
            project_id=str(data.get("project_id") or ""),
            provider=str(data.get("provider") or DEFAULT_STORY_PROVIDER),
            provider_version=str(data.get("provider_version") or ""),
            model=str(data.get("model") or DEFAULT_STORY_MODEL),
            status=status,
            started_at=data.get("started_at") if isinstance(data.get("started_at"), str) else None,
            completed_at=data.get("completed_at") if isinstance(data.get("completed_at"), str) else None,
            updated_at=str(data.get("updated_at") or now_iso()),
            duration_ms=data.get("duration_ms") if isinstance(data.get("duration_ms"), int) else None,
            attempt_count=int(data.get("attempt_count", 0) or 0),
            retry_count=int(data.get("retry_count", 0) or 0),
            resume_from_generation_id=data.get("resume_from_generation_id") if isinstance(data.get("resume_from_generation_id"), str) else None,
            last_error=data.get("last_error") if isinstance(data.get("last_error"), str) else None,
            error_code=data.get("error_code") if isinstance(data.get("error_code"), str) else None,
            request_snapshot=dict(data.get("request_snapshot", {})) if isinstance(data.get("request_snapshot"), dict) else {},
            metrics=StoryProviderMetrics(**{k: metrics_data.get(k) for k in StoryProviderMetrics().__dict__.keys()}),
            repair_applied=bool(data.get("repair_applied", False)),
            repair_rules=[str(item) for item in data.get("repair_rules", [])] if isinstance(data.get("repair_rules"), list) else [],
            free_tier_only=data.get("free_tier_only") if isinstance(data.get("free_tier_only"), bool) else None,
            model_free_tier_status=data.get("model_free_tier_status") if isinstance(data.get("model_free_tier_status"), str) else None,
            project_tier_status=data.get("project_tier_status") if isinstance(data.get("project_tier_status"), str) else None,
            billing_status=data.get("billing_status") if isinstance(data.get("billing_status"), str) else None,
            charge_risk=data.get("charge_risk") if isinstance(data.get("charge_risk"), str) else None,
            local_usage_snapshot=dict(data.get("local_usage_snapshot", {})) if isinstance(data.get("local_usage_snapshot"), dict) else {},
        )


class CancellationToken:
    def __init__(self) -> None:
        self.cancel_requested = False

    def cancel(self) -> None:
        self.cancel_requested = True


ProgressCallback = Callable[[str, int], None]
