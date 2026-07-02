from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
)

from models import AppSettings, DEFAULT_DURATIONS


class SettingsDialog(QDialog):
    """Phase4の設定を変更する画面です。"""

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.resize(640, 620)

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.duration_box = QComboBox()
        self.duration_box.addItems(DEFAULT_DURATIONS)
        self.duration_box.setCurrentText(settings.default_duration)
        form.addRow("デフォルト動画時間", self.duration_box)

        self.image_count_box = QSpinBox()
        self.image_count_box.setRange(3, 8)
        self.image_count_box.setValue(settings.default_image_count)
        form.addRow("デフォルト画像枚数", self.image_count_box)

        save_row = QHBoxLayout()
        self.save_dir_edit = QLineEdit(settings.save_dir)
        browse_button = QPushButton("選択")
        browse_button.clicked.connect(self._select_save_dir)
        save_row.addWidget(self.save_dir_edit)
        save_row.addWidget(browse_button)
        form.addRow("保存先", save_row)

        self.video_editor_box = QComboBox()
        self.video_editor_box.addItems(["ffmpeg", "video-use", "future"])
        self.video_editor_box.setCurrentText(settings.video_editor_engine)
        form.addRow("動画編集エンジン", self.video_editor_box)

        self.voicevox_url_edit = QLineEdit(settings.voicevox_url)
        form.addRow("VOICEVOX Engine URL", self.voicevox_url_edit)

        self.speaker_id_box = QSpinBox()
        self.speaker_id_box.setRange(0, 999)
        self.speaker_id_box.setValue(settings.voicevox_speaker_id)
        form.addRow("VOICEVOX speaker id", self.speaker_id_box)

        self.ffmpeg_path_edit = QLineEdit(settings.ffmpeg_path)
        form.addRow("FFmpeg path", self.ffmpeg_path_edit)

        self.width_box = QSpinBox()
        self.width_box.setRange(360, 7680)
        self.width_box.setValue(settings.output_width)
        form.addRow("出力幅", self.width_box)

        self.height_box = QSpinBox()
        self.height_box.setRange(640, 7680)
        self.height_box.setValue(settings.output_height)
        form.addRow("出力高さ", self.height_box)

        self.seconds_box = QSpinBox()
        self.seconds_box.setRange(1, 60)
        self.seconds_box.setValue(settings.seconds_per_image)
        form.addRow("1画像あたりの秒数", self.seconds_box)

        self.zoom_check = QCheckBox("Ken Burns風ズームを使う")
        self.zoom_check.setChecked(settings.zoom_enabled)
        form.addRow("ズーム", self.zoom_check)

        layout.addLayout(form)
        layout.addWidget(QLabel("ジャンル（1行に1つ）"))

        self.genres_edit = QTextEdit()
        self.genres_edit.setPlainText("\n".join(settings.genres))
        layout.addWidget(self.genres_edit)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton("キャンセル")
        save_button = QPushButton("保存")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

    def get_settings(self) -> AppSettings:
        genres = [line.strip() for line in self.genres_edit.toPlainText().splitlines() if line.strip()]
        return AppSettings(
            default_duration=self.duration_box.currentText(),
            default_image_count=self.image_count_box.value(),
            save_dir=self.save_dir_edit.text().strip(),
            genres=genres,
            video_editor_engine=self.video_editor_box.currentText(),
            voicevox_url=self.voicevox_url_edit.text().strip() or "http://127.0.0.1:50021",
            voicevox_speaker_id=self.speaker_id_box.value(),
            ffmpeg_path=self.ffmpeg_path_edit.text().strip() or "ffmpeg",
            output_width=self.width_box.value(),
            output_height=self.height_box.value(),
            seconds_per_image=self.seconds_box.value(),
            zoom_enabled=self.zoom_check.isChecked(),
        )

    def _select_save_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "保存先を選択", self.save_dir_edit.text())
        if selected:
            self.save_dir_edit.setText(str(Path(selected)))
