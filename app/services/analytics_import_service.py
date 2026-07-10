from __future__ import annotations

import csv
import re
from dataclasses import dataclass, field
from pathlib import Path

from services.analytics_service import AnalyticsError, AnalyticsRecord


@dataclass
class ImportedAnalyticsDataset:
    records: list[AnalyticsRecord] = field(default_factory=list)
    daily_rows: list[dict[str, object]] = field(default_factory=list)
    totals: dict[str, object] = field(default_factory=dict)
    sources: list[str] = field(default_factory=list)


class AnalyticsImportService:
    """YouTube / TikTok Studio CSVを列名から判定して読み込みます。"""

    HEADER_ALIASES = {
        "title": {"title", "video title", "content", "post", "動画", "タイトル", "動画タイトル", "投稿タイトル", "コンテンツ"},
        "video_id": {"video id", "動画 id", "動画id", "コンテンツ id", "コンテンツid", "id"},
        "url": {"url", "video url", "動画 url", "動画リンク", "リンク"},
        "views": {"views", "video views", "view count", "plays", "再生回数", "視聴回数"},
        "likes": {"likes", "like count", "高評価", "いいね", "いいね数"},
        "comments": {"comments", "comment count", "コメント", "コメント数"},
        "shares": {"shares", "share count", "シェア", "シェア数"},
        "saves": {"saves", "saved", "保存", "保存数"},
        "published_at": {"date", "publish date", "published", "posted date", "投稿日", "公開日", "投稿日時", "日付"},
        "genre": {"genre", "category", "ジャンル", "カテゴリ"},
        "watch_time_hours": {"watch time (hours)", "watch time hours", "総再生時間", "総再生時間（時間）", "再生時間（時間）"},
        "average_view_duration": {"average view duration", "平均視聴時間", "平均再生時間"},
        "average_percentage_viewed": {"average percentage viewed", "平均再生率", "平均視聴率"},
        "impressions": {"impressions", "表示回数", "インプレッション", "インプレッション数"},
        "ctr": {"impressions click-through rate (%)", "ctr", "クリック率", "インプレッションのクリック率"},
        "subscriber_change": {"subscribers", "subscriber change", "登録者", "登録者増減"},
        "completion_rate": {"completion rate", "完視聴率", "フル視聴率"},
        "follower_change": {"followers", "follower change", "フォロワー", "フォロワー増減"},
    }

    def import_paths(self, paths: list[Path]) -> ImportedAnalyticsDataset:
        csv_paths: list[Path] = []
        for path in paths:
            if path.is_dir():
                csv_paths.extend(sorted(path.glob("*.csv")))
            elif path.suffix.lower() == ".csv":
                csv_paths.append(path)
        if not csv_paths:
            raise AnalyticsError("読み込めるCSVファイルが見つかりません。")

        dataset = ImportedAnalyticsDataset()
        for csv_path in csv_paths:
            rows = self.read_csv(csv_path)
            dataset.sources.append(str(csv_path))
            if not rows:
                continue
            field_map = self.field_map(rows[0].keys())
            csv_type = self.detect_csv_type(csv_path, rows[0].keys(), field_map)
            if csv_type == "graph":
                dataset.daily_rows.extend(self._graph_rows(rows, field_map))
            elif csv_type == "total":
                dataset.totals.update(self._total_values(rows, field_map))
            else:
                dataset.records.extend(self._records(csv_path, rows, field_map))
        return dataset

    def read_csv(self, path: Path) -> list[dict[str, str]]:
        if not path.exists():
            raise AnalyticsError("CSVファイルが見つかりません。")
        last_error: Exception | None = None
        for encoding in ("utf-8-sig", "utf-8", "cp932", "shift_jis"):
            try:
                with path.open("r", encoding=encoding, newline="") as file:
                    sample = file.read(4096)
                    file.seek(0)
                    dialect = csv.Sniffer().sniff(sample) if sample.strip() else csv.excel
                    return list(csv.DictReader(file, dialect=dialect))
            except UnicodeDecodeError as exc:
                last_error = exc
            except csv.Error:
                with path.open("r", encoding=encoding, newline="") as file:
                    return list(csv.DictReader(file))
            except OSError as exc:
                raise AnalyticsError(f"CSVの読み込みに失敗しました: {exc}") from exc
        raise AnalyticsError(f"CSVの文字コードを判定できませんでした: {last_error}")

    def detect_csv_type(self, path: Path, headers, field_map: dict[str, str]) -> str:
        normalized_headers = {self._normalize_header(header) for header in headers}
        name = path.name.lower()
        if "title" in field_map and "views" in field_map:
            return "table"
        if "published_at" in field_map and "views" in field_map and "title" not in field_map:
            return "graph"
        if "合計" in name or "total" in name or ("views" in field_map and len(normalized_headers) <= 6):
            return "total"
        return "table"

    def field_map(self, headers) -> dict[str, str]:
        result: dict[str, str] = {}
        normalized_aliases = {
            key: {self._normalize_header(alias) for alias in aliases}
            for key, aliases in self.HEADER_ALIASES.items()
        }
        for header in headers:
            normalized = self._normalize_header(header)
            for key, aliases in normalized_aliases.items():
                if normalized in aliases:
                    result[key] = header
        return result

    def _records(self, path: Path, rows: list[dict[str, str]], field_map: dict[str, str]) -> list[AnalyticsRecord]:
        if "title" not in field_map or "views" not in field_map:
            raise AnalyticsError("CSVにタイトルまたは再生数の列がありません。")
        platform = self._detect_platform(path, rows[0].keys(), field_map)
        records: list[AnalyticsRecord] = []
        for row in rows:
            title = self._clean(row.get(field_map["title"], ""))
            if not title:
                continue
            record = AnalyticsRecord(
                title=title,
                views=self.parse_int(row.get(field_map["views"], "")),
                likes=self.parse_int(row.get(field_map.get("likes", ""), "")),
                comments=self.parse_int(row.get(field_map.get("comments", ""), "")),
                posted_date=self._clean(row.get(field_map.get("published_at", ""), "")),
                genre=self._clean(row.get(field_map.get("genre", ""), "")) or "未分類",
                platform=platform,
                video_id=self._clean(row.get(field_map.get("video_id", ""), "")),
                url=self._clean(row.get(field_map.get("url", ""), "")),
                watch_time_hours=self.parse_float(row.get(field_map.get("watch_time_hours", ""), "")),
                average_view_duration=self.parse_duration(row.get(field_map.get("average_view_duration", ""), "")),
                average_percentage_viewed=self.parse_percent(row.get(field_map.get("average_percentage_viewed", ""), "")),
                impressions=self.parse_int(row.get(field_map.get("impressions", ""), "")),
                ctr=self.parse_percent(row.get(field_map.get("ctr", ""), "")),
                subscriber_change=self.parse_int(row.get(field_map.get("subscriber_change", ""), "")),
                shares=self.parse_int(row.get(field_map.get("shares", ""), "")),
                saves=self.parse_int(row.get(field_map.get("saves", ""), "")),
                completion_rate=self.parse_percent(row.get(field_map.get("completion_rate", ""), "")),
                follower_change=self.parse_int(row.get(field_map.get("follower_change", ""), "")),
                source_file=str(path),
            )
            records.append(record)
        return records

    def _graph_rows(self, rows: list[dict[str, str]], field_map: dict[str, str]) -> list[dict[str, object]]:
        result: list[dict[str, object]] = []
        for row in rows:
            result.append(
                {
                    "date": self._clean(row.get(field_map.get("published_at", ""), "")),
                    "views": self.parse_int(row.get(field_map.get("views", ""), "")),
                    "likes": self.parse_int(row.get(field_map.get("likes", ""), "")),
                    "comments": self.parse_int(row.get(field_map.get("comments", ""), "")),
                }
            )
        return result

    def _total_values(self, rows: list[dict[str, str]], field_map: dict[str, str]) -> dict[str, object]:
        if not rows:
            return {}
        row = rows[-1]
        return {
            "views": self.parse_int(row.get(field_map.get("views", ""), "")),
            "likes": self.parse_int(row.get(field_map.get("likes", ""), "")),
            "comments": self.parse_int(row.get(field_map.get("comments", ""), "")),
            "watch_time_hours": self.parse_float(row.get(field_map.get("watch_time_hours", ""), "")),
        }

    def _detect_platform(self, path: Path, headers, field_map: dict[str, str]) -> str:
        haystack = f"{path.name} {' '.join(headers)}".lower()
        if "tiktok" in haystack or "shares" in field_map or "follower_change" in field_map:
            return "TikTok"
        if "youtube" in haystack or "高評価" in haystack or "impressions" in field_map:
            return "YouTube"
        return "CSV"

    def parse_int(self, value: object) -> int:
        text = self._clean(value).replace(",", "")
        match = re.search(r"-?\d+", text)
        return int(match.group(0)) if match else 0

    def parse_float(self, value: object) -> float:
        text = self._clean(value).replace(",", "").replace("%", "")
        match = re.search(r"-?\d+(?:\.\d+)?", text)
        return float(match.group(0)) if match else 0.0

    def parse_percent(self, value: object) -> float:
        return self.parse_float(value)

    def parse_duration(self, value: object) -> float:
        text = self._clean(value)
        if not text:
            return 0.0
        parts = [part for part in text.split(":") if part != ""]
        if len(parts) == 3:
            return self.parse_int(parts[0]) * 3600 + self.parse_int(parts[1]) * 60 + self.parse_float(parts[2])
        if len(parts) == 2:
            return self.parse_int(parts[0]) * 60 + self.parse_float(parts[1])
        return self.parse_float(text)

    def _clean(self, value: object) -> str:
        return str(value or "").strip()

    def _normalize_header(self, value: object) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())
