from __future__ import annotations

import os
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
    QScrollArea,
    QSpinBox,
    QTextEdit,
    QVBoxLayout,
    QMessageBox,
    QWidget,
)

from config import AppPaths
from models import AppSettings, DEFAULT_DURATIONS
from services.diagnostics_service import DiagnosticsService


class SettingsDialog(QDialog):
    """Phase4の設定を変更する画面です。"""

    def __init__(self, settings: AppSettings, paths: AppPaths | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("設定")
        self.resize(640, 620)
        self.paths = paths

        root_layout = QVBoxLayout(self)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content = QWidget()
        layout = QVBoxLayout(content)
        form = QFormLayout()

        self.duration_box = QComboBox()
        self.duration_box.addItems(DEFAULT_DURATIONS)
        self.duration_box.setCurrentText(settings.default_duration)
        form.addRow("デフォルト動画時間", self.duration_box)

        self.image_count_box = QComboBox()
        self.image_count_box.addItems(["3", "4", "5", "6", "8"])
        self.image_count_box.setCurrentText(str(settings.default_image_count if settings.default_image_count in {3, 4, 5, 6, 8} else 5))
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

        self.bgm_enabled_check = QCheckBox("BGMを使用する")
        self.bgm_enabled_check.setChecked(settings.bgm_enabled)
        form.addRow("BGM", self.bgm_enabled_check)

        self.bgm_volume_box = QSpinBox()
        self.bgm_volume_box.setRange(0, 100)
        self.bgm_volume_box.setValue(settings.bgm_volume_percent)
        self.bgm_volume_box.setSuffix("%")
        form.addRow("BGM音量", self.bgm_volume_box)

        self.subtitles_enabled_check = QCheckBox("字幕を使用する")
        self.subtitles_enabled_check.setChecked(settings.subtitles_enabled)
        form.addRow("字幕", self.subtitles_enabled_check)

        self.subtitle_font_size_box = QSpinBox()
        self.subtitle_font_size_box.setRange(24, 160)
        self.subtitle_font_size_box.setValue(settings.subtitle_font_size)
        form.addRow("字幕フォントサイズ", self.subtitle_font_size_box)

        self.subtitle_position_box = QComboBox()
        self.subtitle_position_box.addItems(["下", "中央", "上"])
        self.subtitle_position_box.setCurrentText(settings.subtitle_position)
        form.addRow("字幕位置", self.subtitle_position_box)

        self.subtitle_outline_box = QSpinBox()
        self.subtitle_outline_box.setRange(0, 16)
        self.subtitle_outline_box.setValue(settings.subtitle_outline)
        form.addRow("字幕アウトライン太さ", self.subtitle_outline_box)

        self.subtitle_shadow_check = QCheckBox("字幕影を使う")
        self.subtitle_shadow_check.setChecked(settings.subtitle_shadow_enabled)
        form.addRow("字幕影", self.subtitle_shadow_check)

        self.image_common_conditions_edit = QTextEdit()
        self.image_common_conditions_edit.setPlainText(settings.image_common_conditions)
        self.image_common_conditions_edit.setFixedHeight(120)
        form.addRow("画像共通条件", self.image_common_conditions_edit)

        layout.addLayout(form)

        bgm_folder_button = QPushButton("BGMフォルダを開く")
        bgm_folder_button.clicked.connect(self.open_bgm_folder)
        layout.addWidget(bgm_folder_button)

        layout.addWidget(QLabel("ジャンル（1行に1つ）"))

        self.genres_edit = QTextEdit()
        self.genres_edit.setPlainText("\n".join(settings.genres))
        layout.addWidget(self.genres_edit)

        diagnostics_button = QPushButton("環境チェック")
        diagnostics_button.clicked.connect(self.run_diagnostics)
        layout.addWidget(diagnostics_button)
        scroll.setWidget(content)
        root_layout.addWidget(scroll)

        buttons = QHBoxLayout()
        buttons.addStretch()
        cancel_button = QPushButton("キャンセル")
        save_button = QPushButton("保存")
        cancel_button.clicked.connect(self.reject)
        save_button.clicked.connect(self.accept)
        buttons.addWidget(cancel_button)
        buttons.addWidget(save_button)
        root_layout.addLayout(buttons)

    def get_settings(self) -> AppSettings:
        genres = [line.strip() for line in self.genres_edit.toPlainText().splitlines() if line.strip()]
        return AppSettings(
            default_duration=self.duration_box.currentText(),
            default_image_count=int(self.image_count_box.currentText()),
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
            bgm_enabled=self.bgm_enabled_check.isChecked(),
            bgm_volume_percent=self.bgm_volume_box.value(),
            subtitles_enabled=self.subtitles_enabled_check.isChecked(),
            subtitle_font_size=self.subtitle_font_size_box.value(),
            subtitle_position=self.subtitle_position_box.currentText(),
            subtitle_outline=self.subtitle_outline_box.value(),
            subtitle_shadow_enabled=self.subtitle_shadow_check.isChecked(),
            image_common_conditions=self.image_common_conditions_edit.toPlainText().strip()
            or "・9:16\n・4K\n・文字なし\n・リアル\n・映画風\n・ドキュメンタリー風",
        )

    def _select_save_dir(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "保存先を選択", self.save_dir_edit.text())
        if selected:
            self.save_dir_edit.setText(str(Path(selected)))

    def run_diagnostics(self) -> None:
        if self.paths is None:
            QMessageBox.information(self, "環境チェック", "保存先の情報がないため確認できません。")
            return
        settings = self.get_settings()
        lines = [
            f"{item.status}: {item.name} - {item.message}"
            for item in DiagnosticsService(self.paths, settings).run()
        ]
        QMessageBox.information(self, "環境チェック", "\n".join(lines))

    def open_bgm_folder(self) -> None:
        if self.paths is None:
            QMessageBox.information(self, "BGMフォルダ", "保存先の情報がないため開けません。")
            return
        self.paths.bgm_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.paths.bgm_dir)
