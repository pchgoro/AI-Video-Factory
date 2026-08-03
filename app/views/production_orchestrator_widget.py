from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QObject, QThread, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from models import ProjectInfo
from services.production_orchestrator import ProductionOptions, ProductionOrchestratorService


class ProductionWorker(QObject):
    progress = Signal(dict)
    finished = Signal(dict)
    failed = Signal(str)

    def __init__(self, service: ProductionOrchestratorService, project: ProjectInfo, options: ProductionOptions, mode: str, action: str) -> None:
        super().__init__()
        self.service = service
        self.project = project
        self.options = options
        self.mode = mode
        self.action = action
        self.cancel_requested = False

    def run(self) -> None:
        try:
            if self.action == "resume":
                run = self.service.resume(self.project, self.progress.emit, lambda: self.cancel_requested)
            elif self.action == "retry":
                run = self.service.retry_failed_step(self.project, self.progress.emit, lambda: self.cancel_requested)
            else:
                run = self.service.start(
                    self.project,
                    self.options,
                    mode=self.mode,
                    progress_callback=self.progress.emit,
                    should_cancel=lambda: self.cancel_requested,
                )
        except Exception as exc:
            self.failed.emit(str(exc))
            return
        self.finished.emit(run.to_dict())


class ProductionOrchestratorWidget(QWidget):
    run_updated = Signal(Path)

    def __init__(self, service: ProductionOrchestratorService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.service = service
        self.project: ProjectInfo | None = None
        self.thread: QThread | None = None
        self.worker: ProductionWorker | None = None
        self._build_ui()
        self._set_active(False)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)

        header = QGroupBox("Automated Production")
        header_layout = QHBoxLayout(header)
        self.mode_box = QComboBox()
        self.mode_box.addItems(["Dry Run", "Normal"])
        self.run_status_label = QLabel("pending")
        self.current_step_label = QLabel("-")
        self.progress_label = QLabel("0%")
        self.run_id_label = QLabel("-")
        for label, widget in [
            ("Mode", self.mode_box),
            ("Run status", self.run_status_label),
            ("Current step", self.current_step_label),
            ("Overall progress", self.progress_label),
            ("Run ID", self.run_id_label),
        ]:
            header_layout.addWidget(QLabel(label))
            header_layout.addWidget(widget)
        root.addWidget(header)

        options_box = QGroupBox("Options")
        options_layout = QHBoxLayout(options_box)
        self.export_story_check = QCheckBox("Export Story")
        self.generate_images_check = QCheckBox("Generate Images")
        self.generate_voice_check = QCheckBox("Generate Voice")
        self.generate_subtitles_check = QCheckBox("Generate Subtitles")
        self.render_video_check = QCheckBox("Render Video")
        self.upload_youtube_check = QCheckBox("Upload YouTube")
        self.upload_tiktok_check = QCheckBox("Upload TikTok")
        self.reuse_check = QCheckBox("Reuse existing artifacts")
        self.continue_uploads_check = QCheckBox("Continue independent upload steps")
        for check in [
            self.export_story_check,
            self.generate_images_check,
            self.generate_voice_check,
            self.generate_subtitles_check,
            self.render_video_check,
            self.upload_youtube_check,
            self.upload_tiktok_check,
            self.reuse_check,
            self.continue_uploads_check,
        ]:
            check.setChecked(check not in {self.upload_youtube_check, self.upload_tiktok_check})
            options_layout.addWidget(check)
        options_layout.addStretch()
        root.addWidget(options_box)

        self.step_table = QTableWidget(0, 5)
        self.step_table.setHorizontalHeaderLabels(["Step", "Enabled", "Status", "Progress", "Message"])
        root.addWidget(self.step_table)

        lists = QHBoxLayout()
        preflight_box = QGroupBox("Preflight results")
        preflight_layout = QVBoxLayout(preflight_box)
        self.preflight_list = QListWidget()
        preflight_layout.addWidget(self.preflight_list)
        lists.addWidget(preflight_box)

        artifact_box = QGroupBox("Artifact freshness")
        artifact_layout = QVBoxLayout(artifact_box)
        self.artifact_list = QListWidget()
        artifact_layout.addWidget(self.artifact_list)
        lists.addWidget(artifact_box)
        root.addLayout(lists)

        self.last_message = QTextEdit()
        self.last_message.setReadOnly(True)
        self.last_message.setMinimumHeight(80)
        root.addWidget(self.last_message)

        buttons = QHBoxLayout()
        self.preflight_button = QPushButton("Run Preflight")
        self.dry_run_button = QPushButton("Start Dry Run")
        self.start_button = QPushButton("Start Production")
        self.cancel_button = QPushButton("Cancel")
        self.resume_button = QPushButton("Resume")
        self.retry_button = QPushButton("Retry Failed Step")
        self.open_output_button = QPushButton("Open Output Folder")
        self.preflight_button.clicked.connect(self.run_preflight)
        self.dry_run_button.clicked.connect(lambda: self.start_run("dry_run"))
        self.start_button.clicked.connect(lambda: self.start_run("normal"))
        self.cancel_button.clicked.connect(self.cancel_run)
        self.resume_button.clicked.connect(lambda: self.start_worker("resume"))
        self.retry_button.clicked.connect(lambda: self.start_worker("retry"))
        self.open_output_button.clicked.connect(self.open_output_folder)
        for button in [
            self.preflight_button,
            self.dry_run_button,
            self.start_button,
            self.cancel_button,
            self.resume_button,
            self.retry_button,
            self.open_output_button,
        ]:
            buttons.addWidget(button)
        buttons.addStretch()
        root.addLayout(buttons)

    def set_project(self, project: ProjectInfo | None) -> None:
        self.project = project
        self.clear_view()
        if project is None:
            self.run_status_label.setText("no project")
            self._update_buttons()
            return
        run = self.service.load_run(project)
        if run is not None:
            self.apply_run(run.to_dict())
        else:
            self.run_status_label.setText("pending")
        self._update_buttons()

    def run_preflight(self) -> None:
        if self.project is None:
            self.warn("Select a project first.")
            return
        result = self.service.preflight(self.project, self.options(), dry_run=self.mode() == "dry_run")
        self.show_preflight(result.to_dict())
        if result.has_errors:
            self.last_message.setPlainText("Preflight has errors. Normal Run is blocked.")
        else:
            self.last_message.setPlainText("Preflight completed.")

    def start_run(self, mode: str) -> None:
        if self.project is None:
            self.warn("Select a project first.")
            return
        options = self.options()
        if mode == "normal":
            preflight = self.service.preflight(self.project, options, dry_run=False)
            self.show_preflight(preflight.to_dict())
            if preflight.has_errors:
                self.warn("Preflight has errors. Fix them before Normal Run.")
                return
            message = (
                "Start Production?\n\n"
                "This may run APIs, VOICEVOX, FFmpeg, YouTube upload, or TikTok upload depending on checked options.\n"
                "Uploads are explicit and duplicate IDs are blocked."
            )
        else:
            message = "Start Dry Run?\n\nNo APIs, VOICEVOX generation, FFmpeg render, upload, or Factory export will run."
        if QMessageBox.question(self, "Automated Production", message) != QMessageBox.Yes:
            return
        self.start_worker("start", mode=mode, options=options)

    def start_worker(self, action: str, mode: str | None = None, options: ProductionOptions | None = None) -> None:
        if self.project is None:
            self.warn("Select a project first.")
            return
        if self.thread is not None and self.thread.isRunning():
            self.warn("A production run is already active.")
            return
        self.thread = QThread(self)
        self.worker = ProductionWorker(self.service, self.project, options or self.options(), mode or self.mode(), action)
        self.worker.moveToThread(self.thread)
        self.thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.apply_run)
        self.worker.finished.connect(self.on_finished)
        self.worker.failed.connect(self.on_failed)
        self.worker.finished.connect(self.thread.quit)
        self.worker.failed.connect(self.thread.quit)
        self.thread.finished.connect(self.worker.deleteLater)
        self.thread.finished.connect(self.thread.deleteLater)
        self.thread.finished.connect(lambda: self._set_active(False))
        self._set_active(True)
        self.thread.start()

    def cancel_run(self) -> None:
        if self.project is None:
            return
        self.service.request_cancel(self.project)
        if self.worker is not None:
            self.worker.cancel_requested = True
        self.last_message.setPlainText("Cancel requested. Waiting for the current safe boundary.")

    def on_finished(self, data: dict) -> None:
        self.apply_run(data)
        if self.project is not None:
            self.run_updated.emit(self.project.path)

    def on_failed(self, message: str) -> None:
        self.last_message.setPlainText(message)
        self.warn(message)

    def apply_run(self, data: dict) -> None:
        self.run_status_label.setText(str(data.get("status") or "-"))
        self.current_step_label.setText(str(data.get("current_step") or "-"))
        self.run_id_label.setText(str(data.get("run_id") or "-"))
        steps = data.get("steps", [])
        enabled_steps = [step for step in steps if isinstance(step, dict) and step.get("enabled")]
        done = [step for step in enabled_steps if step.get("status") in {"succeeded", "skipped", "failed", "blocked", "cancelled"}]
        percent = int((len(done) / max(1, len(enabled_steps))) * 100)
        self.progress_label.setText(f"{percent}%")
        self.step_table.setRowCount(len(steps))
        last = ""
        for row, step in enumerate(steps):
            if not isinstance(step, dict):
                continue
            values = [
                str(step.get("display_name") or step.get("step_id") or ""),
                "yes" if step.get("enabled") else "no",
                str(step.get("status") or ""),
                f"{int(step.get('progress', 0) or 0)}%",
                str(step.get("message") or step.get("last_error") or ""),
            ]
            last = values[-1] or last
            for column, value in enumerate(values):
                self.step_table.setItem(row, column, QTableWidgetItem(value))
        self.show_preflight(data.get("preflight", {}) if isinstance(data.get("preflight"), dict) else {})
        if last:
            self.last_message.setPlainText(last)
        self._update_buttons()

    def show_preflight(self, data: dict) -> None:
        self.preflight_list.clear()
        for issue in data.get("issues", []) if isinstance(data, dict) else []:
            self.preflight_list.addItem(f"{issue.get('severity')}: {issue.get('message')}")
        self.artifact_list.clear()
        artifacts = data.get("artifact_status", {}) if isinstance(data, dict) else {}
        for key, value in artifacts.items():
            if isinstance(value, dict):
                self.artifact_list.addItem(f"{key}: {value.get('state', 'unknown')}")

    def options(self) -> ProductionOptions:
        return ProductionOptions(
            export_story=self.export_story_check.isChecked(),
            generate_images=self.generate_images_check.isChecked(),
            generate_voice=self.generate_voice_check.isChecked(),
            generate_subtitles=self.generate_subtitles_check.isChecked(),
            render_video=self.render_video_check.isChecked(),
            upload_youtube=self.upload_youtube_check.isChecked(),
            upload_tiktok=self.upload_tiktok_check.isChecked(),
            reuse_existing_artifacts=self.reuse_check.isChecked(),
            continue_independent_upload_steps=self.continue_uploads_check.isChecked(),
        )

    def mode(self) -> str:
        return "dry_run" if self.mode_box.currentText() == "Dry Run" else "normal"

    def clear_view(self) -> None:
        self.step_table.setRowCount(0)
        self.preflight_list.clear()
        self.artifact_list.clear()
        self.last_message.clear()
        self.current_step_label.setText("-")
        self.progress_label.setText("0%")
        self.run_id_label.setText("-")

    def open_output_folder(self) -> None:
        if self.project is None:
            return
        self.project.path.mkdir(parents=True, exist_ok=True)
        import os

        os.startfile(self.project.path)

    def _set_active(self, active: bool) -> None:
        for widget in [
            self.mode_box,
            self.export_story_check,
            self.generate_images_check,
            self.generate_voice_check,
            self.generate_subtitles_check,
            self.render_video_check,
            self.upload_youtube_check,
            self.upload_tiktok_check,
            self.reuse_check,
            self.continue_uploads_check,
            self.preflight_button,
            self.dry_run_button,
            self.start_button,
            self.resume_button,
            self.retry_button,
        ]:
            widget.setEnabled(not active)
        self.cancel_button.setEnabled(active)

    def _update_buttons(self) -> None:
        has_project = self.project is not None
        active = self.thread is not None and self.thread.isRunning()
        if not active:
            self.preflight_button.setEnabled(has_project)
            self.dry_run_button.setEnabled(has_project)
            self.start_button.setEnabled(has_project)
            self.resume_button.setEnabled(has_project)
            self.retry_button.setEnabled(has_project)
            self.open_output_button.setEnabled(has_project)
            self.cancel_button.setEnabled(False)

    def warn(self, message: str) -> None:
        QMessageBox.warning(self, "Automated Production", message)
