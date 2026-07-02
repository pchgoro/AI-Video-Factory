from __future__ import annotations

from datetime import datetime

from models import DashboardStats, ProjectInfo


class DashboardService:
    """プロジェクト一覧からホーム画面用の集計を作ります。"""

    def build(self, projects: list[ProjectInfo]) -> DashboardStats:
        today = datetime.now().date().isoformat()
        stats = DashboardStats(total_projects=len(projects))
        for project in projects:
            if project.created_at.startswith(today):
                stats.today_count += 1
            if project.progress.get("動画"):
                stats.total_videos += 1
            if project.progress.get("投稿"):
                stats.posted_count += 1
            if all(project.progress.get(item, False) for item in ["台本", "画像", "音声", "動画"]):
                stats.completed_count += 1
            elif any(project.progress.values()):
                stats.in_progress_count += 1
            if project.genre:
                stats.genre_counts[project.genre] = stats.genre_counts.get(project.genre, 0) + 1
        stats.recent_projects = sorted(projects, key=lambda item: item.updated_at or item.created_at, reverse=True)[:8]
        return stats
