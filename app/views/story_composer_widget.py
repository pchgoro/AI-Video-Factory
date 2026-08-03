from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QComboBox,
    QCheckBox,
    QDoubleSpinBox,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models import AppSettings, ProjectInfo
from services.project_service import ProjectService
from services.story_composer import FactoryExportPreview, Story, StoryService, StoryValidationError, ValidationResult
from services.story_provider import CancellationToken, GEMINI_STORY_MODEL_PRESETS, StoryGenerationRequest, STORY_MODEL_PRESETS
from services.story_provider.gemini_model_catalog import get_gemini_model_metadata


class StoryGenerationWorker(QObject):
    progress = Signal(str, int)
    finished = Signal(object)

    def __init__(
        self,
        story_service: StoryService,
        project: ProjectInfo,
        request: StoryGenerationRequest,
        provider_id: str,
        cancellation_token: CancellationToken,
        resume_from_generation_id: str | None = None,
    ) -> None:
        super().__init__()
        self.story_service = story_service
        self.project = project
        self.request = request
        self.provider_id = provider_id
        self.cancellation_token = cancellation_token
        self.resume_from_generation_id = resume_from_generation_id

    def run(self) -> None:
        result = self.story_service.generate_story(
            self.project,
            self.request,
            provider_id=self.provider_id,
            resume_from_generation_id=self.resume_from_generation_id,
            cancellation_token=self.cancellation_token,
            progress_callback=lambda message, progress: self.progress.emit(message, progress),
        )
        self.finished.emit(result)


class StoryComposerWidget(QWidget):
    exported = Signal(Path)

    def __init__(
        self,
        project_service: ProjectService,
        story_service: StoryService,
        settings: AppSettings | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.project_service = project_service
        self.story_service = story_service
        self.settings = settings
        self.project: ProjectInfo | None = None
        self.story: Story | None = None
        self._generation_thread: QThread | None = None
        self._generation_worker: StoryGenerationWorker | None = None
        self._generation_token: CancellationToken | None = None
        self._build_ui()
        self.apply_settings(settings)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        settings_box = QGroupBox("Story Composer")
        grid = QGridLayout(settings_box)
        self.theme_input = QLineEdit()
        self.provider_box = QComboBox()
        self.provider_box.addItem("Manual Prompt", "manual_prompt")
        self.status_label = QLabel("draft")
        self.scene_count_box = QSpinBox()
        self.scene_count_box.setRange(3, 20)
        self.scene_count_box.setValue(5)
        self.duration_box = QDoubleSpinBox()
        self.duration_box.setRange(5.0, 600.0)
        self.duration_box.setDecimals(1)
        self.duration_box.setValue(60.0)
        self.duration_box.setSuffix(" sec")
        self.last_export_label = QLabel("-")

        grid.addWidget(QLabel("Theme"), 0, 0)
        grid.addWidget(self.theme_input, 0, 1)
        grid.addWidget(QLabel("Provider"), 0, 2)
        grid.addWidget(self.provider_box, 0, 3)
        grid.addWidget(QLabel("Status"), 1, 0)
        grid.addWidget(self.status_label, 1, 1)
        grid.addWidget(QLabel("Scene Count"), 1, 2)
        grid.addWidget(self.scene_count_box, 1, 3)
        grid.addWidget(QLabel("Estimated Duration"), 2, 0)
        grid.addWidget(self.duration_box, 2, 1)
        grid.addWidget(QLabel("Last Export"), 2, 2)
        grid.addWidget(self.last_export_label, 2, 3)
        root.addWidget(settings_box)

        ai_box = QGroupBox("Story AI Provider")
        ai_grid = QGridLayout(ai_box)
        self.generation_mode_box = QComboBox()
        self.generation_mode_box.addItems(["Manual", "AI"])
        self.ai_provider_box = QComboBox()
        self._reload_provider_choices()
        self.model_preset_box = QComboBox()
        self.model_preset_box.addItems(["Economy", "Balanced", "Quality", "Custom"])
        self.model_preset_box.setCurrentText("Economy")
        self.custom_model_edit = QLineEdit()
        self.custom_model_edit.setPlaceholderText("Custom model ID")
        self.reasoning_box = QComboBox()
        self.reasoning_box.addItems(["none", "low", "medium", "high"])
        self.reasoning_box.setCurrentText("low")
        self.max_output_box = QSpinBox()
        self.max_output_box.setRange(512, 20000)
        self.max_output_box.setValue(4096)
        self.retry_box = QSpinBox()
        self.retry_box.setRange(0, 5)
        self.retry_box.setValue(2)
        self.timeout_box = QSpinBox()
        self.timeout_box.setRange(10, 600)
        self.timeout_box.setValue(60)
        self.gemini_free_tier_only_check = QCheckBox("Free-tier-only")
        self.gemini_free_tier_only_check.setChecked(True)
        self.gemini_project_free_check = QCheckBox("Project Tier Free confirmed")
        self.gemini_billing_disabled_check = QCheckBox("Billing disabled confirmed")
        self.gemini_daily_cap_box = QSpinBox()
        self.gemini_daily_cap_box.setRange(0, 1000)
        self.gemini_daily_cap_box.setValue(10)
        self.gemini_model_info_label = QLabel("-")
        self.gemini_charge_risk_label = QLabel("unknown")
        self.estimate_label = QLabel("-")
        self.generation_status_label = QLabel("pending")
        self.token_usage_label = QLabel("-")
        self.actual_cost_label = QLabel("-")
        self.generation_error_label = QLabel("-")
        self.candidate_label = QLabel("-")

        ai_grid.addWidget(QLabel("Generation Mode"), 0, 0)
        ai_grid.addWidget(self.generation_mode_box, 0, 1)
        ai_grid.addWidget(QLabel("Provider"), 0, 2)
        ai_grid.addWidget(self.ai_provider_box, 0, 3)
        ai_grid.addWidget(QLabel("Model preset"), 1, 0)
        ai_grid.addWidget(self.model_preset_box, 1, 1)
        ai_grid.addWidget(QLabel("Custom model ID"), 1, 2)
        ai_grid.addWidget(self.custom_model_edit, 1, 3)
        ai_grid.addWidget(QLabel("Reasoning effort"), 2, 0)
        ai_grid.addWidget(self.reasoning_box, 2, 1)
        ai_grid.addWidget(QLabel("Max output tokens"), 2, 2)
        ai_grid.addWidget(self.max_output_box, 2, 3)
        ai_grid.addWidget(QLabel("Retry count"), 3, 0)
        ai_grid.addWidget(self.retry_box, 3, 1)
        ai_grid.addWidget(QLabel("Timeout"), 3, 2)
        ai_grid.addWidget(self.timeout_box, 3, 3)
        ai_grid.addWidget(QLabel("Free-tier-only"), 4, 0)
        ai_grid.addWidget(self.gemini_free_tier_only_check, 4, 1)
        ai_grid.addWidget(QLabel("Local daily cap"), 4, 2)
        ai_grid.addWidget(self.gemini_daily_cap_box, 4, 3)
        ai_grid.addWidget(self.gemini_project_free_check, 5, 0, 1, 2)
        ai_grid.addWidget(self.gemini_billing_disabled_check, 5, 2, 1, 2)
        ai_grid.addWidget(QLabel("Gemini model info"), 6, 0)
        ai_grid.addWidget(self.gemini_model_info_label, 6, 1, 1, 3)
        ai_grid.addWidget(QLabel("Charge risk"), 7, 0)
        ai_grid.addWidget(self.gemini_charge_risk_label, 7, 1, 1, 3)
        ai_grid.addWidget(QLabel("Estimated cost"), 8, 0)
        ai_grid.addWidget(self.estimate_label, 8, 1)
        ai_grid.addWidget(QLabel("Generation status"), 8, 2)
        ai_grid.addWidget(self.generation_status_label, 8, 3)
        ai_grid.addWidget(QLabel("Token usage"), 9, 0)
        ai_grid.addWidget(self.token_usage_label, 9, 1)
        ai_grid.addWidget(QLabel("Actual estimated cost"), 9, 2)
        ai_grid.addWidget(self.actual_cost_label, 9, 3)
        ai_grid.addWidget(QLabel("Last error"), 10, 0)
        ai_grid.addWidget(self.generation_error_label, 10, 1, 1, 3)
        ai_grid.addWidget(QLabel("Generated Story"), 11, 0)
        ai_grid.addWidget(self.candidate_label, 11, 1, 1, 3)
        root.addWidget(ai_box)
        self.ai_provider_box.currentIndexChanged.connect(self._on_provider_or_model_changed)
        self.model_preset_box.currentIndexChanged.connect(self._on_provider_or_model_changed)
        self.custom_model_edit.textChanged.connect(self._on_provider_or_model_changed)
        self.gemini_free_tier_only_check.toggled.connect(self._on_provider_or_model_changed)
        self.gemini_project_free_check.toggled.connect(self._on_provider_or_model_changed)
        self.gemini_billing_disabled_check.toggled.connect(self._on_provider_or_model_changed)

        prompt_box = QGroupBox("Prompt Preview")
        prompt_layout = QVBoxLayout(prompt_box)
        self.prompt_preview = QTextEdit()
        self.prompt_preview.setReadOnly(True)
        self.prompt_preview.setMinimumHeight(170)
        prompt_layout.addWidget(self.prompt_preview)
        root.addWidget(prompt_box)

        json_box = QGroupBox("Raw Story JSON")
        json_layout = QVBoxLayout(json_box)
        self.raw_json_edit = QTextEdit()
        self.raw_json_edit.setPlaceholderText("Story Composer用JSONをここへ貼り付けます。")
        self.raw_json_edit.setMinimumHeight(180)
        json_layout.addWidget(self.raw_json_edit)
        root.addWidget(json_box)

        preview_row = QHBoxLayout()
        validation_box = QGroupBox("Validation Result")
        validation_layout = QVBoxLayout(validation_box)
        self.validation_text = QTextEdit()
        self.validation_text.setReadOnly(True)
        validation_layout.addWidget(self.validation_text)
        preview_row.addWidget(validation_box, stretch=1)

        scenes_box = QGroupBox("Scene Preview")
        scenes_layout = QVBoxLayout(scenes_box)
        self.scene_list = QListWidget()
        scenes_layout.addWidget(self.scene_list)
        preview_row.addWidget(scenes_box, stretch=1)
        root.addLayout(preview_row, stretch=1)

        buttons = QHBoxLayout()
        self.generate_prompt_button = QPushButton("Generate Prompt")
        self.generate_prompt_button.clicked.connect(self.generate_prompt)
        self.copy_prompt_button = QPushButton("Copy Prompt")
        self.copy_prompt_button.clicked.connect(self.copy_prompt)
        self.import_button = QPushButton("Import Story JSON")
        self.import_button.clicked.connect(self.import_story_json)
        self.validate_button = QPushButton("Validate")
        self.validate_button.clicked.connect(self.validate_story)
        self.save_button = QPushButton("Save")
        self.save_button.clicked.connect(self.save_story)
        self.resume_button = QPushButton("Resume")
        self.resume_button.clicked.connect(self.resume_story)
        self.reset_button = QPushButton("Reset")
        self.reset_button.clicked.connect(self.reset_story)
        self.preview_button = QPushButton("Export Preview")
        self.preview_button.clicked.connect(self.show_export_preview)
        self.export_button = QPushButton("Export to Factory")
        self.export_button.clicked.connect(self.export_to_factory)
        self.generate_story_button = QPushButton("Generate Story")
        self.generate_story_button.clicked.connect(self.generate_story_ai)
        self.cancel_generation_button = QPushButton("Cancel Generation")
        self.cancel_generation_button.clicked.connect(self.cancel_generation)
        self.retry_generation_button = QPushButton("Retry Generation")
        self.retry_generation_button.clicked.connect(self.retry_generation)
        self.resume_generation_button = QPushButton("Resume Generation")
        self.resume_generation_button.clicked.connect(self.resume_generation)
        self.preview_generated_button = QPushButton("Preview Generated Story")
        self.preview_generated_button.clicked.connect(self.preview_generated_story)
        self.use_generated_button = QPushButton("Use Generated Story")
        self.use_generated_button.clicked.connect(self.use_generated_story)
        for button in [
            self.generate_prompt_button,
            self.copy_prompt_button,
            self.import_button,
            self.validate_button,
            self.save_button,
            self.resume_button,
            self.reset_button,
            self.generate_story_button,
            self.cancel_generation_button,
            self.retry_generation_button,
            self.resume_generation_button,
            self.preview_generated_button,
            self.use_generated_button,
            self.preview_button,
            self.export_button,
        ]:
            buttons.addWidget(button)
        buttons.addStretch()
        root.addLayout(buttons)
        self._update_enabled_state()

    def set_project(self, project: ProjectInfo | None) -> None:
        self.project = project
        self.story = None
        self.prompt_preview.clear()
        self.raw_json_edit.clear()
        self.validation_text.clear()
        self.scene_list.clear()
        self.last_export_label.setText("-")
        self._show_generation_state()
        if project is None:
            self.theme_input.clear()
            self.status_label.setText("no project")
            self._update_enabled_state()
            return
        self.theme_input.setText(project.topic or project.title)
        self.scene_count_box.setValue(max(3, min(20, int(project.image_count or 5))))
        self.duration_box.setValue(self._duration_seconds(project.duration))
        self.resume_story(show_missing=False)
        self._show_generation_state()
        self._update_enabled_state()

    def generate_prompt(self) -> None:
        if self.project is None:
            self._warn("先にプロジェクトを選択してください。")
            return
        result = self.story_service.build_prompt(
            self.project,
            scene_count=self.scene_count_box.value(),
            duration_seconds=self.duration_box.value(),
        )
        self.prompt_preview.setPlainText(result.prompt)
        self.status_label.setText("prompt_ready")

    def copy_prompt(self) -> None:
        text = self.prompt_preview.toPlainText().strip()
        if not text:
            self._warn("コピーできるPromptがありません。")
            return
        QGuiApplication.clipboard().setText(text)
        QMessageBox.information(self, "Story Composer", "Promptをコピーしました。")

    def import_story_json(self) -> None:
        if self.project is None:
            self._warn("先にプロジェクトを選択してください。")
            return
        raw = self.raw_json_edit.toPlainText()
        try:
            self.story = self.story_service.import_story_json(self.project, raw)
        except StoryValidationError as exc:
            self.validation_text.setPlainText(str(exc))
            self._warn(str(exc))
            return
        self._sync_controls_from_story()
        self._show_validation(self.story.validation)
        self._show_scenes()
        self.status_label.setText(self.story.status)

    def validate_story(self) -> None:
        if self.project is None:
            self._warn("先にプロジェクトを選択してください。")
            return
        if self.story is None:
            self.story = self.story_service.load_story(self.project)
        result = self.story_service.validate_story(self.project, self.story)
        if self.story is not None:
            self.story.validation = result
            self.story.status = "invalid" if result.has_errors else "valid"
        self._show_validation(result)
        self.status_label.setText(result.status)

    def save_story(self) -> None:
        if self.project is None:
            self._warn("先にプロジェクトを選択してください。")
            return
        if self.story is None:
            self._warn("保存できるStoryがありません。Import Story JSONを先に実行してください。")
            return
        self.story.theme = self.theme_input.text().strip()
        self.story.estimated_duration = float(self.duration_box.value())
        self.story.status = "draft" if self.story.status == "exported_to_factory" else self.story.status
        self.story_service.save_story(self.project, self.story)
        QMessageBox.information(self, "Story Composer", "story.jsonを保存しました。")

    def resume_story(self, show_missing: bool = True) -> None:
        if self.project is None:
            return
        story = self.story_service.load_story(self.project)
        manifest = self.story_service.load_manifest(self.project)
        self.story = story
        self.prompt_preview.setPlainText(str(manifest.get("prompt") or ""))
        self.raw_json_edit.setPlainText(str(manifest.get("raw_response") or ""))
        self.last_export_label.setText(str(manifest.get("last_exported_at") or "-"))
        if story is None:
            self.status_label.setText("draft")
            self.validation_text.setPlainText("story.jsonはまだありません。")
            self.scene_list.clear()
            if show_missing:
                QMessageBox.information(self, "Story Composer", "保存済みStoryはありません。")
            return
        self._sync_controls_from_story()
        self._show_validation(story.validation)
        self._show_scenes()
        self.status_label.setText(story.status)

    def reset_story(self) -> None:
        if self.project is None:
            self._warn("先にプロジェクトを選択してください。")
            return
        message = (
            "Story Composerの保存内容だけをResetします。\n\n"
            "削除対象:\n"
            "- story.json\n"
            "- story_manifest.json\n\n"
            "title.txt、image_prompts.txt、images、audio、video/final.mp4、YouTube/TikTok状態は削除しません。"
        )
        if QMessageBox.question(self, "Story Composer Reset", message) != QMessageBox.Yes:
            return
        self.story_service.reset(self.project)
        self.set_project(self.project)

    def show_export_preview(self) -> None:
        if self.project is None:
            self._warn("先にプロジェクトを選択してください。")
            return
        try:
            preview = self.story_service.export_preview(self.project)
        except StoryValidationError as exc:
            self._warn(str(exc))
            return
        self.validation_text.setPlainText(self._format_export_preview(preview))

    def export_to_factory(self) -> None:
        if self.project is None:
            self._warn("先にプロジェクトを選択してください。")
            return
        if self.story is None:
            self.story = self.story_service.load_story(self.project)
        if self.story is None:
            self._warn("ExportできるStoryがありません。")
            return
        result = self.story_service.validator.validate(self.story)
        self._show_validation(result)
        if result.has_errors:
            self._warn("Validation errorがあるためExportできません。")
            return
        preview = self.story_service.adapter.preview(self.project, self.story)
        message = self._format_export_preview(preview)
        if result.warnings:
            message += "\n\nWarningsがあります。内容を確認してExportしますか？"
        else:
            message += "\n\nFactoryファイルへExportしますか？"
        if QMessageBox.question(self, "Export to Factory", message) != QMessageBox.Yes:
            return
        try:
            export_result = self.story_service.export_to_factory(self.project)
        except Exception as exc:
            self._warn(f"Exportに失敗しました。\n{exc}")
            return
        self.project = self.project_service.load_project(self.project.path)
        self.resume_story(show_missing=False)
        self.exported.emit(self.project.path)
        QMessageBox.information(
            self,
            "Export to Factory",
            f"Exportしました。\nBackup: {export_result.backup_dir}",
        )

    def generate_story_ai(self) -> None:
        if self.project is None:
            self._warn("先にプロジェクトを選択してください。")
            return
        request = self._story_generation_request()
        provider_id = str(self.ai_provider_box.currentData() or "openai")
        provider = self.story_service.provider_manager.get(provider_id)
        config = provider.validate_configuration()
        if not config.configured:
            self.generation_error_label.setText(config.message)
            self._warn(config.message)
            return
        if provider_id == "gemini" and not self._gemini_generation_allowed():
            self._warn("Gemini Free-tier-only guard blocks generation until model Free Tier, Project Tier, Billing, and local cap checks are safe.")
            return
        estimate = provider.estimate_cost(request)
        self.estimate_label.setText(self._format_cost(estimate.estimated_cost_usd))
        billing_note = (
            "Gemini Free-tier-only is enabled. This app only uses a local safety cap; Google-side remaining quota is not known.\n"
            "Generation is allowed only because you confirmed Project Tier Free and Billing disabled.\n"
            if provider_id == "gemini"
            else "OpenAI API billing is separate from ChatGPT Plus.\n"
        )
        message = (
            "Story AI generation will call the selected provider API.\n\n"
            f"Provider: {provider.provider_name}\n"
            f"Model: {request.model}\n"
            f"Max output tokens: {request.max_output_tokens}\n"
            f"Estimated cost: {self._format_cost(estimate.estimated_cost_usd)}\n\n"
            f"{billing_note}"
            "Generation will only save a candidate Story. Export and Production will not start automatically."
        )
        if QMessageBox.question(self, "Generate Story", message) != QMessageBox.Yes:
            return
        self._start_generation(request, provider_id)

    def retry_generation(self) -> None:
        if self.project is None:
            return
        state = self.story_service.load_generation_state(self.project)
        resume_from = state.generation_id if state is not None else None
        self._start_generation(self._story_generation_request(), str(self.ai_provider_box.currentData() or "openai"), resume_from)

    def resume_generation(self) -> None:
        self._show_generation_state()
        QMessageBox.information(self, "Story AI Provider", "Resumeは状態を復元しました。API再実行はRetry Generationで開始してください。")

    def cancel_generation(self) -> None:
        if self._generation_token is not None:
            self._generation_token.cancel()
            self.generation_status_label.setText("cancel requested")
            self.generation_error_label.setText("Cancelling after the current safe point.")

    def preview_generated_story(self) -> None:
        if self.project is None:
            return
        story = self.story_service.load_generated_candidate(self.project)
        if story is None:
            self._warn("Generated Story candidateがありません。")
            return
        self.story = story
        self._sync_controls_from_story()
        self._show_validation(story.validation)
        self._show_scenes()
        self.status_label.setText("candidate_preview")

    def use_generated_story(self) -> None:
        if self.project is None:
            return
        if QMessageBox.question(self, "Use Generated Story", "候補Storyをstory.jsonへ採用しますか？既存story.jsonはバックアップします。") != QMessageBox.Yes:
            return
        try:
            self.story = self.story_service.use_generated_story(self.project)
        except StoryValidationError as exc:
            self._warn(str(exc))
            return
        self._sync_controls_from_story()
        self._show_validation(self.story.validation)
        self._show_scenes()
        self.status_label.setText(self.story.status)
        self.candidate_label.setText("used")

    def _start_generation(self, request: StoryGenerationRequest, provider_id: str, resume_from_generation_id: str | None = None) -> None:
        if self.project is None or self._generation_thread is not None:
            return
        self._generation_token = CancellationToken()
        self._generation_thread = QThread(self)
        self._generation_worker = StoryGenerationWorker(
            self.story_service,
            self.project,
            request,
            provider_id,
            self._generation_token,
            resume_from_generation_id,
        )
        self._generation_worker.moveToThread(self._generation_thread)
        self._generation_thread.started.connect(self._generation_worker.run)
        self._generation_worker.progress.connect(self._on_generation_progress)
        self._generation_worker.finished.connect(self._on_generation_finished)
        self._generation_worker.finished.connect(self._generation_thread.quit)
        self._generation_worker.finished.connect(self._generation_worker.deleteLater)
        self._generation_thread.finished.connect(self._generation_thread.deleteLater)
        self._generation_thread.finished.connect(self._generation_thread_finished)
        self._set_generation_active(True)
        self.generation_status_label.setText("running")
        self._generation_thread.start()

    def _on_generation_progress(self, message: str, progress: int) -> None:
        self.generation_status_label.setText(f"running {max(0, min(100, progress))}%")
        self.generation_error_label.setText(message)

    def _on_generation_finished(self, result) -> None:
        self.generation_status_label.setText(str(getattr(result, "status", "completed")))
        if getattr(result, "error_message", None):
            self.generation_error_label.setText(str(result.error_message))
        metrics = getattr(result, "metrics", None)
        if metrics is not None:
            self.token_usage_label.setText(
                f"in {metrics.input_tokens or 0} / out {metrics.output_tokens or 0} / total {metrics.total_tokens or 0}"
            )
            self.actual_cost_label.setText(self._format_cost(metrics.estimated_cost_usd))
        if getattr(result, "status", "") == "completed":
            self.candidate_label.setText("available")
        self._show_generation_state()

    def _generation_thread_finished(self) -> None:
        self._generation_thread = None
        self._generation_worker = None
        self._generation_token = None
        self._set_generation_active(False)

    def _story_generation_request(self) -> StoryGenerationRequest:
        model = self._selected_model()
        return StoryGenerationRequest(
            project_id=self.project.name if self.project else "",
            theme=self.theme_input.text().strip(),
            target_duration_seconds=float(self.duration_box.value()),
            min_scenes=3,
            max_scenes=int(self.scene_count_box.value()),
            model=model,
            reasoning_effort=self.reasoning_box.currentText(),
            max_output_tokens=self.max_output_box.value(),
            retry_count=self.retry_box.value(),
            timeout_seconds=self.timeout_box.value(),
            provider_options=self._provider_options(),
        )

    def _selected_model(self) -> str:
        preset = self.model_preset_box.currentText()
        provider_id = str(self.ai_provider_box.currentData() or "gemini")
        if preset != "Custom":
            if provider_id == "gemini":
                return GEMINI_STORY_MODEL_PRESETS.get(preset, "gemini-3.5-flash-lite")
            return STORY_MODEL_PRESETS.get(preset, "gpt-5.6-luna")
        custom = self.custom_model_edit.text().strip()
        if not custom or len(custom) > 120 or any(ord(ch) < 32 for ch in custom):
            return "gemini-3.5-flash-lite" if provider_id == "gemini" else "gpt-5.6-luna"
        return custom

    def _reload_provider_choices(self) -> None:
        self.ai_provider_box.clear()
        names = {"gemini": "Gemini", "openai": "OpenAI", "mock": "Mock", "manual_prompt": "Manual Prompt"}
        for provider_id in self.story_service.provider_manager.provider_ids():
            self.ai_provider_box.addItem(names.get(provider_id, provider_id), provider_id)
        gemini_index = self.ai_provider_box.findData("gemini")
        self.ai_provider_box.setCurrentIndex(gemini_index if gemini_index >= 0 else 0)

    def _show_generation_state(self) -> None:
        if self.project is None:
            self.generation_status_label.setText("no project")
            self.candidate_label.setText("-")
            return
        state = self.story_service.load_generation_state(self.project)
        if state is None:
            self.generation_status_label.setText("pending")
            self.token_usage_label.setText("-")
            self.actual_cost_label.setText("-")
            self.generation_error_label.setText("-")
        else:
            self.generation_status_label.setText(state.status)
            self.generation_error_label.setText(state.last_error or "-")
            self.token_usage_label.setText(
                f"in {state.metrics.input_tokens or 0} / out {state.metrics.output_tokens or 0} / total {state.metrics.total_tokens or 0}"
            )
            self.actual_cost_label.setText(self._format_cost(state.metrics.estimated_cost_usd))
        self.candidate_label.setText("available" if self.story_service.load_generated_candidate(self.project) else "-")

    def _format_cost(self, cost: float | None) -> str:
        return "pricing unavailable" if cost is None else f"estimated ${cost:.6f}"

    def _set_generation_active(self, active: bool) -> None:
        for widget in [
            self.generation_mode_box,
            self.ai_provider_box,
            self.model_preset_box,
            self.custom_model_edit,
            self.reasoning_box,
            self.max_output_box,
            self.retry_box,
            self.timeout_box,
            self.gemini_free_tier_only_check,
            self.gemini_project_free_check,
            self.gemini_billing_disabled_check,
            self.gemini_daily_cap_box,
            self.generate_story_button,
            self.retry_generation_button,
            self.resume_generation_button,
            self.preview_generated_button,
            self.use_generated_button,
        ]:
            widget.setEnabled(not active)
        self.cancel_generation_button.setEnabled(active)
        if not active:
            self._on_provider_or_model_changed()

    def apply_settings(self, settings: AppSettings | None) -> None:
        if settings is None:
            return
        self.settings = settings
        provider_index = self.ai_provider_box.findData(getattr(settings, "default_story_provider", "gemini"))
        if provider_index >= 0:
            self.ai_provider_box.setCurrentIndex(provider_index)
        model = str(getattr(settings, "default_story_model", "gemini-3.5-flash-lite"))
        presets = GEMINI_STORY_MODEL_PRESETS if str(self.ai_provider_box.currentData() or "") == "gemini" else STORY_MODEL_PRESETS
        preset_name = next((name for name, preset_model in presets.items() if preset_model == model), "Custom")
        self.model_preset_box.setCurrentText(preset_name)
        self.custom_model_edit.setText("" if preset_name != "Custom" else model)
        self.reasoning_box.setCurrentText(str(getattr(settings, "default_reasoning_effort", "low")))
        self.max_output_box.setValue(int(getattr(settings, "default_max_output_tokens", 4096)))
        self.retry_box.setValue(int(getattr(settings, "story_provider_retry_count", 2)))
        self.timeout_box.setValue(int(getattr(settings, "story_provider_timeout_seconds", 60)))
        self.gemini_free_tier_only_check.setChecked(bool(getattr(settings, "gemini_free_tier_only", True)))
        key_confirmation_valid = self._settings_gemini_confirmation_valid(settings)
        self.gemini_project_free_check.setChecked(bool(getattr(settings, "gemini_project_free_tier_confirmed", False)) and key_confirmation_valid)
        self.gemini_billing_disabled_check.setChecked(bool(getattr(settings, "gemini_billing_disabled_confirmed", False)) and key_confirmation_valid)
        self.gemini_daily_cap_box.setValue(int(getattr(settings, "gemini_local_daily_request_cap", 10)))
        self._on_provider_or_model_changed()

    def _provider_options(self) -> dict[str, object]:
        provider_id = str(self.ai_provider_box.currentData() or "gemini")
        if provider_id != "gemini":
            return {}
        model = self._selected_model()
        metadata = get_gemini_model_metadata(model)
        project_confirmed = self.gemini_project_free_check.isChecked()
        billing_confirmed = self.gemini_billing_disabled_check.isChecked()
        current_fingerprint = self._gemini_key_fingerprint()
        charge_risk = "low" if project_confirmed and billing_confirmed and current_fingerprint and metadata is not None and metadata.free_tier_status == "available" else "unknown"
        fingerprint = self._confirmation_key_fingerprint(current_fingerprint) if project_confirmed and billing_confirmed else ""
        return {
            "free_tier_only": self.gemini_free_tier_only_check.isChecked(),
            "project_free_tier_confirmed": project_confirmed,
            "billing_disabled_confirmed": billing_confirmed,
            "confirmation_key_fingerprint": fingerprint,
            "local_daily_request_cap": self.gemini_daily_cap_box.value(),
            "temperature": 0.7,
            "model_free_tier_status": metadata.free_tier_status if metadata else "unknown",
            "project_tier_status": "user_confirmed_free" if project_confirmed else "unknown",
            "billing_status": "user_confirmed_disabled" if billing_confirmed else "unknown",
            "charge_risk": charge_risk,
        }

    def _gemini_generation_allowed(self) -> bool:
        if not self.gemini_free_tier_only_check.isChecked():
            return True
        model = self._selected_model()
        metadata = get_gemini_model_metadata(model)
        return (
            metadata is not None
            and metadata.free_tier_status == "available"
            and metadata.structured_outputs
            and bool(self._gemini_key_fingerprint())
            and self.gemini_project_free_check.isChecked()
            and self.gemini_billing_disabled_check.isChecked()
        )

    def _settings_gemini_confirmation_valid(self, settings: AppSettings | None = None) -> bool:
        active_settings = settings or self.settings
        current_fingerprint = self._gemini_key_fingerprint()
        stored_fingerprint = str(getattr(active_settings, "gemini_confirmation_key_fingerprint", ""))
        return bool(current_fingerprint and stored_fingerprint and current_fingerprint == stored_fingerprint)

    def _confirmation_key_fingerprint(self, current_fingerprint: str) -> str:
        stored_fingerprint = str(getattr(self.settings, "gemini_confirmation_key_fingerprint", ""))
        if stored_fingerprint and stored_fingerprint == current_fingerprint:
            return stored_fingerprint
        return current_fingerprint

    def _gemini_key_fingerprint(self) -> str:
        try:
            provider = self.story_service.provider_manager.get("gemini")
            if hasattr(provider, "current_key_fingerprint"):
                return str(provider.current_key_fingerprint())
        except Exception:
            return ""
        return ""

    def _on_provider_or_model_changed(self) -> None:
        provider_id = str(self.ai_provider_box.currentData() or "gemini")
        is_gemini = provider_id == "gemini"
        for widget in [
            self.gemini_free_tier_only_check,
            self.gemini_project_free_check,
            self.gemini_billing_disabled_check,
            self.gemini_daily_cap_box,
        ]:
            widget.setEnabled(is_gemini and self._generation_thread is None)
        if not is_gemini:
            self.gemini_model_info_label.setText("-")
            self.gemini_charge_risk_label.setText("-")
            return
        metadata = get_gemini_model_metadata(self._selected_model())
        if metadata is None:
            self.gemini_model_info_label.setText("custom/unknown; Free-tier-only blocks generation")
            self.gemini_charge_risk_label.setText("unknown")
        else:
            self.gemini_model_info_label.setText(
                f"{metadata.model_id} / {metadata.stability} / structured={metadata.structured_outputs} / free tier={metadata.free_tier_status} / checked={metadata.metadata_checked_at}"
            )
            risk = "low" if self._gemini_generation_allowed() else "unknown"
            self.gemini_charge_risk_label.setText(f"{risk} / local record only, not Google remaining quota")
        self.generate_story_button.setEnabled(self.project is not None and (provider_id != "gemini" or self._gemini_generation_allowed()))

    def _sync_controls_from_story(self) -> None:
        if self.story is None:
            return
        self.theme_input.setText(self.story.theme)
        self.scene_count_box.setValue(max(3, min(20, len(self.story.scenes) or 5)))
        self.duration_box.setValue(float(self.story.estimated_duration or 60.0))

    def _show_validation(self, result: ValidationResult) -> None:
        lines = [f"status: {result.status}"]
        for severity, issues in [("error", result.errors), ("warning", result.warnings), ("info", result.infos)]:
            if not issues:
                continue
            lines.append("")
            lines.append(severity.upper())
            for issue in issues:
                scene = f" scene={issue.scene_index}" if issue.scene_index is not None else ""
                field = f" [{issue.field}]" if issue.field else ""
                lines.append(f"-{scene}{field} {issue.message}")
        self.validation_text.setPlainText("\n".join(lines))

    def _show_scenes(self) -> None:
        self.scene_list.clear()
        if self.story is None:
            return
        for scene in sorted(self.story.scenes, key=lambda item: item.scene_index):
            self.scene_list.addItem(
                f"{scene.scene_index}. {scene.scene_type} "
                f"{scene.start_time:.1f}-{scene.end_time:.1f}s\n"
                f"字幕: {scene.subtitle or '-'}\n"
                f"画像: {scene.image_prompt[:120]}"
            )

    def _format_export_preview(self, preview: FactoryExportPreview) -> str:
        return "\n".join(
            [
                "Export Preview",
                "",
                f"title: {preview.title}",
                f"narration chars: {len(preview.narration)}",
                f"subtitle count: {preview.subtitle_count}",
                f"image prompt count: {preview.image_prompt_count}",
                f"hashtags: {preview.hashtags or '-'}",
                "",
                "target files:",
                *[f"- {name}" for name in preview.target_files],
                "",
                "overwrite:",
                *[f"- {name}" for name in preview.existing_files],
                "",
                "new:",
                *[f"- {name}" for name in preview.new_files],
            ]
        )

    def _duration_seconds(self, duration: str) -> float:
        text = str(duration)
        digits = "".join(ch for ch in text if ch.isdigit())
        value = float(digits or 60)
        lowered = text.casefold()
        if "分" in text or "minute" in lowered or "min" in lowered:
            return value * 60.0
        return value

    def _update_enabled_state(self) -> None:
        enabled = self.project is not None
        for button in [
            self.generate_prompt_button,
            self.copy_prompt_button,
            self.import_button,
            self.validate_button,
            self.save_button,
            self.resume_button,
            self.reset_button,
            self.preview_button,
            self.export_button,
        ]:
            button.setEnabled(enabled)
        if hasattr(self, "cancel_generation_button"):
            self.cancel_generation_button.setEnabled(False)
        if hasattr(self, "generate_story_button"):
            self._on_provider_or_model_changed()

    def _warn(self, message: str) -> None:
        QMessageBox.warning(self, "Story Composer", message)
