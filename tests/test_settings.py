from __future__ import annotations

from config import AppPaths
from services.settings_service import SettingsService


def test_settings_roundtrip(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    service = SettingsService(paths)
    settings = service.load()
    settings.voicevox_url = "http://127.0.0.1:50021"
    settings.voicevox_speaker_id = 3
    settings.ffmpeg_path = "ffmpeg"
    settings.bgm_enabled = True
    settings.bgm_volume_percent = 35
    service.save(settings)
    loaded = service.load()
    assert loaded.voicevox_speaker_id == 3
    assert loaded.ffmpeg_path == "ffmpeg"
    assert loaded.bgm_enabled is True
    assert loaded.bgm_volume_percent == 35
