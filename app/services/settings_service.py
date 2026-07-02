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
        )

    def save(self, settings: AppSettings) -> None:
        self.paths.settings_path.write_text(
            json.dumps(settings.__dict__, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
