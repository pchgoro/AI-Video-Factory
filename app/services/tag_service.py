from __future__ import annotations

import re


class TagService:
    """Build posting tags for each platform from hashtags.txt."""

    def youtube_tags_from_hashtags(self, text: str) -> list[str]:
        return [tag.lstrip("#") for tag in self._split_tags(text) if tag.lstrip("#")]

    def tiktok_tags_from_hashtags(self, text: str) -> list[str]:
        tags = [self._with_hash(tag) for tag in self._split_tags(text)]
        if "#VOICEVOX" not in tags:
            tags.append("#VOICEVOX")
        return tags

    def youtube_text(self, tags: list[str]) -> str:
        return ", ".join(tag.lstrip("#").strip() for tag in tags if tag.strip())

    def tiktok_text(self, tags: list[str]) -> str:
        return " ".join(self._with_hash(tag) for tag in tags if tag.strip())

    def parse_youtube_text(self, text: str) -> list[str]:
        return [tag.lstrip("#").strip() for tag in re.split(r"[,、\n]+", text) if tag.strip()]

    def parse_tiktok_text(self, text: str) -> list[str]:
        return [self._with_hash(tag) for tag in self._split_tags(text)]

    def _split_tags(self, text: str) -> list[str]:
        return [part.strip() for part in re.findall(r"#?[^#,\s、，]+", text) if part.strip()]

    def _with_hash(self, tag: str) -> str:
        cleaned = tag.strip()
        if not cleaned:
            return ""
        return cleaned if cleaned.startswith("#") else f"#{cleaned}"
