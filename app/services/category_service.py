from __future__ import annotations

import json
from pathlib import Path

from config import AppPaths


DEFAULT_CATEGORIES: dict[str, list[str]] = {
    "宇宙": ["ブラックホール", "恒星", "惑星", "銀河", "宇宙探査", "宇宙雑学"],
    "株": ["半導体", "AI関連", "高配当", "決算解説", "テーマ株", "投資初心者"],
    "AIニュース": ["ChatGPT", "画像生成AI", "動画生成AI", "AIエージェント", "業界ニュース"],
    "歴史": ["日本史", "世界史", "戦国", "偉人", "古代文明"],
    "猫": ["保護猫", "猫の健康", "猫雑学", "かわいい猫"],
    "偉人": ["科学者", "経営者", "歴史人物", "芸術家"],
}


class CategoryService:
    """ジャンル配下のカテゴリ定義をJSONで管理します。"""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load(self) -> dict[str, list[str]]:
        if not self.paths.categories_path.exists():
            return {genre: categories.copy() for genre, categories in DEFAULT_CATEGORIES.items()}
        try:
            data = json.loads(self.paths.categories_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {genre: categories.copy() for genre, categories in DEFAULT_CATEGORIES.items()}
        if not isinstance(data, dict):
            return {genre: categories.copy() for genre, categories in DEFAULT_CATEGORIES.items()}
        result: dict[str, list[str]] = {}
        for genre, categories in data.items():
            if isinstance(categories, list):
                result[str(genre)] = [str(category).strip() for category in categories if str(category).strip()]
        for genre, categories in DEFAULT_CATEGORIES.items():
            result.setdefault(genre, categories.copy())
        return result

    def save(self, categories_by_genre: dict[str, list[str]]) -> None:
        normalized = {
            str(genre).strip(): list(dict.fromkeys(str(category).strip() for category in categories if str(category).strip()))
            for genre, categories in categories_by_genre.items()
            if str(genre).strip()
        }
        self.paths.categories_path.write_text(json.dumps(normalized, ensure_ascii=False, indent=2), encoding="utf-8")

    def categories_for_genre(self, genre: str, categories_by_genre: dict[str, list[str]] | None = None) -> list[str]:
        data = categories_by_genre or self.load()
        return data.get(genre, [])

    def add_category(self, genre: str, category: str, categories_by_genre: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
        data = categories_by_genre or self.load()
        genre = genre.strip()
        category = category.strip()
        if not genre or not category:
            return data
        items = data.setdefault(genre, [])
        if category not in items:
            items.append(category)
        return data

    def rename_category(self, genre: str, old_category: str, new_category: str, categories_by_genre: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
        data = categories_by_genre or self.load()
        items = data.setdefault(genre, [])
        old_category = old_category.strip()
        new_category = new_category.strip()
        if old_category in items and new_category:
            items[items.index(old_category)] = new_category
            data[genre] = list(dict.fromkeys(items))
        return data

    def delete_category(self, genre: str, category: str, categories_by_genre: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
        data = categories_by_genre or self.load()
        data[genre] = [item for item in data.get(genre, []) if item != category]
        return data

    def move_category(self, genre: str, category: str, direction: int, categories_by_genre: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
        data = categories_by_genre or self.load()
        items = data.get(genre, [])
        if category not in items:
            return data
        index = items.index(category)
        new_index = max(0, min(len(items) - 1, index + direction))
        items[index], items[new_index] = items[new_index], items[index]
        return data

    def is_category_used(self, projects, genre: str, category: str) -> bool:
        return any(project.genre == genre and project.category == category for project in projects)
