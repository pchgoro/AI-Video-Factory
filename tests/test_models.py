from __future__ import annotations

from models import WIZARD_STEPS


def test_wizard_steps_do_not_include_subtitle_step() -> None:
    assert WIZARD_STEPS == ["テーマ入力", "ChatGPT", "回答解析", "画像", "音声", "動画", "投稿"]
    assert "字幕" not in WIZARD_STEPS
