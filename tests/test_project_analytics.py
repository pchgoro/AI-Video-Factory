from __future__ import annotations

import csv
import json

from models import ProjectInfo
from services.analytics_import_service import AnalyticsImportService
from services.analytics_link_service import AnalyticsLinkService
from services.analytics_service import AnalyticsError, AnalyticsRecord, AnalyticsService
from services.continuation_suggestion_service import ContinuationSuggestionService
from services.performance_rule_engine import PerformanceRuleEngine
from services.project_analytics_service import ProjectAnalyticsService


def _write_csv(path, headers, rows, encoding="utf-8-sig") -> None:
    with path.open("w", encoding=encoding, newline="") as file:
        writer = csv.writer(file)
        writer.writerow(headers)
        writer.writerows(rows)


def _project(tmp_path, name="p1", title="ブラックホールとは？", topic="ブラックホール") -> ProjectInfo:
    path = tmp_path / name
    path.mkdir()
    (path / "video").mkdir()
    (path / "title.txt").write_text(title, encoding="utf-8")
    (path / "topic.txt").write_text(topic, encoding="utf-8")
    (path / "project.json").write_text(json.dumps({"title": title, "topic": topic, "genre": "宇宙"}, ensure_ascii=False), encoding="utf-8")
    return ProjectInfo(name=name, path=path, title=title, topic=topic, genre="宇宙")


def test_youtube_table_graph_and_total_csv_import(tmp_path) -> None:
    table = tmp_path / "表データ.csv"
    graph = tmp_path / "グラフデータ.csv"
    total = tmp_path / "合計.csv"
    _write_csv(table, ["動画タイトル", "再生回数", "高評価", "コメント", "インプレッション数", "CTR", "平均視聴率"], [["ブラックホールとは？", "1,200", "60", "8", "5000", "6.5%", "58%"]])
    _write_csv(graph, ["日付", "再生回数", "高評価"], [["2026-07-01", "100", "5"], ["2026-07-02", "200", "8"]])
    _write_csv(total, ["再生回数", "高評価", "コメント", "総再生時間（時間）"], [["1,200", "60", "8", "12.5"]])

    dataset = AnalyticsImportService().import_paths([table, graph, total])

    assert dataset.records[0].title == "ブラックホールとは？"
    assert dataset.records[0].ctr == 6.5
    assert dataset.records[0].average_percentage_viewed == 58
    assert len(dataset.daily_rows) == 2
    assert dataset.totals["views"] == 1200
    report = AnalyticsService().import_paths([table, graph, total], [])
    assert report.summary.total_views == 1200


def test_youtube_studio_japanese_columns_keep_title_and_id_separate(tmp_path) -> None:
    table = tmp_path / "表データ.csv"
    graph = tmp_path / "グラフデータ.csv"
    total = tmp_path / "合計.csv"
    _write_csv(
        table,
        ["コンテンツ", "動画のタイトル", "動画公開時刻", "長さ", "平均視聴率 (%)", "平均視聴時間", "高評価数", "視聴回数", "総再生時間（単位: 時間）", "チャンネル登録者", "インプレッション数", "インプレッションのクリック率 (%)"],
        [
            ["合計", "", "", "", "105.64", "0:00:56", "319", "15299", "100.9885", "27", "800", "5.13"],
            ["Tyb-hzda344", "ブラックホールは地球の近くにある？", "Jul 8, 2026", "56", "87.12", "0:00:46", "38", "1,580", "7.6646", "1", "49", "4.08"],
        ],
    )
    _write_csv(graph, ["日付", "コンテンツ", "動画のタイトル", "動画公開時刻", "長さ", "視聴回数"], [["2026-06-11", "Tyb-hzda344", "ブラックホールは地球の近くにある？", "Jul 8, 2026", "56", "0"]])
    _write_csv(total, ["日付", "視聴回数"], [["2026-06-11", "1"], ["2026-06-12", "2"]])

    dataset = AnalyticsImportService().import_paths([table, graph, total])

    assert len(dataset.records) == 1
    assert dataset.records[0].video_id == "Tyb-hzda344"
    assert dataset.records[0].title == "ブラックホールは地球の近くにある？"
    assert dataset.records[0].posted_date == "2026-07-08"
    assert dataset.records[0].likes == 38
    assert dataset.records[0].views == 1580
    assert dataset.records[0].average_percentage_viewed == 87.12
    assert dataset.records[0].average_view_duration == 46
    assert dataset.records[0].ctr == 4.08
    assert dataset.records[0].subscriber_change == 1
    assert len(dataset.daily_rows) == 1
    assert dataset.totals["views"] == 3


def test_cp932_csv_import_and_missing_columns_do_not_crash(tmp_path) -> None:
    csv_path = tmp_path / "youtube_cp932.csv"
    _write_csv(csv_path, ["動画タイトル", "再生回数"], [["宇宙の謎", "300"]], encoding="cp932")

    report = AnalyticsService().import_csv(csv_path, [])

    assert report.records[0].title == "宇宙の謎"
    assert report.records[0].likes == 0


def test_broken_csv_returns_japanese_error(tmp_path) -> None:
    csv_path = tmp_path / "broken.csv"
    _write_csv(csv_path, ["名前", "値"], [["x", "1"]])

    try:
        AnalyticsService().import_csv(csv_path, [])
    except AnalyticsError as exc:
        assert "タイトルまたは再生数" in str(exc)
    else:
        raise AssertionError("AnalyticsError was not raised")


def test_project_matching_exact_normalized_partial_and_similarity(tmp_path) -> None:
    project = _project(tmp_path)
    service = AnalyticsLinkService(tmp_path)
    index = service._project_candidates([project])

    assert service.match_project(AnalyticsRecord("ブラックホールとは？"), index)[1] == "完全一致"
    assert service.match_project(AnalyticsRecord(" ブラックホールとは？ #Shorts "), index)[1] == "正規化一致"
    assert service.match_project(AnalyticsRecord("ブラックホールとは？ 宇宙の謎"), index)[1] == "部分一致"
    assert service.match_project(AnalyticsRecord("ブラクホールとは"), index)[1] == "類似度一致"
    assert service.match_project(AnalyticsRecord("猫のごはん"), index)[0] is None


def test_unmatched_and_manual_link_persistence(tmp_path) -> None:
    project = _project(tmp_path)
    service = AnalyticsLinkService(tmp_path)
    record = AnalyticsRecord("未知の動画", platform="YouTube")

    summary = service.apply_links([record], [project])
    assert summary.unlinked_count == 1

    service.save_manual_link(record, project.name)
    record.project_name = ""
    summary = service.apply_links([record], [project])

    assert summary.linked_count == 1
    assert record.project_name == project.name


def test_project_json_analytics_save_and_rule_outputs(tmp_path) -> None:
    project = _project(tmp_path)
    records = [
        AnalyticsRecord("ブラックホールとは？", views=2000, likes=120, comments=20, platform="YouTube", project_name=project.name, ctr=7, average_percentage_viewed=60),
        AnalyticsRecord("ブラックホールとは？", views=3000, likes=180, comments=25, platform="TikTok", project_name=project.name, completion_rate=50),
    ]
    report = AnalyticsService().build_report(records)
    service = ProjectAnalyticsService()

    service.save_project_analytics([project], records)
    saved = json.loads((project.path / "project.json").read_text(encoding="utf-8"))
    project_report = service.build_project_report(project, report, ["ブラックホールの中では時間はどうなる？"])

    assert saved["analytics"]["youtube"]["views"] == 2000
    assert saved["posting_status"]["status"] == "CSVから投稿確認済み"
    assert project_report.youtube_insight.rating >= 4
    assert project_report.continuation_topics


def test_rule_engine_handles_insufficient_data_and_generates_improvements() -> None:
    report = AnalyticsService().build_report([AnalyticsRecord("99%が知らない宇宙の秘密", views=1000, likes=10, comments=1)])
    insight = PerformanceRuleEngine().evaluate(report.records[0], report)
    empty = PerformanceRuleEngine().evaluate(None, report)

    assert insight.reasons
    assert insight.improvements
    assert empty.improvements == ["分析データ不足"]


def test_continuation_suggestions_are_rule_based(tmp_path) -> None:
    project = _project(tmp_path)
    report = AnalyticsService().build_report([AnalyticsRecord("ブラックホールに落ちたら？", views=5000)])

    suggestions = ContinuationSuggestionService().suggest(project, report, [])

    assert any("事象の地平面" in item or "ホーキング放射" in item for item in suggestions)
