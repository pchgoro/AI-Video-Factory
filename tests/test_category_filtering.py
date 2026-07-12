from __future__ import annotations

import json

from config import AppPaths
from models import ProjectInfo
from services.analytics_service import AnalyticsRecord, AnalyticsService
from services.ai_advisor_service import AiAdvisorService
from services.category_service import CategoryService
from services.project_filter_service import ProjectFilterCriteria, ProjectFilterService, UNCATEGORIZED
from services.project_service import ProjectService


def test_category_add_edit_delete_move_and_persistence(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    service = CategoryService(paths)
    categories = service.load()

    categories = service.add_category("宇宙", "ブラックホール深掘り", categories)
    categories = service.rename_category("宇宙", "ブラックホール深掘り", "ブラックホール基礎", categories)
    categories = service.move_category("宇宙", "ブラックホール基礎", -1, categories)
    service.save(categories)

    reloaded = service.load()
    assert "ブラックホール基礎" in reloaded["宇宙"]

    reloaded = service.delete_category("宇宙", "ブラックホール基礎", reloaded)
    service.save(reloaded)
    assert "ブラックホール基礎" not in CategoryService(paths).load()["宇宙"]


def test_project_service_reads_old_project_without_category_and_bulk_updates(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_dir = paths.projects_dir / "old"
    project_dir.mkdir()
    (project_dir / "project.json").write_text(json.dumps({"topic": "古い動画", "genre": "宇宙"}, ensure_ascii=False), encoding="utf-8")
    project = ProjectService(paths).load_project(project_dir)

    assert project.category == ""

    updated = ProjectService(paths).bulk_update_classification(
        [project],
        genre="宇宙",
        category="ブラックホール",
        series="ブラックホール基礎",
        add_tags=["初心者向け", "宇宙"],
        remove_tags=["宇宙"],
    )[0]

    assert updated.category == "ブラックホール"
    assert updated.series == "ブラックホール基礎"
    assert updated.tags == ["初心者向け"]


def test_project_filter_genre_category_series_compound_uncategorized_and_reset(tmp_path) -> None:
    projects = [
        ProjectInfo(name="p1", path=tmp_path / "p1", title="ブラックホールとは？", genre="宇宙", category="ブラックホール", series="基礎", tags=["初心者向け"], progress={"動画": True, "投稿": True}, analytics_rating=4, analytics_views=1200),
        ProjectInfo(name="p2", path=tmp_path / "p2", title="太陽とは？", genre="宇宙", category="恒星", series="恒星", tags=["中級"], progress={"動画": False, "投稿": False}, analytics_rating=2, analytics_views=300),
        ProjectInfo(name="p3", path=tmp_path / "p3", title="未分類", genre="株", category="", series="", tags=[], progress={"動画": False, "投稿": False}),
    ]
    service = ProjectFilterService()

    assert service.filter(projects, ProjectFilterCriteria(genre="宇宙")) == projects[:2]
    assert service.filter(projects, ProjectFilterCriteria(category="ブラックホール")) == [projects[0]]
    assert service.filter(projects, ProjectFilterCriteria(series="基礎")) == [projects[0]]
    assert service.filter(projects, ProjectFilterCriteria(genre="宇宙", category="ブラックホール", tag="初心者", posted_status="投稿済み", min_rating=4, min_views=1000)) == [projects[0]]
    assert service.filter(projects, ProjectFilterCriteria(category=UNCATEGORIZED)) == [projects[2]]
    assert service.reset() == ProjectFilterCriteria()


def test_category_counts_and_series_values_handle_empty_and_missing_categories(tmp_path) -> None:
    projects = [
        ProjectInfo(name="p1", path=tmp_path / "p1", genre="宇宙", category="ブラックホール", series="基礎"),
        ProjectInfo(name="p2", path=tmp_path / "p2", genre="宇宙", category="", series=""),
    ]
    service = ProjectFilterService()

    assert service.category_counts(projects, "宇宙") == {"ブラックホール": 1, UNCATEGORIZED: 1}
    assert service.series_values(projects, "宇宙", "ブラックホール") == ["基礎"]
    assert service.filter(projects, ProjectFilterCriteria(category="存在しないカテゴリ")) == []


def test_analytics_category_metrics_and_advisor_source(tmp_path) -> None:
    records = [
        AnalyticsRecord("ブラックホールとは？", views=1200, likes=120, genre="宇宙", category="ブラックホール", average_percentage_viewed=74),
        AnalyticsRecord("恒星とは？", views=300, likes=6, genre="宇宙", category="恒星", average_percentage_viewed=30),
    ]
    report = AnalyticsService().build_report(records)

    assert report.category_metrics[0].name == "宇宙 > ブラックホール"
    assert report.category_metrics[0].total_views == 1200
    assert report.category_metrics[0].average_like_rate == 10
    assert report.category_metrics[0].average_view_percentage == 74
    advisor = AiAdvisorService().build(report, [], [])
    assert "宇宙 > ブラックホール" in advisor.recommended_themes[0].name
