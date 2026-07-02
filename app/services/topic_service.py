from __future__ import annotations

import json

from config import AppPaths
from models import DEFAULT_TOPICS


class TopicService:
    """topics.jsonを通じてネタ帳を管理します。"""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load(self) -> list[str]:
        if not self.paths.topics_path.exists():
            self.save(DEFAULT_TOPICS.copy())
            return DEFAULT_TOPICS.copy()
        try:
            data = json.loads(self.paths.topics_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_TOPICS.copy()
        if isinstance(data, list):
            return [str(item) for item in data if str(item).strip()]
        return DEFAULT_TOPICS.copy()

    def save(self, topics: list[str]) -> None:
        cleaned = []
        for topic in topics:
            value = topic.strip()
            if value and value not in cleaned:
                cleaned.append(value)
        self.paths.topics_path.write_text(
            json.dumps(cleaned, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
