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


def test_default_subtitle_position_uses_short_safe_area() -> None:
    cue = SubtitleService().parse_subtitles('[{"start":0,"end":2,"text":"安全位置の字幕"}]')[0]
    ass = SubtitleService().build_ass([cue], AppSettings(subtitle_position="下"))

    assert ",2,80,80,720,1" in ass


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


def test_title_overlay_missing_file(tmp_path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    
    settings = AppSettings(title_enabled=True, subtitles_enabled=False)
    # title.txt doesn't exist
    with pytest.raises(SubtitleError, match="title.txt が見つかりません。"):
        SubtitleService().generate_for_project(project_dir, settings)


def test_title_overlay_empty_file(tmp_path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "title.txt").write_text("", encoding="utf-8")
    
    settings = AppSettings(title_enabled=True, subtitles_enabled=False)
    with pytest.raises(SubtitleError, match="タイトルが空です。"):
        SubtitleService().generate_for_project(project_dir, settings)


def test_title_overlay_generation(tmp_path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    # A long title (> 14 chars) should wrap
    (project_dir / "title.txt").write_text("ブラックホールは宇宙最大の謎である", encoding="utf-8")
    (project_dir / "subtitles.txt").write_text("", encoding="utf-8")
    
    settings = AppSettings(title_enabled=True, subtitles_enabled=False, title_size=72, title_position="上")
    path = SubtitleService().generate_for_project(project_dir, settings)
    
    assert path == project_dir / "video" / "subtitles.ass"
    ass = path.read_text(encoding="utf-8")
    
    # Check style and formatting
    assert "Style: Title,Yu Gothic UI,72," in ass
    assert "170,1" in ass  # MarginV=170 for "上"
    
    # Check dialog event and wrap (17 chars: "ブラックホールは宇宙最大の謎である" -> "ブラックホールは\N宇宙最大の謎である")
    assert r"Dialogue: 1," in ass
    assert r"Title,,0,0,0,,ブラックホールは\N宇宙最大の謎である" in ass


def test_title_overlay_duration_and_position(tmp_path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "title.txt").write_text("動画タイトル", encoding="utf-8")
    (project_dir / "subtitles.txt").write_text('[{"start": 0.0, "end": 8.0, "text": "字幕"}]', encoding="utf-8")
    
    # 5 seconds duration, "中央" position, transparent bg
    settings = AppSettings(
        title_enabled=True,
        subtitles_enabled=True,
        title_position="中央",
        title_bg_enabled=False,
        title_duration="5秒"
    )
    
    path = SubtitleService().generate_for_project(project_dir, settings)
    ass = path.read_text(encoding="utf-8")
    
    # Position: "中央" -> Alignment=5, MarginV=0
    assert "Style: Title," in ass
    assert "Yu Gothic UI," in ass
    assert ",5,54,54,0,1" in ass  # Alignment=5, MarginV=0
    # Background disabled: BorderStyle=1
    assert ",1,2,0,5" in ass  # BorderStyle=1, Outline=2, Shadow=0
    
    # Duration: 5 seconds -> end time 0:00:05.00
    assert "0:00:00.00,0:00:05.00,Title" in ass


def test_title_overlay_presets(tmp_path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "title.txt").write_text("🔴⚠️🌌タイトル✅❓", encoding="utf-8")
    (project_dir / "subtitles.txt").write_text("", encoding="utf-8")
    
    # 1. Space documentary style (宇宙ドキュメンタリー風) - Default
    settings = AppSettings(
        title_enabled=True,
        subtitles_enabled=False,
        title_preset="宇宙ドキュメンタリー風",
        title_bg_opacity=60,
        title_width_percent=85,
        title_position="上（左寄せ）"
    )
    path = SubtitleService().generate_for_project(project_dir, settings)
    ass = path.read_text(encoding="utf-8")
    assert "Style: Title,Yu Gothic UI," in ass
    assert "&H00FFFFE0" in ass  # Light Cyan color
    assert "&H661A0A00" in ass  # BGR background color with 60% opacity (alpha = 255 - 153 = 102 = 66 hex)
    assert ",7," in ass  # Left-aligned (Alignment=7)
    assert ",81,81," in ass  # Left/Right margin based on 85% width: (1080 * 15) // 200 = 81
    assert "🔴⚠️🌌タイトル✅❓" in ass  # Emojis preserved and didn't crash
    
    # 2. Information show style (情報番組風) with decoration lines
    settings = AppSettings(
        title_enabled=True,
        subtitles_enabled=False,
        title_preset="情報番組風",
        title_bg_opacity=50
    )
    path = SubtitleService().generate_for_project(project_dir, settings)
    ass = path.read_text(encoding="utf-8")
    assert "━━━━━━━━━━━━" in ass  # Lines added
    assert "&H80000000" in ass  # 50% opacity black
    
    # 3. High impact style (インパクト強め) with decoration lines, larger size
    settings = AppSettings(
        title_enabled=True,
        subtitles_enabled=False,
        title_preset="インパクト強め",
        title_size=60
    )
    path = SubtitleService().generate_for_project(project_dir, settings)
    ass = path.read_text(encoding="utf-8")
    assert "Style: Title,Meiryo,72" in ass  # 60 * 1.2 = 72
    assert "&H0000FFFF" in ass  # Yellow
    
    # 4. News style (ニュース風)
    settings = AppSettings(
        title_enabled=True,
        subtitles_enabled=False,
        title_preset="ニュース風",
        title_bg_opacity=100
    )
    path = SubtitleService().generate_for_project(project_dir, settings)
    ass = path.read_text(encoding="utf-8")
    assert "Style: Title,Meiryo," in ass
    assert "&H00000000" in ass  # 100% opacity (alpha = 00 hex)


def test_title_overlay_highlighting(tmp_path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    (project_dir / "title.txt").write_text("【ブラックホール】に落ちると？", encoding="utf-8")
    (project_dir / "subtitles.txt").write_text("", encoding="utf-8")
    
    # Highlight Enabled (Default)
    settings = AppSettings(
        title_enabled=True,
        subtitles_enabled=False,
        title_preset="宇宙ドキュメンタリー風",
        title_size=70,
        title_highlight_enabled=True
    )
    path = SubtitleService().generate_for_project(project_dir, settings)
    ass = path.read_text(encoding="utf-8")
    # Should contain color and size tag for highlighted word, then \r reset
    assert r"{\c&H0080FFFF&}{\fs80}{\b1}ブラックホー\Nル{\r}に落ちると？" in ass
    
    # Highlight Disabled
    settings.title_highlight_enabled = False
    path = SubtitleService().generate_for_project(project_dir, settings)
    ass = path.read_text(encoding="utf-8")
    # Brackets stripped, no tags, but still wrapped
    assert r"ブラックホー\Nルに落ちると？" in ass
    assert r"\c&H" not in ass

