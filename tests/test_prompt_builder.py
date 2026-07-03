from __future__ import annotations

from services.prompt_builder import build_chatgpt_prompt


def test_prompt_requires_subtitles_to_match_narration() -> None:
    prompt = build_chatgpt_prompt("ブラックホール", "60秒", "宇宙", 3)

    assert "script と voice_text は同じ内容にする" in prompt
    assert "subtitles は voice_text で実際に読み上げる文章" in prompt
    assert "ナレーションに無い別文、要約、補足説明にしない" in prompt
    assert "0.0 や 2.8 のような秒数の数値" in prompt
