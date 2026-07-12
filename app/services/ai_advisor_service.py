from __future__ import annotations

import random
import re
from collections import Counter
from dataclasses import dataclass, field
from datetime import date, datetime

from models import ProjectInfo
from services.analytics_service import AnalyticsReport, AnalyticsRecord, GroupMetric, WordMetric


@dataclass
class TopicSuggestion:
    name: str
    stars: int
    reason: str = ""


@dataclass
class TopicInventory:
    unmade: int = 0
    in_progress: int = 0
    completed: int = 0
    posted: int = 0


@dataclass
class ProductionGoal:
    target: int = 100
    current: int = 0

    @property
    def percent(self) -> int:
        if self.target <= 0:
            return 0
        return max(0, min(100, round(self.current / self.target * 100)))

    @property
    def bar(self) -> str:
        filled = round(self.percent / 10)
        return "█" * filled + "□" * (10 - filled)


@dataclass
class Badge:
    label: str
    achieved: bool


@dataclass
class AdvisorReport:
    today_analysis: list[str] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)
    recommended_themes: list[TopicSuggestion] = field(default_factory=list)
    recommended_titles: list[str] = field(default_factory=list)
    next_plan: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)
    goal: ProductionGoal = field(default_factory=ProductionGoal)
    badges: list[Badge] = field(default_factory=list)
    inventory: TopicInventory = field(default_factory=TopicInventory)
    daily_message: str = ""


class AiAdvisorService:
    DAILY_MESSAGES = [
        "今日も1本積み上げよう。",
        "継続は最大の武器です。",
        "あと1本が未来の伸びにつながります。",
        "迷ったら、よく伸びたテーマをもう1本作りましょう。",
        "小さく作って、数字で育てましょう。",
    ]

    FALLBACK_TOPICS = ["ブラックホール", "ホワイトホール", "ダークマター", "太陽", "月"]
    SERIES_IDEAS = ["ホーキング放射", "特異点", "情報パラドックス", "重力レンズ", "イベントホライズン"]

    def build(self, analytics: AnalyticsReport, projects: list[ProjectInfo], topics: list[str], monthly_target: int = 100) -> AdvisorReport:
        inventory = self.topic_inventory(projects, topics)
        current_count = analytics.summary.total_videos or inventory.posted
        report = AdvisorReport(
            today_analysis=self.today_analysis(analytics),
            comments=self.comments(analytics, projects),
            recommended_themes=self.recommended_themes(analytics, topics),
            recommended_titles=self.recommended_titles(analytics),
            next_plan=self.next_plan(analytics, topics),
            improvements=self.improvements(analytics, projects),
            goal=ProductionGoal(monthly_target, current_count),
            badges=self.badges(analytics, projects),
            inventory=inventory,
            daily_message=self.daily_message(current_count, monthly_target),
        )
        return report

    def today_analysis(self, analytics: AnalyticsReport) -> list[str]:
        summary = analytics.summary
        return [
            f"平均再生数：{summary.average_views:,.0f}回",
            f"最高再生：{summary.max_views:,}回",
            f"平均いいね率：{summary.average_like_rate:.1f}%",
            f"投稿本数：{summary.total_videos}本",
        ]

    def comments(self, analytics: AnalyticsReport, projects: list[ProjectInfo]) -> list[str]:
        if not analytics.records:
            return ["CSVを読み込むと、成績に基づいた制作提案が表示されます。"]
        comments = list(analytics.comments)
        if analytics.category_metrics:
            top_category = analytics.category_metrics[0]
            if top_category.name != "未分類":
                comments.append(f"{top_category.name}カテゴリが好調です。次も同じカテゴリの別角度を試す価値があります。")
        recent = self._recent_records(analytics.records, 5)
        if len(recent) >= 2:
            first_half = recent[: max(1, len(recent) // 2)]
            second_half = recent[max(1, len(recent) // 2) :]
            before = self._average([record.like_rate for record in first_half])
            after = self._average([record.like_rate for record in second_half])
            if after > before:
                comments.append("最近5本はいいね率が改善しています。")
        if analytics.summary.average_comment_rate >= 1:
            comments.append("コメント率が高くなっています。視聴者が反応しやすいテーマです。")
        posted_dates = {record.posted_date[:10] for record in analytics.records if record.posted_date}
        if len(posted_dates) >= max(3, len(analytics.records) // 3):
            comments.append("投稿頻度が安定しています。")
        if projects and len(analytics.records) < len(projects):
            comments.append("完成済みプロジェクトとCSV成績を突き合わせると、さらに精度が上がります。")
        return comments

    def recommended_themes(self, analytics: AnalyticsReport, topics: list[str]) -> list[TopicSuggestion]:
        suggestions: list[TopicSuggestion] = []
        for metric in analytics.category_metrics[:2]:
            if metric.name != "未分類":
                suggestions.append(TopicSuggestion(metric.name, self._stars_from_group(metric, analytics), f"カテゴリ平均{metric.average_views:,.0f}回"))
        for metric in analytics.word_metrics[:5]:
            if metric.word not in {item.name for item in suggestions}:
                suggestions.append(TopicSuggestion(metric.word, self._stars_from_word(metric, analytics), f"{metric.count}件 / 平均{metric.average_views:,.0f}回"))
        if len(suggestions) < 5:
            existing = {item.name for item in suggestions}
            candidates = topics or self.FALLBACK_TOPICS
            for topic in candidates:
                if topic not in existing:
                    suggestions.append(TopicSuggestion(topic, max(2, 5 - len(suggestions)), "ネタ在庫から提案"))
                if len(suggestions) >= 5:
                    break
        return suggestions[:5]

    def recommended_titles(self, analytics: AnalyticsReport) -> list[str]:
        themes = [item.word for item in analytics.word_metrics[:5]] or self.FALLBACK_TOPICS
        best_patterns = [item.name for item in analytics.pattern_metrics[:3]]
        titles: list[str] = []
        for theme in themes:
            if "99" not in "".join(best_patterns):
                titles.append(f"99%が知らない{theme}の秘密")
            titles.append(f"{theme}は本当に存在する？")
            titles.append(f"{theme}とは何なのか？")
            titles.append(f"{theme}が突然消えるとどうなる？")
            titles.append(f"TOP5でわかる{theme}の謎")
            if len(titles) >= 5:
                break
        return titles[:5]

    def next_plan(self, analytics: AnalyticsReport, topics: list[str]) -> list[str]:
        base = self._best_theme(analytics, topics)
        ideas = self.SERIES_IDEAS
        return [
            f"{base}シリーズ",
            "あと15本作れます。",
            "おすすめ",
            *[f"・{idea}" for idea in ideas],
        ]

    def improvements(self, analytics: AnalyticsReport, projects: list[ProjectInfo]) -> list[str]:
        improvements: list[str] = []
        pattern_names = {metric.name for metric in analytics.pattern_metrics}
        if analytics.records and "ランキング" not in pattern_names and "TOP形式" not in pattern_names:
            improvements.append("ランキング動画が少ないです。TOP5やランキング形式を増やすことをおすすめします。")
        if analytics.summary.average_comment_rate < 0.5 and analytics.records:
            improvements.append("コメント率が低めです。問いかけで終わる構成を増やすと反応が伸びやすいです。")
        if analytics.summary.average_like_rate < 2 and analytics.records:
            improvements.append("いいね率が低めです。冒頭3秒の驚きや共感を強めましょう。")
        if projects:
            durations = [self._duration_seconds(project.duration) for project in projects if project.duration]
            if durations and self._average(durations) > 70:
                improvements.append("動画時間を少し短くすると維持率が改善する可能性があります。")
        if not improvements:
            improvements.append("伸びているテーマをシリーズ化し、同じ世界観で継続投稿しましょう。")
        return improvements

    def badges(self, analytics: AnalyticsReport, projects: list[ProjectInfo]) -> list[Badge]:
        posted_projects = sum(1 for project in projects if project.progress.get("投稿済"))
        completed_projects = sum(1 for project in projects if project.progress.get("動画"))
        max_views = analytics.summary.max_views
        total_views = analytics.summary.total_views
        total_videos = max(analytics.summary.total_videos, completed_projects)
        return [
            Badge("🎉 初投稿", posted_projects >= 1 or analytics.summary.total_videos >= 1),
            Badge("🚀 1000再生達成", max_views >= 1000),
            Badge("🔥 100本制作", total_videos >= 100),
            Badge("⭐ 登録者100人", False),
            Badge("🏆 総再生10万", total_views >= 100_000),
        ]

    def topic_inventory(self, projects: list[ProjectInfo], topics: list[str]) -> TopicInventory:
        project_topics = {value for project in projects for value in [project.topic, project.title, project.series] if value}
        unmade = sum(1 for topic in topics if topic not in project_topics)
        posted = sum(1 for project in projects if project.progress.get("投稿済"))
        completed = sum(1 for project in projects if project.progress.get("動画") and not project.progress.get("投稿済"))
        in_progress = sum(1 for project in projects if not project.progress.get("動画"))
        return TopicInventory(unmade=unmade, in_progress=in_progress, completed=completed, posted=posted)

    def daily_message(self, current_count: int, monthly_target: int) -> str:
        remaining = monthly_target - current_count
        if 0 < remaining <= 3:
            return f"あと{remaining}本で{monthly_target}本です。"
        rng = random.Random(date.today().isoformat())
        return rng.choice(self.DAILY_MESSAGES)

    def _stars_from_word(self, metric: WordMetric, analytics: AnalyticsReport) -> int:
        if analytics.summary.average_views <= 0:
            return 3
        ratio = metric.average_views / analytics.summary.average_views
        if ratio >= 1.5:
            return 5
        if ratio >= 1.1:
            return 4
        if ratio >= 0.8:
            return 3
        return 2

    def _best_theme(self, analytics: AnalyticsReport, topics: list[str]) -> str:
        if analytics.category_metrics and analytics.category_metrics[0].name != "未分類":
            return analytics.category_metrics[0].name
        if analytics.word_metrics:
            return analytics.word_metrics[0].word
        if analytics.genre_metrics:
            return analytics.genre_metrics[0].name
        if topics:
            return topics[0]
        return self.FALLBACK_TOPICS[0]

    def _stars_from_group(self, metric: GroupMetric, analytics: AnalyticsReport) -> int:
        if analytics.summary.average_views <= 0:
            return 3
        ratio = metric.average_views / analytics.summary.average_views
        if ratio >= 1.5:
            return 5
        if ratio >= 1.1:
            return 4
        if ratio >= 0.8:
            return 3
        return 2

    def _recent_records(self, records: list[AnalyticsRecord], count: int) -> list[AnalyticsRecord]:
        return sorted(records, key=lambda record: self._date_key(record.posted_date))[-count:]

    def _date_key(self, value: str) -> datetime:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(value[:19], fmt)
            except ValueError:
                continue
        return datetime.min

    def _duration_seconds(self, value: str) -> float:
        digits = [int(item) for item in re.findall(r"\d+", value or "")]
        if not digits:
            return 0
        seconds = float(digits[0])
        if "分" in value:
            seconds *= 60
        return seconds

    def _average(self, values: list[float]) -> float:
        return sum(values) / len(values) if values else 0.0
