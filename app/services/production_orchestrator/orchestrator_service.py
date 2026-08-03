from __future__ import annotations

import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Callable

from models import AppSettings, ProjectInfo
from services.image_generation.models import ImageGenerationSettings
from services.production_orchestrator.artifact_service import ArtifactService
from services.production_orchestrator.dependency import enabled_steps, execution_order, unmet_dependencies, validate_no_cycles
from services.production_orchestrator.lock import ProductionLockError, ProductionRunLock
from services.production_orchestrator.models import ProductionOptions, ProductionRun, StepResult, now_iso
from services.production_orchestrator.preflight_service import ProductionPreflightService
from services.production_orchestrator.run_repository import ProductionRunRepository
from services.production_orchestrator.steps import ProductionStepAdapter, StepContext
from services.project_service import ProjectService


ProgressCallback = Callable[[dict[str, object]], None]
CancelCallback = Callable[[], bool]


class ProductionOrchestratorService:
    def __init__(
        self,
        project_service: ProjectService,
        settings: AppSettings,
        preflight_service: ProductionPreflightService,
        adapters: dict[str, ProductionStepAdapter],
        repository: ProductionRunRepository | None = None,
        artifact_service: ArtifactService | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        validate_no_cycles()
        self.project_service = project_service
        self.settings = settings
        self.preflight_service = preflight_service
        self.adapters = adapters
        self.repository = repository or ProductionRunRepository()
        self.artifact_service = artifact_service or ArtifactService(settings)
        self.logger = logger or logging.getLogger("ai_video_factory.production")

    def load_run(self, project: ProjectInfo) -> ProductionRun | None:
        return self.repository.load(project.path)

    def preflight(self, project: ProjectInfo, options: ProductionOptions | None = None, dry_run: bool = False):
        options = options or ProductionOptions()
        return self.preflight_service.check(project, options, self.image_settings(), dry_run=dry_run)

    def start(
        self,
        project: ProjectInfo,
        options: ProductionOptions | None = None,
        mode: str = "normal",
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
    ) -> ProductionRun:
        options = options or ProductionOptions()
        run = ProductionRun.create(uuid.uuid4().hex, project.name, mode, options)
        return self._execute_run(project, run, progress_callback, should_cancel, require_preflight=(mode == "normal"))

    def resume(
        self,
        project: ProjectInfo,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
    ) -> ProductionRun:
        run = self.repository.load(project.path)
        if run is None:
            raise ValueError("No production_run.json exists.")
        if run.status not in {"interrupted", "partially_succeeded", "failed", "cancelled"}:
            raise ValueError("This production run is not resumable.")
        options = ProductionOptions.from_dict(run.options)
        refreshed = self.project_service.load_project(project.path)
        artifacts = self.artifact_service.artifact_status(refreshed, run.input_snapshot)
        for step in run.steps:
            if step.status in {"running", "interrupted"}:
                step.status = "pending"
                step.retryable = True
            if step.status in {"succeeded", "skipped"}:
                artifact_key = self._artifact_key_for_step(step.step_id)
                if artifact_key and artifacts.get(artifact_key, {}).get("state") in {"missing", "invalid", "stale"}:
                    step.status = "pending"
                    step.retryable = True
                    step.message = "Artifact changed after interruption."
            step.enabled = options.is_enabled(step.step_id)
        run.status = "pending"
        run.cancel_requested = False
        run.completed_at = None
        self.repository.save(project.path, run, force=True)
        return self._execute_run(project, run, progress_callback, should_cancel, require_preflight=True)

    def retry_failed_step(
        self,
        project: ProjectInfo,
        progress_callback: ProgressCallback | None = None,
        should_cancel: CancelCallback | None = None,
    ) -> ProductionRun:
        run = self.repository.load(project.path)
        if run is None:
            raise ValueError("No production_run.json exists.")
        failed = next((step for step in run.steps if step.status in {"failed", "interrupted", "cancelled"} and step.retryable), None)
        if failed is None:
            raise ValueError("No retryable failed step exists.")
        if failed.attempt_count >= 3:
            raise ValueError("Retry attempt limit reached.")
        for step in run.steps:
            if step.step_id == failed.step_id:
                step.status = "pending"
                step.last_error = None
                step.error_code = None
                step.progress = 0
            elif step.status == "blocked":
                step.status = "pending"
        run.status = "pending"
        run.cancel_requested = False
        run.completed_at = None
        self.repository.save(project.path, run, force=True)
        return self._execute_run(project, run, progress_callback, should_cancel, require_preflight=True)

    def request_cancel(self, project: ProjectInfo) -> None:
        run = self.repository.load(project.path)
        if run is None:
            return
        run.cancel_requested = True
        self.repository.save(project.path, run, force=True)

    def image_settings(self) -> ImageGenerationSettings:
        return ImageGenerationSettings(
            provider=self.settings.image_generation_provider,
            model=self.settings.image_generation_model,
            steps=self.settings.image_generation_steps,
            max_images_per_run=self.settings.image_generation_max_images_per_run,
            max_retries_per_image=self.settings.image_generation_max_retries_per_image,
            daily_request_limit=self.settings.image_generation_daily_request_limit,
            per_project_image_limit=self.settings.image_generation_project_limit,
            target_width=self.settings.output_width,
            target_height=self.settings.output_height,
            prompt_optimizer_enabled=self.settings.image_prompt_optimizer_enabled,
            prompt_template_mode=self.settings.image_prompt_template_mode,
            manual_prompt_template=self.settings.image_manual_prompt_template,
        )

    def _execute_run(
        self,
        project: ProjectInfo,
        run: ProductionRun,
        progress_callback: ProgressCallback | None,
        should_cancel: CancelCallback | None,
        require_preflight: bool,
    ) -> ProductionRun:
        lock = ProductionRunLock(project.path, run.run_id)
        try:
            lock.acquire()
        except ProductionLockError:
            raise
        try:
            project = self.project_service.load_project(project.path)
            options = ProductionOptions.from_dict(run.options)
            preflight = self.preflight(project, options, dry_run=(run.mode == "dry_run"))
            run.preflight = preflight.to_dict()
            run.input_snapshot = self.artifact_service.snapshot(project)
            if require_preflight and preflight.has_errors:
                run.status = "failed"
                run.completed_at = now_iso()
                self._block_pending(run, "Preflight errors must be fixed before Normal Run.")
                self.repository.save(project.path, run, force=True)
                self._emit(progress_callback, run)
                return run
            run.status = "running"
            run.started_at = run.started_at or now_iso()
            self.repository.save(project.path, run, force=True)
            self.logger.info("run start run_id=%s project_id=%s mode=%s", run.run_id, project.name, run.mode)

            context = StepContext(
                project=project,
                settings=self.settings,
                image_settings=self.image_settings(),
                options=options,
                artifact_service=self.artifact_service,
                input_snapshot=run.input_snapshot,
                progress_callback=lambda data: self._step_progress(project.path, run, data, progress_callback),
                should_cancel=lambda: run.cancel_requested or (should_cancel and should_cancel()),
                dry_run=(run.mode == "dry_run"),
            )
            for step_id in execution_order():
                step = run.step(step_id)
                if step is None:
                    continue
                if run.cancel_requested or (should_cancel and should_cancel()):
                    step.status = "cancelled" if step.status == "pending" else step.status
                    run.status = "cancelled"
                    break
                if not step.enabled:
                    step.status = "skipped"
                    step.progress = 100
                    step.message = "Step disabled."
                    step.completed_at = now_iso()
                    self.repository.save(project.path, run, force=True)
                    self._emit(progress_callback, run)
                    continue
                if step.status in {"succeeded", "skipped"}:
                    continue
                unmet = unmet_dependencies(run, step_id)
                if unmet:
                    step.status = "blocked"
                    step.last_error = "Blocked by unmet dependencies: " + ", ".join(unmet)
                    step.completed_at = now_iso()
                    self.repository.save(project.path, run, force=True)
                    self._emit(progress_callback, run)
                    continue
                result = self._run_step(project.path, run, step_id, context, progress_callback)
                if result.status == "failed" and step_id in {"upload_youtube", "upload_tiktok"} and options.continue_independent_upload_steps:
                    continue
                if result.status in {"failed", "cancelled"}:
                    self._block_downstream(run, step_id)
                    break
                project = self.project_service.load_project(project.path)
                context.project = project
                if step_id == "export_story":
                    run.input_snapshot = self.artifact_service.snapshot(project)
                    context.input_snapshot = run.input_snapshot
            self._finish_run(run)
            self.repository.save(project.path, run, force=True)
            self._emit(progress_callback, run)
            self.logger.info("run completion run_id=%s status=%s", run.run_id, run.status)
            return run
        finally:
            lock.release()

    def _run_step(
        self,
        project_dir: Path,
        run: ProductionRun,
        step_id: str,
        context: StepContext,
        progress_callback: ProgressCallback | None,
    ) -> StepResult:
        step = run.step(step_id)
        if step is None:
            return StepResult.failed("Step not found.", "step_not_found", False)
        adapter = self.adapters.get(step_id)
        if adapter is None:
            result = StepResult.failed("Step adapter not configured.", "adapter_missing", False)
        else:
            step.status = "running"
            step.started_at = step.started_at or now_iso()
            step.attempt_count += 1
            step.progress = 0
            step.message = "Running."
            run.current_step = step_id
            self.repository.save(project_dir, run, force=True)
            self._emit(progress_callback, run)
            self.logger.info("step start run_id=%s step=%s", run.run_id, step_id)
            try:
                result = adapter.run(context)
            except Exception as exc:
                result = StepResult.failed(adapter.sanitize_error(exc), exc.__class__.__name__, True)
        step.status = result.status
        step.progress = max(0, min(100, int(result.progress)))
        step.retryable = result.retryable
        step.message = result.message
        step.error_code = result.error_code
        step.last_error = result.message if result.status == "failed" else None
        step.outputs = self._safe_outputs(result.outputs)
        step.completed_at = now_iso()
        self.repository.save(project_dir, run, force=True)
        self._emit(progress_callback, run)
        if result.status in {"succeeded", "skipped"}:
            self.logger.info("step success run_id=%s step=%s status=%s", run.run_id, step_id, result.status)
        else:
            self.logger.warning("step failure run_id=%s step=%s status=%s error=%s", run.run_id, step_id, result.status, result.error_code)
        return result

    def _step_progress(self, project_dir: Path, run: ProductionRun, data: dict[str, object], progress_callback: ProgressCallback | None) -> None:
        step_id = str(data.get("step_id") or run.current_step or "")
        step = run.step(step_id)
        if step is not None:
            if data.get("progress") is not None:
                step.progress = max(0, min(100, int(data.get("progress", 0) or 0)))
            if data.get("message"):
                step.message = str(data.get("message"))
        self.repository.save(project_dir, run)
        self._emit(progress_callback, run)

    def _finish_run(self, run: ProductionRun) -> None:
        run.recalculate_summary()
        statuses = [step.status for step in run.steps if step.enabled]
        if run.cancel_requested or any(status == "cancelled" for status in statuses):
            run.status = "cancelled"
        elif any(status == "failed" for status in statuses):
            run.status = "partially_succeeded" if any(status in {"succeeded", "skipped"} for status in statuses) else "failed"
        elif any(status == "blocked" for status in statuses):
            run.status = "partially_succeeded" if any(status in {"succeeded", "skipped"} for status in statuses) else "failed"
        else:
            run.status = "succeeded"
        run.current_step = None
        run.completed_at = now_iso()

    def _block_downstream(self, run: ProductionRun, failed_step_id: str) -> None:
        seen_failed = False
        for step in run.steps:
            if step.step_id == failed_step_id:
                seen_failed = True
                continue
            if seen_failed and step.enabled and step.status == "pending":
                step.status = "blocked"
                step.message = f"Blocked after {failed_step_id}."
                step.completed_at = now_iso()

    def _block_pending(self, run: ProductionRun, message: str) -> None:
        for step in run.steps:
            if step.status == "pending":
                step.status = "blocked"
                step.message = message
                step.completed_at = now_iso()

    def _artifact_key_for_step(self, step_id: str) -> str | None:
        return {
            "export_story": "factory_export",
            "generate_images": "images",
            "generate_voice": "audio",
            "generate_subtitles": "subtitles",
            "render_video": "video",
            "upload_youtube": "youtube",
            "upload_tiktok": "tiktok",
        }.get(step_id)

    def _safe_outputs(self, outputs: dict) -> dict:
        blocked = {"access_token", "refresh_token", "client_secret", "upload_url", "raw_response", "base64"}
        safe = {}
        for key, value in (outputs or {}).items():
            if key in blocked:
                continue
            if isinstance(value, (str, int, float, bool)) or value is None:
                safe[key] = value
            elif isinstance(value, list):
                safe[key] = value[:100]
            elif isinstance(value, dict):
                safe[key] = {str(k): v for k, v in list(value.items())[:100] if str(k) not in blocked}
        return safe

    def _emit(self, progress_callback: ProgressCallback | None, run: ProductionRun) -> None:
        if progress_callback:
            progress_callback(run.to_dict())
