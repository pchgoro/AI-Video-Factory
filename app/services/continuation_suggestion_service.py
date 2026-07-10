from __future__ import annotations

import re
from collections import Counter

from models import ProjectInfo
from services.analytics_service import AnalyticsReport


class ContinuationSuggestionService:
    TEMPLATES = [
        "{theme}の中では何が起きている？",
        "{theme}はなぜ注目されている？",
        "{theme}に隠された意外な事実",
        "{theme}を別角度から見ると？",
        "{theme}で99%が知らないこと",
    ]
    SPACE_KEYWORDS = ["事象の地平面", "ホーキング放射", "特異点", "重力レンズ", "超大質量", "ダークマター", "ホワイトホール"]

    def suggest(self, project: ProjectInfo, report: AnalyticsReport, topics: list[str] | None = None) -> list[str]:
        theme = project.topic or project.title or project.series or "同じテーマ"
        words = self._frequent_words(report)
        candidates: list[str] = []
        if "ブラックホール" in theme or "宇宙" in project.genre:
            candidates.extend([f"{word}とは何か？" for word in self.SPACE_KEYWORDS])
        candidates.extend(topic for topic in (topics or []) if theme[:4] and theme[:4] in topic and topic != project.topic)
        candidates.extend(template.format(theme=theme) for template in self.TEMPLATES)
        candidates.extend(f"{word}と{theme}の関係とは？" for word in words[:3] if word not in theme)
        return list(dict.fromkeys(candidates))[:5]

    def _frequent_words(self, report: AnalyticsReport) -> list[str]:
        counter: Counter[str] = Counter()
        for record in report.records:
            for word in re.findall(r"[A-Za-z0-9]+|[一-龥ぁ-んァ-ンー]{2,}", record.title):
                counter[word] += 1
        return [word for word, _count in counter.most_common(10)]
