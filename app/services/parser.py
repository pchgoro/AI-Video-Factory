from __future__ import annotations

import json
import logging
import re
from json import JSONDecodeError
from typing import Any

from models import ParsedChatGptAnswer


SECTION_PATTERN = re.compile(
    r"^(タイトル|ナレーション|画像プロンプト\d+|字幕|ハッシュタグ)\s*[:：]\s*(.*)$",
    re.MULTILINE,
)


class ChatGptParseError(ValueError):
    """ChatGPT回答を解析できなかったときの日本語エラーです。"""


class ChatGptAnswerParser:
    """ChatGPTのJSON回答を標準形式へ変換します。旧テキスト形式にも対応します。"""

    def parse(self, raw_text: str) -> ParsedChatGptAnswer:
        logger = logging.getLogger("ai_video_factory")
        text = raw_text.strip()
        if not text:
            logger.warning("JSON解析: 空の入力")
            raise ChatGptParseError("ChatGPTの回答が空です。JSONを貼り付けてください。")

        if self._looks_like_json(text):
            logger.info("JSON解析: JSON形式として解析")
            return self._parse_json(text)

        logger.info("JSON解析: 旧形式として解析")
        return self._parse_legacy(text)

    def _parse_json(self, text: str) -> ParsedChatGptAnswer:
        try:
            data = json.loads(text)
        except JSONDecodeError as exc:
            logging.getLogger("ai_video_factory").warning("JSON解析エラー: %s", exc.msg)
            raise ChatGptParseError(
                f"JSONの形式が壊れています。カンマ、引用符、かっこの閉じ忘れを確認してください。\n詳細: {exc.msg}"
            ) from exc

        if not isinstance(data, dict):
            raise ChatGptParseError("JSONの一番外側は { } のオブジェクトにしてください。")

        image_prompts = self._as_string_list(data.get("image_prompts"), "image_prompts")
        hashtags = self._as_string_list(data.get("hashtags"), "hashtags")
        subtitles = self._format_subtitles(data.get("subtitles"))

        return ParsedChatGptAnswer(
            title=str(data.get("title", "")).strip(),
            script=str(data.get("script", "")).strip(),
            voice_text=str(data.get("voice_text", data.get("script", ""))).strip(),
            image_prompts=image_prompts,
            subtitles=subtitles,
            hashtags=" ".join(hashtags).strip(),
        )

    def _parse_legacy(self, text: str) -> ParsedChatGptAnswer:
        matches = list(SECTION_PATTERN.finditer(text))
        if not matches:
            raise ChatGptParseError("JSONとして解析できませんでした。旧形式の場合は「タイトル：」「ナレーション：」などの見出しが必要です。")

        sections: dict[str, str] = {}
        for index, match in enumerate(matches):
            key = match.group(1)
            first_line = match.group(2).strip()
            start = match.end()
            end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            body = text[start:end].strip()
            sections[key] = (first_line + "\n" + body).strip() if body else first_line

        image_prompts = [
            value
            for key, value in sorted(sections.items())
            if key.startswith("画像プロンプト") and value
        ]
        script = sections.get("ナレーション", "")
        return ParsedChatGptAnswer(
            title=sections.get("タイトル", ""),
            script=script,
            voice_text=script,
            image_prompts=image_prompts,
            subtitles=sections.get("字幕", ""),
            hashtags=sections.get("ハッシュタグ", ""),
        )

    def _looks_like_json(self, text: str) -> bool:
        return text.startswith("{") or text.startswith("[")

    def _as_string_list(self, value: Any, field_name: str) -> list[str]:
        if value is None:
            return []
        if not isinstance(value, list):
            raise ChatGptParseError(f"{field_name} は配列で返してください。")
        return [str(item).strip() for item in value if str(item).strip()]

    def _format_subtitles(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        if not isinstance(value, list):
            raise ChatGptParseError("subtitles は配列で返してください。")

        lines: list[str] = []
        for item in value:
            if isinstance(item, dict):
                text = str(item.get("text", "")).strip()
                start = str(item.get("start", "")).strip()
                end = str(item.get("end", "")).strip()
                if start or end:
                    lines.append(f"{start} --> {end} {text}".strip())
                elif text:
                    lines.append(text)
            elif str(item).strip():
                lines.append(str(item).strip())
        return "\n".join(lines)
