from __future__ import annotations

import json

from config import AppPaths
from models import AppSettings, DEFAULT_GENRES


class SettingsService:
    """settings.jsonの読み書きを担当します。"""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load(self) -> AppSettings:
        path = self.paths.settings_path
        if not path.exists():
            return AppSettings(save_dir=str(self.paths.base_dir), genres=DEFAULT_GENRES.copy())

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return AppSettings(save_dir=str(self.paths.base_dir), genres=DEFAULT_GENRES.copy())

        return AppSettings(
            default_duration=data.get("default_duration", "90秒"),
            default_image_count=int(data.get("default_image_count", 5)),
            save_dir=data.get("save_dir") or str(self.paths.base_dir),
            genres=data.get("genres") or DEFAULT_GENRES.copy(),
            video_editor_engine=data.get("video_editor_engine", "ffmpeg"),
            voicevox_url=data.get("voicevox_url", "http://127.0.0.1:50021"),
            voicevox_speaker_id=int(data.get("voicevox_speaker_id", 3)),
            ffmpeg_path=data.get("ffmpeg_path", "ffmpeg"),
            output_width=int(data.get("output_width", 1080)),
            output_height=int(data.get("output_height", 1920)),
            seconds_per_image=int(data.get("seconds_per_image", 5)),
            zoom_enabled=bool(data.get("zoom_enabled", True)),
            bgm_enabled=bool(data.get("bgm_enabled", True)),
            bgm_volume_percent=int(data.get("bgm_volume_percent", 20)),
            subtitles_enabled=bool(data.get("subtitles_enabled", True)),
            subtitle_font_size=int(data.get("subtitle_font_size", 64)),
            subtitle_position=data.get("subtitle_position", "下"),
            subtitle_outline=int(data.get("subtitle_outline", 4)),
            subtitle_shadow_enabled=bool(data.get("subtitle_shadow_enabled", True)),
            title_enabled=bool(data.get("title_enabled", False)),
            title_size=int(data.get("title_size", 72)),
            title_position=data.get("title_position", "上"),
            title_bg_enabled=bool(data.get("title_bg_enabled", True)),
            title_duration=data.get("title_duration", "常に表示"),
            title_preset=data.get("title_preset", "宇宙ドキュメンタリー風"),
            title_highlight_enabled=bool(data.get("title_highlight_enabled", True)),
            title_bg_opacity=int(data.get("title_bg_opacity", 50)),
            title_padding=int(data.get("title_padding", 15)),
            title_width_percent=int(data.get("title_width_percent", 90)),
            title_line_spacing=int(data.get("title_line_spacing", 10)),
            image_common_conditions=data.get(
                "image_common_conditions",
                "・9:16\n・4K\n・文字なし\n・リアル\n・映画風\n・ドキュメンタリー風",
            ),
        )

    def save(self, settings: AppSettings) -> None:
        self.paths.settings_path.write_text(
            json.dumps(settings.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
