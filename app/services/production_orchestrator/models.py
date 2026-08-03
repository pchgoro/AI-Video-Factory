from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


RUN_STATUSES = {
    "pending",
    "running",
    "succeeded",
    "partially_succeeded",
    "failed",
    "cancelled",
    "interrupted",
}

STEP_STATUSES = {
    "pending",
    "running",
    "succeeded",
    "failed",
    "skipped",
    "cancelled",
    "blocked",
    "interrupted",
}

PRODUCTION_STEPS = [
    "validate_story",
    "export_story",
    "generate_images",
    "generate_voice",
    "generate_subtitles",
    "render_video",
    "upload_youtube",
    "upload_tiktok",
]

STEP_DISPLAY_NAMES = {
    "validate_story": "Story validation",
    "export_story": "Export Story",
    "generate_images": "Image generation",
    "generate_voice": "VOICEVOX",
    "generate_subtitles": "Subtitle generation",
    "render_video": "Video render",
    "upload_youtube": "YouTube PRIVATE upload",
    "upload_tiktok": "TikTok Upload Content",
}


def now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")


@dataclass
class ProductionOptions:
    export_story: bool = True
    generate_images: bool = True
    generate_voice: bool = True
    generate_subtitles: bool = True
    render_video: bool = True
    upload_youtube: bool = False
    upload_tiktok: bool = False
    reuse_existing_artifacts: bool = True
    continue_independent_upload_steps: bool = True

    def is_enabled(self, step_id: str) -> bool:
        mapping = {
            "validate_story": True,
            "export_story": self.export_story,
            "generate_images": self.generate_images,
            "generate_voice": self.generate_voice,
            "generate_subtitles": self.generate_subtitles,
            "render_video": self.render_video,
            "upload_youtube": self.upload_youtube,
            "upload_tiktok": self.upload_tiktok,
        }
        return bool(mapping.get(step_id, False))

    @classmethod
    def from_dict(cls, data: dict[str, Any] | None) -> "ProductionOptions":
        if not isinstance(data, dict):
            return cls()
        values = {field_name: bool(data.get(field_name, getattr(cls(), field_name))) for field_name in cls().__dict__}
        return cls(**values)

    def to_dict(self) -> dict[str, bool]:
        return {
            "export_story": self.export_story,
            "generate_images": self.generate_images,
            "generate_voice": self.generate_voice,
            "generate_subtitles": self.generate_subtitles,
            "render_video": self.render_video,
            "upload_youtube": self.upload_youtube,
            "upload_tiktok": self.upload_tiktok,
            "reuse_existing_artifacts": self.reuse_existing_artifacts,
            "continue_independent_upload_steps": self.continue_independent_upload_steps,
        }


@dataclass
class ProductionStep:
    step_id: str
    display_name: str
    enabled: bool = True
    required: bool = True
    status: str = "pending"
    started_at: str | None = None
    completed_at: str | None = None
    attempt_count: int = 0
    retryable: bool = False
    progress: int = 0
    message: str = ""
    last_error: str | None = None
    error_code: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, step_id: str, enabled: bool = True) -> "ProductionStep":
        return cls(step_id=step_id, display_name=STEP_DISPLAY_NAMES.get(step_id, step_id), enabled=enabled)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionStep":
        step = cls.create(str(data.get("step_id") or ""), bool(data.get("enabled", True)))
        step.display_name = str(data.get("display_name") or step.display_name)
        step.required = bool(data.get("required", True))
        step.status = str(data.get("status") or "pending")
        if step.status not in STEP_STATUSES:
            step.status = "pending"
        step.started_at = data.get("started_at") if isinstance(data.get("started_at"), str) else None
        step.completed_at = data.get("completed_at") if isinstance(data.get("completed_at"), str) else None
        step.attempt_count = int(data.get("attempt_count", 0) or 0)
        step.retryable = bool(data.get("retryable", False))
        step.progress = max(0, min(100, int(data.get("progress", 0) or 0)))
        step.message = str(data.get("message") or "")
        step.last_error = str(data.get("last_error")) if data.get("last_error") is not None else None
        step.error_code = str(data.get("error_code")) if data.get("error_code") is not None else None
        outputs = data.get("outputs", {})
        step.outputs = outputs if isinstance(outputs, dict) else {}
        return step

    def to_dict(self) -> dict[str, Any]:
        return {
            "step_id": self.step_id,
            "display_name": self.display_name,
            "enabled": self.enabled,
            "required": self.required,
            "status": self.status,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "attempt_count": self.attempt_count,
            "retryable": self.retryable,
            "progress": max(0, min(100, int(self.progress))),
            "message": self.message,
            "last_error": self.last_error,
            "error_code": self.error_code,
            "outputs": self.outputs,
        }


@dataclass
class StepResult:
    status: str
    message: str = ""
    progress: int = 100
    retryable: bool = False
    error_code: str | None = None
    outputs: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def succeeded(cls, message: str = "", outputs: dict[str, Any] | None = None) -> "StepResult":
        return cls("succeeded", message, 100, False, None, outputs or {})

    @classmethod
    def skipped(cls, message: str = "", outputs: dict[str, Any] | None = None) -> "StepResult":
        return cls("skipped", message, 100, False, None, outputs or {"reused": True})

    @classmethod
    def failed(cls, message: str, error_code: str = "step_failed", retryable: bool = False) -> "StepResult":
        return cls("failed", message, 0, retryable, error_code, {})


@dataclass
class PreflightIssue:
    severity: str
    code: str
    message: str
    step_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {"severity": self.severity, "code": self.code, "message": self.message, "step_id": self.step_id}


@dataclass
class PreflightResult:
    issues: list[PreflightIssue] = field(default_factory=list)
    artifact_status: dict[str, dict[str, Any]] = field(default_factory=dict)

    @property
    def has_errors(self) -> bool:
        return any(issue.severity == "error" for issue in self.issues)

    @property
    def warnings(self) -> list[PreflightIssue]:
        return [issue for issue in self.issues if issue.severity == "warning"]

    def add(self, severity: str, code: str, message: str, step_id: str | None = None) -> None:
        self.issues.append(PreflightIssue(severity, code, message, step_id))

    def to_dict(self) -> dict[str, Any]:
        return {
            "issues": [issue.to_dict() for issue in self.issues],
            "artifact_status": self.artifact_status,
        }


@dataclass
class ProductionRun:
    schema_version: str = "1.0"
    run_id: str = ""
    project_id: str = ""
    status: str = "pending"
    mode: str = "normal"
    created_at: str = field(default_factory=now_iso)
    started_at: str | None = None
    updated_at: str = field(default_factory=now_iso)
    completed_at: str | None = None
    cancel_requested: bool = False
    current_step: str | None = None
    steps: list[ProductionStep] = field(default_factory=list)
    options: dict[str, Any] = field(default_factory=dict)
    input_snapshot: dict[str, Any] = field(default_factory=dict)
    summary: dict[str, int] = field(default_factory=dict)
    preflight: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(cls, run_id: str, project_id: str, mode: str, options: ProductionOptions) -> "ProductionRun":
        steps = [ProductionStep.create(step_id, options.is_enabled(step_id)) for step_id in PRODUCTION_STEPS]
        run = cls(run_id=run_id, project_id=project_id, mode=mode, options=options.to_dict(), steps=steps)
        run.recalculate_summary()
        return run

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ProductionRun":
        steps_data = data.get("steps", [])
        steps = [ProductionStep.from_dict(item) for item in steps_data if isinstance(item, dict)]
        run = cls(
            schema_version=str(data.get("schema_version") or "1.0"),
            run_id=str(data.get("run_id") or ""),
            project_id=str(data.get("project_id") or ""),
            status=str(data.get("status") or "pending"),
            mode=str(data.get("mode") or "normal"),
            created_at=str(data.get("created_at") or now_iso()),
            started_at=data.get("started_at") if isinstance(data.get("started_at"), str) else None,
            updated_at=str(data.get("updated_at") or now_iso()),
            completed_at=data.get("completed_at") if isinstance(data.get("completed_at"), str) else None,
            cancel_requested=bool(data.get("cancel_requested", False)),
            current_step=data.get("current_step") if isinstance(data.get("current_step"), str) else None,
            steps=steps,
            options=data.get("options", {}) if isinstance(data.get("options"), dict) else {},
            input_snapshot=data.get("input_snapshot", {}) if isinstance(data.get("input_snapshot"), dict) else {},
            summary=data.get("summary", {}) if isinstance(data.get("summary"), dict) else {},
            preflight=data.get("preflight", {}) if isinstance(data.get("preflight"), dict) else {},
        )
        if run.status not in RUN_STATUSES:
            run.status = "pending"
        if run.status == "running":
            run.status = "interrupted"
            for step in run.steps:
                if step.status == "running":
                    step.status = "interrupted"
                    step.retryable = True
                    step.message = "Interrupted before completion."
        run.recalculate_summary()
        return run

    def step(self, step_id: str) -> ProductionStep | None:
        return next((step for step in self.steps if step.step_id == step_id), None)

    def recalculate_summary(self) -> None:
        counts = {"succeeded": 0, "failed": 0, "skipped": 0, "cancelled": 0, "blocked": 0}
        for step in self.steps:
            if step.status in counts:
                counts[step.status] += 1
        self.summary = counts

    def touch(self) -> None:
        self.updated_at = now_iso()

    def to_dict(self) -> dict[str, Any]:
        self.recalculate_summary()
        return {
            "schema_version": self.schema_version,
            "run_id": self.run_id,
            "project_id": self.project_id,
            "status": self.status,
            "mode": self.mode,
            "created_at": self.created_at,
            "started_at": self.started_at,
            "updated_at": self.updated_at,
            "completed_at": self.completed_at,
            "cancel_requested": self.cancel_requested,
            "current_step": self.current_step,
            "steps": [step.to_dict() for step in self.steps],
            "options": self.options,
            "input_snapshot": self.input_snapshot,
            "summary": self.summary,
            "preflight": self.preflight,
        }
