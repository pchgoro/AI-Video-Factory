from __future__ import annotations

import csv

from models import ProjectInfo
from services.analytics_service import AnalyticsError, AnalyticsRecord, AnalyticsService


def _write_csv(path, headers, rows) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)


def test_import_youtube_csv_builds_summary_and_rankings(tmp_path) -> None:
    csv_path = tmp_path / "youtube.csv"
    _write_csv(
        csv_path,
        ["動画タイトル", "再生回数", "高評価", "コメント", "投稿日"],
        [
            ["ブラックホールとは？", "1,000", "50", "10", "2026-07-01"],
            ["宇宙のなぜ", "500", "10", "2", "2026-07-02"],
        ],
    )
    project = ProjectInfo(name="p1", path=tmp_path / "p1", title="ブラックホールとは？", genre="宇宙")

    report = AnalyticsService().import_csv(csv_path, [project])

    assert report.summary.total_videos == 2
    assert report.summary.total_views == 1500
    assert report.summary.average_views == 750
    assert report.records[0].genre == "宇宙"
    assert report.rankings["再生数"][0].title == "ブラックホールとは？"
    assert report.pattern_metrics[0].name == "〜とは？"
    assert report.records[0].rating >= report.records[1].rating


def test_import_tiktok_csv_supports_aliases_and_rates(tmp_path) -> None:
    csv_path = tmp_path / "tiktok_export.csv"
    _write_csv(
        csv_path,
        ["Title", "Views", "Likes", "Comments", "Date", "Genre"],
        [["猫が宇宙を見たら？", "2000", "100", "20", "2026/07/01", "猫"]],
    )

    report = AnalyticsService().import_csv(csv_path, [])

    assert report.records[0].platform == "TikTok"
    assert report.records[0].like_rate == 5
    assert report.records[0].comment_rate == 1
    assert report.genre_metrics[0].name == "猫"


def test_missing_required_columns_returns_japanese_error(tmp_path) -> None:
    csv_path = tmp_path / "broken.csv"
    _write_csv(csv_path, ["名前", "いいね"], [["sample", "1"]])

    try:
        AnalyticsService().import_csv(csv_path, [])
    except AnalyticsError as exc:
        assert "タイトルまたは再生数" in str(exc)
    else:
        raise AssertionError("AnalyticsError was not raised")


def test_filter_records_by_title_genre_views_date_and_rating() -> None:
    service = AnalyticsService()
    records = [
        AnalyticsRecord("ブラックホールとは？", views=1000, likes=50, comments=5, genre="宇宙", posted_date="2026-07-01"),
        AnalyticsRecord("猫ランキング", views=100, likes=1, comments=0, genre="猫", posted_date="2026-06-01"),
    ]
    report = service.build_report(records)

    filtered = service.filter_records(
        report.records,
        title_keyword="ブラック",
        genre_keyword="宇宙",
        min_views=500,
        posted_date="2026-07",
        min_rating=3,
    )

    assert [record.title for record in filtered] == ["ブラックホールとは？"]


def test_export_report_csv(tmp_path) -> None:
    service = AnalyticsService()
    report = service.build_report([AnalyticsRecord("AIニュース", views=300, likes=9, comments=3, genre="AI")])
    output = tmp_path / "exports" / "analytics.csv"

    service.export_report_csv(report, output)

    text = output.read_text(encoding="utf-8-sig")
    assert "AIニュース" in text
    assert "like_rate" in text


def test_render_dashboard_graphs(tmp_path) -> None:
    service = AnalyticsService()
    report = service.build_report(
        [
            AnalyticsRecord("ブラックホールとは？", views=1000, likes=50, comments=5, genre="宇宙", posted_date="2026-07-01"),
            AnalyticsRecord("猫ランキング", views=700, likes=30, comments=2, genre="猫", posted_date="2026-07-02"),
        ]
    )
    output = tmp_path / "analytics.png"

    service.render_dashboard_graphs(report, output)

    assert output.exists()
    assert output.stat().st_size > 0
