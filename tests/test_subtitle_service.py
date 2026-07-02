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


def test_subtitles_auto_split() -> None:
    # A single very long cue should be split
    text = '[{"start": 0.0, "end": 10.0, "text": "私たちは、その光を観測することでブラックホールの存在を知っています。そして中心には『特異点』と呼ばれる場所があると考えられていますが、そこで何が起きているのかは、今の科学でも説明できません。"}]'
    cues = SubtitleService().parse_subtitles(text)
    
    # It should split into multiple cues
    assert len(cues) > 1
    
    # Timings should be distributed proportionally
    assert cues[0].start == 0.0
    assert cues[-1].end == 10.0
    
    # Check that no cue has text longer than 28 characters
    for cue in cues:
        assert len(cue.text) <= 28
        assert cue.start < cue.end


def test_subtitles_auto_wrap() -> None:
    # A single line longer than 15 characters should be auto-wrapped with a newline (\N) in ASS
    cue = SubtitleService().parse_subtitles('[{"start": 0.0, "end": 3.0, "text": "とても小さな場所に大量の重さが集まった天体です。"}]')[0]
    settings = AppSettings()
    ass = SubtitleService().build_ass([cue], settings)
    
    # It should have a line break \N in the dialogue event
    assert r"とても小さな場所に大量の\N重さが集まった天体です。" in ass
