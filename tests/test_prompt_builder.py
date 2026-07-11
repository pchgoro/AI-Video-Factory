from __future__ import annotations

from models import PromptTemplate
from services.prompt_builder import build_bulk_image_prompt, build_chatgpt_prompt


def test_bulk_image_prompt_uses_requested_image_count() -> None:
    prompt = build_bulk_image_prompt(["p1", "p2", "p3"], 3, "・9:16\n・4K")

    assert "画像を3枚、１枚ずつ生成してください。" in prompt
    assert "画像1" in prompt
    assert "画像3" in prompt
    assert "画像4" not in prompt
    assert "1枚ずつ出力してください" in prompt


def test_bulk_image_prompt_adds_template_condition() -> None:
    template = PromptTemplate("猫", "猫", "style", "angle", "warm cute cat visuals, no text")

    prompt = build_bulk_image_prompt(["cat 1"], 2, "9:16\n4K", template)

    assert "・9:16" in prompt
    assert "・4K" in prompt
    assert "・warm cute cat visuals, no text" in prompt
    assert "画像2" in prompt


def test_prompt_requires_subtitles_to_match_narration() -> None:
    prompt = build_chatgpt_prompt("ブラックホール", "60秒", "宇宙", 3)

    assert "script と voice_text は同じ内容にする" in prompt
    assert "subtitles は voice_text で実際に読み上げる文章" in prompt
    assert "ナレーションに無い別文、要約、補足説明にしない" in prompt
    assert "0.0 や 2.8 のような秒数の数値" in prompt
