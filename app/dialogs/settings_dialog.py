from __future__ import annotations

import hashlib
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDoubleSpinBox,
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
        self.settings = settings

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

        self.motion_style_box = QComboBox()
        self.motion_style_box.addItems([
            "Static",
            "Slow Zoom In",
            "Slow Zoom Out",
            "Pan Left",
            "Pan Right",
            "Pan Up",
            "Pan Down",
            "Ken Burns",
            "Random Motion",
        ])
        self.motion_style_box.setCurrentText(getattr(settings, "motion_style", "Random Motion"))
        form.addRow("Motion Style", self.motion_style_box)

        self.zoom_speed_box = QComboBox()
        self.zoom_speed_box.addItems(["Slow", "Normal", "Fast"])
        self.zoom_speed_box.setCurrentText(getattr(settings, "zoom_speed", "Normal"))
        form.addRow("ズーム速度", self.zoom_speed_box)

        self.transition_type_box = QComboBox()
        self.transition_type_box.addItems(["Fade", "Cross Fade", "Zoom Fade", "Slide", "None"])
        self.transition_type_box.setCurrentText(getattr(settings, "transition_type", "Cross Fade"))
        form.addRow("トランジション", self.transition_type_box)

        self.overlay_opacity_box = QSpinBox()
        self.overlay_opacity_box.setRange(10, 50)
        self.overlay_opacity_box.setValue(getattr(settings, "overlay_opacity", 30))
        self.overlay_opacity_box.setSuffix("%")
        form.addRow("宇宙オーバーレイ透明度", self.overlay_opacity_box)

        self.light_effect_box = QComboBox()
        self.light_effect_box.addItems(["OFF", "Lens Flare", "Glow", "Soft Light"])
        self.light_effect_box.setCurrentText(getattr(settings, "light_effect", "OFF"))
        form.addRow("Light Effect", self.light_effect_box)

        self.bgm_enabled_check = QCheckBox("BGMを使用する")
        self.bgm_enabled_check.setChecked(settings.bgm_enabled)
        form.addRow("BGM", self.bgm_enabled_check)

        self.bgm_volume_box = QSpinBox()
        self.bgm_volume_box.setRange(0, 100)
        self.bgm_volume_box.setValue(settings.bgm_volume_percent)
        self.bgm_volume_box.setSuffix("%")
        form.addRow("BGM音量", self.bgm_volume_box)

        self.intro_enabled_check = QCheckBox("オープニングを使用する")
        self.intro_enabled_check.setChecked(settings.intro_enabled)
        form.addRow("オープニング", self.intro_enabled_check)

        self.ending_enabled_check = QCheckBox("エンディングを使用する")
        self.ending_enabled_check.setChecked(settings.ending_enabled)
        self.intro_duration_box = QSpinBox()
        self.intro_duration_box.setRange(1, 60)
        self.intro_duration_box.setValue(getattr(settings, "intro_duration_seconds", 3))
        self.intro_duration_box.setSuffix(" 秒")

        self.intro_motion_box = QComboBox()
        self.intro_motion_box.addItems(["Static", "Slow Zoom In", "Slow Zoom Out"])
        self.intro_motion_box.setCurrentText(getattr(settings, "intro_motion", "Slow Zoom In"))

        self.intro_audio_mode_box = QComboBox()
        self.intro_audio_mode_box.addItems(["Original", "BGM", "Original + BGM", "Mute"])
        self.intro_audio_mode_box.setCurrentText(getattr(settings, "intro_audio_mode", "Original"))

        self.intro_bgm_volume_box = QSpinBox()
        self.intro_bgm_volume_box.setRange(0, 100)
        self.intro_bgm_volume_box.setValue(getattr(settings, "intro_bgm_volume_percent", 20))
        self.intro_bgm_volume_box.setSuffix("%")

        self.ending_duration_box = QSpinBox()
        self.ending_duration_box.setRange(1, 60)
        self.ending_duration_box.setValue(getattr(settings, "ending_duration_seconds", 3))
        self.ending_duration_box.setSuffix(" 秒")

        self.ending_motion_box = QComboBox()
        self.ending_motion_box.addItems(["Static", "Slow Zoom In", "Slow Zoom Out"])
        self.ending_motion_box.setCurrentText(getattr(settings, "ending_motion", "Slow Zoom Out"))

        self.ending_audio_mode_box = QComboBox()
        self.ending_audio_mode_box.addItems(["Original", "BGM", "Original + BGM", "Mute"])
        self.ending_audio_mode_box.setCurrentText(getattr(settings, "ending_audio_mode", "Original"))

        self.ending_bgm_volume_box = QSpinBox()
        self.ending_bgm_volume_box.setRange(0, 100)
        self.ending_bgm_volume_box.setValue(getattr(settings, "ending_bgm_volume_percent", 20))
        self.ending_bgm_volume_box.setSuffix("%")

        form.addRow("イントロ表示時間", self.intro_duration_box)
        form.addRow("イントロズーム", self.intro_motion_box)
        form.addRow("イントロ音声", self.intro_audio_mode_box)
        form.addRow("イントロBGM音量", self.intro_bgm_volume_box)
        form.addRow("エンディング表示時間", self.ending_duration_box)
        form.addRow("エンディングズーム", self.ending_motion_box)
        form.addRow("エンディング音声", self.ending_audio_mode_box)
        form.addRow("エンディングBGM音量", self.ending_bgm_volume_box)
        form.addRow("エンディング", self.ending_enabled_check)

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

        self.title_enabled_check = QCheckBox("タイトルを表示")
        self.title_enabled_check.setChecked(settings.title_enabled)
        form.addRow("タイトル表示", self.title_enabled_check)

        self.title_size_box = QSpinBox()
        self.title_size_box.setRange(24, 160)
        self.title_size_box.setValue(settings.title_size)
        form.addRow("タイトルサイズ", self.title_size_box)

        self.title_position_box = QComboBox()
        self.title_position_box.addItems(["上", "上（左寄せ）", "中央", "下"])
        self.title_position_box.setCurrentText(settings.title_position)
        form.addRow("タイトル位置", self.title_position_box)

        self.title_bg_check = QCheckBox("半透明背景")
        self.title_bg_check.setChecked(settings.title_bg_enabled)
        form.addRow("タイトル背景", self.title_bg_check)

        self.title_duration_box = QComboBox()
        self.title_duration_box.addItems(["常に表示", "3秒", "5秒", "10秒"])
        self.title_duration_box.setCurrentText(settings.title_duration)
        form.addRow("タイトル表示時間", self.title_duration_box)

        self.title_preset_box = QComboBox()
        self.title_preset_box.addItems(["宇宙ドキュメンタリー風", "シンプル", "情報番組風", "ニュース風", "インパクト強め"])
        self.title_preset_box.setCurrentText(getattr(settings, "title_preset", "宇宙ドキュメンタリー風"))
        form.addRow("タイトルデザインプリセット", self.title_preset_box)

        self.title_highlight_check = QCheckBox("重要語を強調する")
        self.title_highlight_check.setChecked(getattr(settings, "title_highlight_enabled", True))
        form.addRow("タイトル強調", self.title_highlight_check)

        self.title_bg_opacity_box = QSpinBox()
        self.title_bg_opacity_box.setRange(0, 100)
        self.title_bg_opacity_box.setValue(getattr(settings, "title_bg_opacity", 50))
        form.addRow("タイトル背景透明度", self.title_bg_opacity_box)

        self.title_padding_box = QSpinBox()
        self.title_padding_box.setRange(0, 100)
        self.title_padding_box.setValue(getattr(settings, "title_padding", 15))
        form.addRow("タイトル余白", self.title_padding_box)

        self.title_width_percent_box = QSpinBox()
        self.title_width_percent_box.setRange(10, 100)
        self.title_width_percent_box.setValue(getattr(settings, "title_width_percent", 90))
        form.addRow("タイトル横幅%", self.title_width_percent_box)

        self.title_line_spacing_box = QSpinBox()
        self.title_line_spacing_box.setRange(0, 100)
        self.title_line_spacing_box.setValue(getattr(settings, "title_line_spacing", 10))
        form.addRow("タイトル行間", self.title_line_spacing_box)

        self.image_common_conditions_edit = QTextEdit()
        self.image_common_conditions_edit.setPlainText(settings.image_common_conditions)
        self.image_common_conditions_edit.setFixedHeight(120)
        form.addRow("画像共通条件", self.image_common_conditions_edit)

        self.image_generation_provider_box = QComboBox()
        self.image_generation_provider_box.addItems(["cloudflare_workers_ai"])
        self.image_generation_provider_box.setCurrentText(getattr(settings, "image_generation_provider", "cloudflare_workers_ai"))
        form.addRow("AI画像Provider", self.image_generation_provider_box)

        self.image_generation_model_box = QComboBox()
        self.image_generation_model_box.addItems(["@cf/black-forest-labs/flux-1-schnell"])
        self.image_generation_model_box.setCurrentText(getattr(settings, "image_generation_model", "@cf/black-forest-labs/flux-1-schnell"))
        form.addRow("AI画像Model", self.image_generation_model_box)

        self.image_generation_steps_box = QSpinBox()
        self.image_generation_steps_box.setRange(1, 8)
        self.image_generation_steps_box.setValue(int(getattr(settings, "image_generation_steps", 4)))
        form.addRow("AI画像Steps", self.image_generation_steps_box)

        self.image_generation_max_run_box = QSpinBox()
        self.image_generation_max_run_box.setRange(1, 8)
        self.image_generation_max_run_box.setValue(int(getattr(settings, "image_generation_max_images_per_run", 8)))
        form.addRow("AI画像 1回上限", self.image_generation_max_run_box)

        self.image_generation_retry_box = QSpinBox()
        self.image_generation_retry_box.setRange(0, 5)
        self.image_generation_retry_box.setValue(int(getattr(settings, "image_generation_max_retries_per_image", 2)))
        form.addRow("AI画像 retry/枚", self.image_generation_retry_box)

        self.image_generation_daily_limit_box = QSpinBox()
        self.image_generation_daily_limit_box.setRange(0, 1000)
        self.image_generation_daily_limit_box.setValue(int(getattr(settings, "image_generation_daily_request_limit", 20)))
        form.addRow("AI画像 日次上限", self.image_generation_daily_limit_box)

        self.image_generation_project_limit_box = QSpinBox()
        self.image_generation_project_limit_box.setRange(0, 1000)
        self.image_generation_project_limit_box.setValue(int(getattr(settings, "image_generation_project_limit", 40)))
        form.addRow("AI画像 project上限", self.image_generation_project_limit_box)

        self.image_prompt_optimizer_check = QCheckBox("Prompt Optimizer ON")
        self.image_prompt_optimizer_check.setChecked(bool(getattr(settings, "image_prompt_optimizer_enabled", True)))
        form.addRow("AI Image Prompt Optimizer", self.image_prompt_optimizer_check)

        self.default_story_provider_box = QComboBox()
        self.default_story_provider_box.addItem("Gemini", "gemini")
        self.default_story_provider_box.addItem("OpenAI", "openai")
        self.default_story_provider_box.addItem("Mock", "mock")
        self.default_story_provider_box.addItem("Manual Prompt", "manual_prompt")
        provider_index = self.default_story_provider_box.findData(str(getattr(settings, "default_story_provider", "gemini")))
        self.default_story_provider_box.setCurrentIndex(provider_index if provider_index >= 0 else 0)
        form.addRow("Story AI Provider", self.default_story_provider_box)

        self.default_story_model_box = QComboBox()
        self.default_story_model_box.addItems(["gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol", "Custom"])
        current_story_model = str(getattr(settings, "default_story_model", "gemini-3.5-flash-lite"))
        self.default_story_model_box.setCurrentText(
            current_story_model
            if current_story_model in {"gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"}
            else "Custom"
        )
        self.custom_story_model_edit = QLineEdit(
            ""
            if current_story_model in {"gemini-3.5-flash-lite", "gemini-3.5-flash", "gemini-3.6-flash", "gpt-5.6-luna", "gpt-5.6-terra", "gpt-5.6-sol"}
            else current_story_model
        )
        model_row = QHBoxLayout()
        model_row.addWidget(self.default_story_model_box)
        model_row.addWidget(self.custom_story_model_edit)
        form.addRow("Story AI Model", model_row)

        self.story_reasoning_box = QComboBox()
        self.story_reasoning_box.addItems(["none", "low", "medium", "high"])
        self.story_reasoning_box.setCurrentText(str(getattr(settings, "default_reasoning_effort", "low")))
        form.addRow("Story Reasoning Effort", self.story_reasoning_box)

        self.story_max_output_box = QSpinBox()
        self.story_max_output_box.setRange(512, 20000)
        self.story_max_output_box.setValue(int(getattr(settings, "default_max_output_tokens", 4096)))
        form.addRow("Story Max Output Tokens", self.story_max_output_box)

        self.story_retry_box = QSpinBox()
        self.story_retry_box.setRange(0, 5)
        self.story_retry_box.setValue(int(getattr(settings, "story_provider_retry_count", 2)))
        form.addRow("Story Retry Count", self.story_retry_box)

        self.story_timeout_box = QSpinBox()
        self.story_timeout_box.setRange(10, 600)
        self.story_timeout_box.setValue(int(getattr(settings, "story_provider_timeout_seconds", 60)))
        self.story_timeout_box.setSuffix(" sec")
        form.addRow("Story Timeout", self.story_timeout_box)

        self.gemini_free_tier_only_check = QCheckBox("Free-tier-only")
        self.gemini_free_tier_only_check.setChecked(bool(getattr(settings, "gemini_free_tier_only", True)))
        form.addRow("Gemini Free-tier-only", self.gemini_free_tier_only_check)

        self.gemini_project_free_check = QCheckBox("Google AI StudioでProject TierがFreeであることを確認済み")
        self.gemini_project_free_check.setChecked(bool(getattr(settings, "gemini_project_free_tier_confirmed", False)))
        form.addRow("Gemini Project Tier確認", self.gemini_project_free_check)

        self.gemini_billing_disabled_check = QCheckBox("このProjectでBillingを有効化していないことを確認済み")
        self.gemini_billing_disabled_check.setChecked(bool(getattr(settings, "gemini_billing_disabled_confirmed", False)))
        form.addRow("Gemini Billing確認", self.gemini_billing_disabled_check)

        self.gemini_daily_cap_box = QSpinBox()
        self.gemini_daily_cap_box.setRange(0, 1000)
        self.gemini_daily_cap_box.setValue(int(getattr(settings, "gemini_local_daily_request_cap", 10)))
        form.addRow("Gemini local daily cap", self.gemini_daily_cap_box)

        self.gemini_temperature_box = QDoubleSpinBox()
        self.gemini_temperature_box.setRange(0.0, 2.0)
        self.gemini_temperature_box.setSingleStep(0.1)
        self.gemini_temperature_box.setValue(float(getattr(settings, "gemini_temperature", 0.7)))
        form.addRow("Gemini temperature", self.gemini_temperature_box)

        layout.addLayout(form)

        bgm_folder_button = QPushButton("BGMフォルダを開く")
        bgm_folder_button.clicked.connect(self.open_bgm_folder)
        layout.addWidget(bgm_folder_button)
        intro_folder_button = QPushButton("オープニングフォルダを開く")
        intro_folder_button.clicked.connect(self.open_intro_folder)
        layout.addWidget(intro_folder_button)
        ending_folder_button = QPushButton("エンディングフォルダを開く")
        ending_folder_button.clicked.connect(self.open_ending_folder)
        layout.addWidget(ending_folder_button)
        overlay_folder_button = QPushButton("Overlayフォルダを開く")
        overlay_folder_button.clicked.connect(self.open_overlay_folder)
        layout.addWidget(overlay_folder_button)

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
        gemini_confirmation = self._gemini_confirmation_state()
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
            intro_enabled=self.intro_enabled_check.isChecked(),
            ending_enabled=self.ending_enabled_check.isChecked(),
            intro_duration_seconds=self.intro_duration_box.value(),
            ending_duration_seconds=self.ending_duration_box.value(),
            intro_motion=self.intro_motion_box.currentText(),
            ending_motion=self.ending_motion_box.currentText(),
            intro_audio_mode=self.intro_audio_mode_box.currentText(),
            ending_audio_mode=self.ending_audio_mode_box.currentText(),
            intro_bgm_volume_percent=self.intro_bgm_volume_box.value(),
            ending_bgm_volume_percent=self.ending_bgm_volume_box.value(),
            subtitles_enabled=self.subtitles_enabled_check.isChecked(),
            subtitle_font_size=self.subtitle_font_size_box.value(),
            subtitle_position=self.subtitle_position_box.currentText(),
            subtitle_outline=self.subtitle_outline_box.value(),
            subtitle_shadow_enabled=self.subtitle_shadow_check.isChecked(),
            title_enabled=self.title_enabled_check.isChecked(),
            title_size=self.title_size_box.value(),
            title_position=self.title_position_box.currentText(),
            title_bg_enabled=self.title_bg_check.isChecked(),
            title_duration=self.title_duration_box.currentText(),
            title_preset=self.title_preset_box.currentText(),
            title_highlight_enabled=self.title_highlight_check.isChecked(),
            title_bg_opacity=self.title_bg_opacity_box.value(),
            title_padding=self.title_padding_box.value(),
            title_width_percent=self.title_width_percent_box.value(),
            title_line_spacing=self.title_line_spacing_box.value(),
            motion_style=self.motion_style_box.currentText(),
            zoom_speed=self.zoom_speed_box.currentText(),
            transition_type=self.transition_type_box.currentText(),
            overlay_opacity=self.overlay_opacity_box.value(),
            light_effect=self.light_effect_box.currentText(),
            image_generation_provider=self.image_generation_provider_box.currentText(),
            image_generation_model=self.image_generation_model_box.currentText(),
            image_generation_steps=self.image_generation_steps_box.value(),
            image_generation_max_images_per_run=self.image_generation_max_run_box.value(),
            image_generation_max_retries_per_image=self.image_generation_retry_box.value(),
            image_generation_daily_request_limit=self.image_generation_daily_limit_box.value(),
            image_generation_project_limit=self.image_generation_project_limit_box.value(),
            image_prompt_optimizer_enabled=self.image_prompt_optimizer_check.isChecked(),
            default_story_provider=str(self.default_story_provider_box.currentData() or "gemini"),
            default_story_model=self._selected_story_model(),
            default_reasoning_effort=self.story_reasoning_box.currentText(),
            default_max_output_tokens=self.story_max_output_box.value(),
            story_provider_retry_count=self.story_retry_box.value(),
            story_provider_timeout_seconds=self.story_timeout_box.value(),
            default_gemini_model=self._selected_story_model() if self._selected_story_model().startswith("gemini-") else "gemini-3.5-flash-lite",
            gemini_free_tier_only=self.gemini_free_tier_only_check.isChecked(),
            gemini_project_free_tier_confirmed=self.gemini_project_free_check.isChecked(),
            gemini_project_free_tier_confirmed_at=gemini_confirmation["project_confirmed_at"],
            gemini_billing_disabled_confirmed=self.gemini_billing_disabled_check.isChecked(),
            gemini_billing_disabled_confirmed_at=gemini_confirmation["billing_confirmed_at"],
            gemini_confirmation_key_fingerprint=gemini_confirmation["fingerprint"],
            gemini_confirmation_version=gemini_confirmation["version"],
            gemini_local_daily_request_cap=self.gemini_daily_cap_box.value(),
            gemini_retry_count=self.story_retry_box.value(),
            gemini_timeout_seconds=self.story_timeout_box.value(),
            gemini_temperature=self.gemini_temperature_box.value(),
            gemini_max_output_tokens=self.story_max_output_box.value(),
            image_common_conditions=self.image_common_conditions_edit.toPlainText().strip()
            or "・9:16\n・4K\n・文字なし\n・リアル\n・映画風\n・ドキュメンタリー風",
        )

    def _gemini_confirmation_state(self) -> dict[str, str]:
        both_confirmed = self.gemini_project_free_check.isChecked() and self.gemini_billing_disabled_check.isChecked()
        if not both_confirmed:
            return {
                "project_confirmed_at": "",
                "billing_confirmed_at": "",
                "fingerprint": "",
                "version": "1.0",
            }
        fingerprint = self._current_gemini_key_fingerprint()
        if not fingerprint:
            return {
                "project_confirmed_at": "",
                "billing_confirmed_at": "",
                "fingerprint": "",
                "version": "1.0",
            }
        existing_fingerprint = str(getattr(self.settings, "gemini_confirmation_key_fingerprint", ""))
        reuse_existing = existing_fingerprint == fingerprint
        now = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        return {
            "project_confirmed_at": str(getattr(self.settings, "gemini_project_free_tier_confirmed_at", "")) if reuse_existing else now,
            "billing_confirmed_at": str(getattr(self.settings, "gemini_billing_disabled_confirmed_at", "")) if reuse_existing else now,
            "fingerprint": fingerprint,
            "version": "1.0",
        }

    def _current_gemini_key_fingerprint(self) -> str:
        load_dotenv()
        api_key = os.environ.get("GEMINI_API_KEY", "").strip()
        if not api_key:
            return ""
        return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:16]

    def _selected_story_model(self) -> str:
        if self.default_story_model_box.currentText() != "Custom":
            return self.default_story_model_box.currentText()
        custom = self.custom_story_model_edit.text().strip()
        if not custom or len(custom) > 120 or any(ord(ch) < 32 for ch in custom):
            return "gemini-3.5-flash-lite"
        return custom

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

    def open_intro_folder(self) -> None:
        if self.paths is None:
            QMessageBox.information(self, "オープニングフォルダ", "保存先の情報がないため開けません。")
            return
        self.paths.intro_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.paths.intro_dir)

    def open_ending_folder(self) -> None:
        if self.paths is None:
            QMessageBox.information(self, "エンディングフォルダ", "保存先の情報がないため開けません。")
            return
        self.paths.ending_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.paths.ending_dir)

    def open_overlay_folder(self) -> None:
        if self.paths is None:
            QMessageBox.information(self, "Overlayフォルダ", "保存先の情報がないため開けません。")
            return
        self.paths.overlay_dir.mkdir(parents=True, exist_ok=True)
        os.startfile(self.paths.overlay_dir)
