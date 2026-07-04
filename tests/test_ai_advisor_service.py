from __future__ import annotations

from models import ProjectInfo
from services.ai_advisor_service import AiAdvisorService
from services.analytics_service import AnalyticsRecord, AnalyticsService


def _analytics_report():
    return AnalyticsService().build_report(
        [
            AnalyticsRecord("ブラックホールとは何なのか？", views=12000, likes=600, comments=90, genre="宇宙", posted_date="2026-07-01"),
            AnalyticsRecord("99%が知らないブラックホールの秘密", views=9000, likes=360, comments=70, genre="宇宙", posted_date="2026-07-02"),
            AnalyticsRecord("猫ランキングTOP5", views=1000, likes=20, comments=3, genre="猫", posted_date="2026-07-03"),
        ]
    )


def test_ai_advisor_builds_recommendations_and_goal() -> None:
    service = AiAdvisorService()
    report = service.build(_analytics_report(), [], ["ブラックホール", "太陽"], monthly_target=100)

    assert report.today_analysis[0].startswith("平均再生数")
    assert report.goal.current == 3
    assert report.goal.percent == 3
    assert report.recommended_themes
    assert report.recommended_titles
    assert any("ブラックホール" in title for title in report.recommended_titles)
    assert report.next_plan[0].endswith("シリーズ")
    assert report.daily_message


def test_ai_advisor_inventory_counts_project_states(tmp_path) -> None:
    posted = ProjectInfo(name="posted", path=tmp_path / "posted", topic="投稿済テーマ", progress={"動画": True, "投稿済": True})
    completed = ProjectInfo(name="completed", path=tmp_path / "completed", topic="完成テーマ", progress={"動画": True, "投稿済": False})
    progress = ProjectInfo(name="progress", path=tmp_path / "progress", topic="制作中テーマ", progress={"動画": False, "投稿済": False})

    inventory = AiAdvisorService().topic_inventory(
        [posted, completed, progress],
        ["投稿済テーマ", "完成テーマ", "制作中テーマ", "未制作テーマ"],
    )

    assert inventory.unmade == 1
    assert inventory.in_progress == 1
    assert inventory.completed == 1
    assert inventory.posted == 1


def test_ai_advisor_badges_are_rule_based(tmp_path) -> None:
    projects = [ProjectInfo(name=f"p{i}", path=tmp_path / f"p{i}", progress={"動画": True, "投稿済": i == 0}) for i in range(100)]

    report = AiAdvisorService().build(_analytics_report(), projects, [])
    achieved = {badge.label: badge.achieved for badge in report.badges}

    assert achieved["🎉 初投稿"]
    assert achieved["🚀 1000再生達成"]
    assert achieved["🔥 100本制作"]
    assert not achieved["⭐ 登録者100人"]


def test_ai_advisor_empty_analytics_still_shows_topics_and_inventory(tmp_path) -> None:
    service = AiAdvisorService()
    empty_report = AnalyticsService().build_report([])
    project = ProjectInfo(name="p1", path=tmp_path / "p1", topic="既存テーマ", progress={"動画": False})

    report = service.build(empty_report, [project], ["既存テーマ", "未制作テーマ"])

    assert report.recommended_themes
    assert report.inventory.unmade == 1
    assert "CSVを読み込む" in report.comments[0]
