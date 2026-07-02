from __future__ import annotations

import json

from config import AppPaths
from models import PromptTemplate


DEFAULT_TEMPLATES = [
    PromptTemplate("宇宙", "宇宙", "宇宙ドキュメンタリー風。神秘的だが中学生にも分かる語り口", "冒頭に強い疑問を置き、科学的にやさしく説明する", "cinematic space documentary style, 4K look, deep space, no text"),
    PromptTemplate("株", "株", "落ち着いた経済解説。煽らず、初心者にも分かる", "なぜ注目されているか、リスク、見るべきポイントを整理する", "clean financial documentary visuals, charts without readable text, 9:16, 4K look"),
    PromptTemplate("AIニュース", "AIニュース", "最新テックニュース風。専門用語をほどいて説明する", "何が新しいのか、生活や仕事への影響を短く伝える", "futuristic AI technology documentary, no readable text, 9:16, 4K look"),
    PromptTemplate("歴史", "歴史", "歴史ドキュメンタリー風。物語として引き込む", "人物、時代背景、意外な転換点を中心に構成する", "cinematic historical documentary, realistic, no text, 9:16"),
    PromptTemplate("猫", "猫", "やさしい雑学ショート。かわいさと学びを両立する", "身近な疑問から入り、豆知識として楽しくまとめる", "cute realistic cat documentary, warm indoor light, no text, 9:16"),
    PromptTemplate("偉人", "偉人", "偉人の人生を短く熱量高く伝える", "挫折、転機、現代への学びを一本道で語る", "cinematic biographical documentary scene, no readable text, 9:16"),
]


class TemplateService:
    """templates.jsonを読み書きし、プロンプトテンプレートを管理します。"""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load(self) -> list[PromptTemplate]:
        if not self.paths.templates_path.exists():
            self.save(DEFAULT_TEMPLATES)
            return DEFAULT_TEMPLATES.copy()
        try:
            data = json.loads(self.paths.templates_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_TEMPLATES.copy()
        templates = []
        for item in data if isinstance(data, list) else []:
            if isinstance(item, dict) and item.get("name"):
                templates.append(PromptTemplate(
                    name=str(item.get("name", "")),
                    genre=str(item.get("genre", item.get("name", ""))),
                    style=str(item.get("style", "")),
                    angle=str(item.get("angle", "")),
                    image_style=str(item.get("image_style", "")),
                ))
        return templates or DEFAULT_TEMPLATES.copy()

    def save(self, templates: list[PromptTemplate]) -> None:
        data = [template.__dict__ for template in templates]
        self.paths.templates_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
