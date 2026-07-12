from __future__ import annotations

from dataclasses import dataclass, field

from models import ProjectInfo


UNCATEGORIZED = "未分類"


@dataclass
class ProjectFilterCriteria:
    keyword: str = ""
    genre: str = ""
    category: str = ""
    series: str = ""
    tag: str = ""
    posted_status: str = ""
    progress_status: str = ""
    min_rating: int = 0
    min_views: int = 0


@dataclass
class ProjectBulkUpdate:
    genre: str = ""
    category: str = ""
    series: str = ""
    add_tags: list[str] = field(default_factory=list)
    remove_tags: list[str] = field(default_factory=list)


class ProjectFilterService:
    """プロジェクト一覧の複合フィルターを担当します。"""

    ALL_LABELS = {"", "すべて", "すべてのジャンル", "すべてのカテゴリ", "すべてのシリーズ", "すべての状態"}

    def filter(self, projects: list[ProjectInfo], criteria: ProjectFilterCriteria) -> list[ProjectInfo]:
        keyword = criteria.keyword.strip().lower()
        tag = criteria.tag.strip().lstrip("#").lower()
        result: list[ProjectInfo] = []
        for project in projects:
            if keyword and keyword not in self._haystack(project):
                continue
            if not self._matches_value(project.genre, criteria.genre, uncategorized=False):
                continue
            if not self._matches_value(project.category, criteria.category, uncategorized=True):
                continue
            if not self._matches_value(project.series, criteria.series, uncategorized=False):
                continue
            if tag and not any(tag in item.lower().lstrip("#") for item in project.tags + project.youtube_tags + project.tiktok_tags):
                continue
            if not self._matches_posted(project, criteria.posted_status):
                continue
            if not self._matches_progress(project, criteria.progress_status):
                continue
            if criteria.min_rating and int(getattr(project, "analytics_rating", 0) or 0) < criteria.min_rating:
                continue
            if criteria.min_views and int(getattr(project, "analytics_views", 0) or 0) < criteria.min_views:
                continue
            result.append(project)
        return result

    def reset(self) -> ProjectFilterCriteria:
        return ProjectFilterCriteria()

    def category_counts(self, projects: list[ProjectInfo], genre: str = "") -> dict[str, int]:
        counts: dict[str, int] = {}
        for project in projects:
            if genre and genre not in self.ALL_LABELS and project.genre != genre:
                continue
            category = project.category or UNCATEGORIZED
            counts[category] = counts.get(category, 0) + 1
        return counts

    def series_values(self, projects: list[ProjectInfo], genre: str = "", category: str = "") -> list[str]:
        values = {
            project.series
            for project in projects
            if project.series
            and self._matches_value(project.genre, genre, uncategorized=False)
            and self._matches_value(project.category, category, uncategorized=True)
        }
        return sorted(values)

    def _haystack(self, project: ProjectInfo) -> str:
        fields = [
            project.title,
            project.topic,
            project.genre,
            project.category,
            project.posted_date,
            project.series,
            " ".join(project.tags),
            " ".join(project.youtube_tags),
            " ".join(project.tiktok_tags),
            project.name,
        ]
        return " ".join(fields).lower()

    def _matches_value(self, value: str, expected: str, uncategorized: bool) -> bool:
        expected = expected.strip()
        if expected in self.ALL_LABELS:
            return True
        if uncategorized and expected == UNCATEGORIZED:
            return not value
        return value == expected

    def _matches_posted(self, project: ProjectInfo, expected: str) -> bool:
        expected = expected.strip()
        if expected in self.ALL_LABELS:
            return True
        manual = bool(project.progress.get("投稿"))
        csv_confirmed = bool(getattr(project, "csv_posted", False))
        if expected == "投稿済み":
            return manual or csv_confirmed
        if expected == "手動で投稿済み":
            return manual
        if expected == "CSVから投稿確認済み":
            return csv_confirmed
        if expected == "未投稿":
            return not manual and not csv_confirmed
        return True

    def _matches_progress(self, project: ProjectInfo, expected: str) -> bool:
        expected = expected.strip()
        if expected in self.ALL_LABELS:
            return True
        if expected == "制作中":
            return not project.progress.get("動画")
        if expected == "動画完成":
            return bool(project.progress.get("動画"))
        return bool(project.progress.get(expected))
