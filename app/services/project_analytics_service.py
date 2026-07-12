from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from models import ProjectInfo
from services.analytics_service import AnalyticsRecord, AnalyticsReport
from services.continuation_suggestion_service import ContinuationSuggestionService
from services.performance_rule_engine import PerformanceRuleEngine, VideoPerformanceInsight


@dataclass
class ProjectAnalyticsReport:
    project: ProjectInfo
    youtube: AnalyticsRecord | None = None
    tiktok: AnalyticsRecord | None = None
    youtube_insight: VideoPerformanceInsight = field(default_factory=VideoPerformanceInsight)
    tiktok_insight: VideoPerformanceInsight = field(default_factory=VideoPerformanceInsight)
    continuation_topics: list[str] = field(default_factory=list)
    cross_platform_comments: list[str] = field(default_factory=list)


class ProjectAnalyticsService:
    """プロジェクトごとの分析データ保存と表示用レポート生成を担当します。"""

    def __init__(self) -> None:
        self.rules = PerformanceRuleEngine()
        self.continuations = ContinuationSuggestionService()

    def save_project_analytics(self, projects: list[ProjectInfo], records: list[AnalyticsRecord]) -> None:
        project_by_name = {project.name: project for project in projects}
        grouped: dict[str, list[AnalyticsRecord]] = {}
        for record in records:
            if record.project_name:
                grouped.setdefault(record.project_name, []).append(record)
        for project_name, items in grouped.items():
            project = project_by_name.get(project_name)
            if not project:
                continue
            metadata = self._read_metadata(project.path)
            analytics = metadata.setdefault("analytics", {})
            for record in items:
                platform_key = "youtube" if record.platform == "YouTube" else "tiktok" if record.platform == "TikTok" else "csv"
                analytics[platform_key] = self.record_to_project_json(record)
            metadata["analytics_rating"] = max(int(record.rating or 0) for record in items)
            metadata["posting_status"] = {
                "manual_posted": (project.path / "posted.txt").exists(),
                "csv_confirmed": True,
                "status": "CSVから投稿確認済み",
                "last_confirmed_at": datetime.now().isoformat(timespec="seconds"),
            }
            self._write_metadata(project.path, metadata)

    def build_project_report(
        self,
        project: ProjectInfo,
        analytics_report: AnalyticsReport,
        topics: list[str] | None = None,
    ) -> ProjectAnalyticsReport:
        related = [record for record in analytics_report.records if record.project_name == project.name]
        youtube = next((record for record in related if record.platform == "YouTube"), None)
        tiktok = next((record for record in related if record.platform == "TikTok"), None)
        youtube_insight = self.rules.evaluate(youtube, analytics_report)
        tiktok_insight = self.rules.evaluate(tiktok, analytics_report)
        best_rating = max(youtube_insight.rating if youtube else 0, tiktok_insight.rating if tiktok else 0)
        continuation_topics = self.continuations.suggest(project, analytics_report, topics) if best_rating >= 4 else []
        return ProjectAnalyticsReport(
            project=project,
            youtube=youtube,
            tiktok=tiktok,
            youtube_insight=youtube_insight,
            tiktok_insight=tiktok_insight,
            continuation_topics=continuation_topics,
            cross_platform_comments=self.rules.cross_platform(youtube, tiktok, analytics_report),
        )

    def record_to_project_json(self, record: AnalyticsRecord) -> dict[str, object]:
        base = {
            "video_id": record.video_id,
            "url": record.url,
            "published_at": record.posted_date,
            "title": record.title,
            "views": record.views,
            "likes": record.likes,
            "comments": record.comments,
            "average_view_duration": record.average_view_duration,
            "last_imported_at": datetime.now().isoformat(timespec="seconds"),
        }
        if record.platform == "YouTube":
            base.update(
                {
                    "watch_time_hours": record.watch_time_hours,
                    "average_percentage_viewed": record.average_percentage_viewed,
                    "impressions": record.impressions,
                    "ctr": record.ctr,
                    "subscriber_change": record.subscriber_change,
                }
            )
        elif record.platform == "TikTok":
            base.update(
                {
                    "shares": record.shares,
                    "saves": record.saves,
                    "completion_rate": record.completion_rate,
                    "follower_change": record.follower_change,
                }
            )
        return base

    def _read_metadata(self, project_dir: Path) -> dict[str, object]:
        metadata_path = project_dir / "project.json"
        if not metadata_path.exists():
            return {}
        try:
            data = json.loads(metadata_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_metadata(self, project_dir: Path, metadata: dict[str, object]) -> None:
        (project_dir / "project.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
