from __future__ import annotations

import json

import pytest

from services.parser import ChatGptAnswerParser, ChatGptParseError


def test_parse_valid_json() -> None:
    raw = json.dumps(
        {
            "title": "タイトル",
            "script": "台本",
            "voice_text": "音声",
            "image_prompts": ["image 1", "image 2", "image 3"],
            "subtitles": [{"text": "字幕", "start": "0:00", "end": "0:01"}],
            "hashtags": ["#AI", "#Shorts"],
        },
        ensure_ascii=False,
    )
    parsed = ChatGptAnswerParser().parse(raw)
    assert parsed.title == "タイトル"
    assert parsed.script == "台本"
    assert parsed.voice_text == "音声"
    assert len(parsed.image_prompts) == 3
    assert "#AI" in parsed.hashtags


def test_parse_broken_json() -> None:
    with pytest.raises(ChatGptParseError):
        ChatGptAnswerParser().parse('{"title": "壊れたJSON",')


def test_parse_empty_json() -> None:
    with pytest.raises(ChatGptParseError):
        ChatGptAnswerParser().parse("")


def test_parse_large_json() -> None:
    raw = json.dumps(
        {
            "title": "大きいJSON",
            "script": "長い本文" * 5000,
            "voice_text": "読み上げ" * 5000,
            "image_prompts": ["prompt"] * 8,
            "subtitles": [],
            "hashtags": ["#test"],
        },
        ensure_ascii=False,
    )
    parsed = ChatGptAnswerParser().parse(raw)
    assert parsed.title == "大きいJSON"
    assert len(parsed.image_prompts) == 8


def test_parse_legacy_format() -> None:
    raw = """タイトル：旧形式
ナレーション：これは台本です。
画像プロンプト1：space image
字幕：字幕です
ハッシュタグ：#宇宙"""
    parsed = ChatGptAnswerParser().parse(raw)
    assert parsed.title == "旧形式"
    assert parsed.script == "これは台本です。"
    assert parsed.image_prompts == ["space image"]
