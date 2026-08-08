from __future__ import annotations

import inspect

from models import WIZARD_STEPS
from views.main_window import MainWindow


def test_wizard_steps_do_not_include_subtitle_step() -> None:
    assert WIZARD_STEPS == ["テーマ入力", "ChatGPT", "回答解析", "画像", "音声", "動画", "投稿"]
    assert "字幕" not in WIZARD_STEPS


def test_wizard_image_step_uses_image_progress_key() -> None:
    source = inspect.getsource(MainWindow._wizard_states)
    assert 'progress.get("画像")' in source
    assert 'progress.get("??")' not in source
