from __future__ import annotations

import json

import pytest

from models import AppSettings
from services.subtitle_service import SubtitleError, SubtitleService


def test_subtitle_json_converts_to_ass(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    subtitles = [
        {"start": 0.0, "end": 2.8, "text": "ブラックホールは\n謎の天体です"},
        {"start": 2.8, "end": 5.6, "text": "光さえ逃げられません"},
    ]
    (project / "subtitles.txt").write_text(json.dumps(subtitles, ensure_ascii=False), encoding="utf-8")

    path = SubtitleService().generate_for_project(project, AppSettings(subtitle_font_size=72, subtitle_position="下"))

    assert path == project / "video" / "subtitles.ass"
    text = path.read_text(encoding="utf-8")
    assert "PlayResX: 1080" in text
    assert "Style: Default,Yu Gothic,72" in text
    assert "0:00:00.00,0:00:02.80" in text
    assert r"ブラックホールは\N謎の天体です" in text


def test_empty_subtitle_does_not_fail(tmp_path) -> None:
    project = tmp_path / "project"
    project.mkdir()
    (project / "subtitles.txt").write_text("", encoding="utf-8")

    assert SubtitleService().generate_for_project(project, AppSettings()) is None


def test_broken_subtitle_data_raises_japanese_error() -> None:
    with pytest.raises(SubtitleError, match="字幕JSONの形式が正しくありません|秒数の数値"):
        SubtitleService().parse_subtitles('[{"start": "bad", "end": 2, "text": "字幕"}]')


def test_subtitle_settings_are_reflected() -> None:
    settings = AppSettings(
        subtitle_font_size=80,
        subtitle_position="上",
        subtitle_outline=8,
        subtitle_shadow_enabled=False,
    )
    ass = SubtitleService().build_ass([SubtitleService().parse_subtitles('[{"start":0,"end":2,"text":"上字幕"}]')[0]], settings)

    assert "Yu Gothic,80" in ass
    assert ",1,8,0,8,80,80,120,1" in ass
