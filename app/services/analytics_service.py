from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

from models import ProjectInfo


class AnalyticsError(ValueError):
    """Analytics import/export error shown to users."""


@dataclass
class AnalyticsRecord:
    title: str
    views: int = 0
    likes: int = 0
    comments: int = 0
    posted_date: str = ""
    genre: str = "未分類"
    platform: str = "CSV"
    project_name: str = ""
    rating: int = 1

    @property
    def like_rate(self) -> float:
        return self.likes / self.views * 100 if self.views else 0.0

    @property
    def comment_rate(self) -> float:
        return self.comments / self.views * 100 if self.views else 0.0


@dataclass
class AnalyticsSummary:
    total_videos: int = 0
    total_views: int = 0
    average_views: float = 0.0
    max_views: int = 0
    min_views: int = 0
    total_likes: int = 0
    total_comments: int = 0
    average_like_rate: float = 0.0
    average_comment_rate: float = 0.0


@dataclass
class GroupMetric:
    name: str
    count: int
    average_views: float
    average_likes: float


@dataclass
class WordMetric:
    word: str
    count: int
    average_views: float


@dataclass
class AnalyticsReport:
    records: list[AnalyticsRecord] = field(default_factory=list)
    summary: AnalyticsSummary = field(default_factory=AnalyticsSummary)
    rankings: dict[str, list[AnalyticsRecord]] = field(default_factory=dict)
    genre_metrics: list[GroupMetric] = field(default_factory=list)
    word_metrics: list[WordMetric] = field(default_factory=list)
    pattern_metrics: list[GroupMetric] = field(default_factory=list)
    comments: list[str] = field(default_factory=list)


class AnalyticsService:
    HEADER_ALIASES = {
        "title": {"title", "video title", "content", "post", "タイトル", "動画タイトル", "投稿タイトル"},
        "views": {"views", "video views", "view count", "plays", "再生回数", "視聴回数", "表示回数"},
        "likes": {"likes", "like count", "高評価", "いいね", "いいね数"},
        "comments": {"comments", "comment count", "コメント", "コメント数"},
        "posted_date": {"date", "publish date", "published", "posted date", "投稿日", "公開日", "投稿日時"},
        "genre": {"genre", "category", "ジャンル", "カテゴリ"},
    }

    STOP_WORDS = {
        "です",
        "ます",
        "する",
        "できる",
        "なぜ",
        "とは",
        "これ",
        "その",
        "動画",
        "shorts",
        "youtube",
        "tiktok",
    }

    def import_csv(self, csv_path: Path, projects: list[ProjectInfo] | None = None) -> AnalyticsReport:
        if not csv_path.exists():
            raise AnalyticsError("CSVファイルが見つかりません。")
        try:
            with csv_path.open("r", encoding="utf-8-sig", newline="") as file:
                rows = list(csv.DictReader(file))
        except UnicodeDecodeError:
            with csv_path.open("r", encoding="cp932", newline="") as file:
                rows = list(csv.DictReader(file))
        except OSError as exc:
            raise AnalyticsError(f"CSVの読み込みに失敗しました: {exc}") from exc

        if not rows:
            return self.build_report([])

        field_map = self._field_map(rows[0].keys())
        if "title" not in field_map or "views" not in field_map:
            raise AnalyticsError("CSVにタイトルまたは再生数の列がありません。")

        project_index = self._project_index(projects or [])
        records: list[AnalyticsRecord] = []
        platform = self._detect_platform(csv_path, rows[0].keys())
        for row in rows:
            title = self._clean_text(row.get(field_map["title"], ""))
            if not title:
                continue
            project = self._match_project(title, project_index)
            genre = self._clean_text(row.get(field_map.get("genre", ""), "")) if "genre" in field_map else ""
            record = AnalyticsRecord(
                title=title,
                views=self._parse_int(row.get(field_map["views"], "")),
                likes=self._parse_int(row.get(field_map.get("likes", ""), "")) if "likes" in field_map else 0,
                comments=self._parse_int(row.get(field_map.get("comments", ""), "")) if "comments" in field_map else 0,
                posted_date=self._clean_text(row.get(field_map.get("posted_date", ""), "")) if "posted_date" in field_map else "",
                genre=genre or (project.genre if project else "未分類"),
                platform=platform,
                project_name=project.name if project else "",
            )
            records.append(record)

        return self.build_report(records)

    def build_report(self, records: list[AnalyticsRecord]) -> AnalyticsReport:
        summary = self._summary(records)
        for record in records:
            record.rating = self._rating(record, summary)
        rankings = {
            "再生数": self._top(records, lambda item: item.views),
            "いいね": self._top(records, lambda item: item.likes),
            "コメント": self._top(records, lambda item: item.comments),
            "いいね率": self._top(records, lambda item: item.like_rate),
            "コメント率": self._top(records, lambda item: item.comment_rate),
        }
        report = AnalyticsReport(
            records=records,
            summary=summary,
            rankings=rankings,
            genre_metrics=self._group_metrics(records, lambda item: item.genre or "未分類"),
            word_metrics=self._word_metrics(records),
            pattern_metrics=self._group_metrics(records, self.title_pattern),
        )
        report.comments = self._comments(report)
        return report

    def filter_records(
        self,
        records: list[AnalyticsRecord],
        title_keyword: str = "",
        genre_keyword: str = "",
        min_views: int = 0,
        posted_date: str = "",
        min_rating: int = 0,
    ) -> list[AnalyticsRecord]:
        title_keyword = title_keyword.strip().lower()
        genre_keyword = genre_keyword.strip().lower()
        posted_date = posted_date.strip()
        result = []
        for record in records:
            if title_keyword and title_keyword not in record.title.lower():
                continue
            if genre_keyword and genre_keyword not in record.genre.lower():
                continue
            if min_views and record.views < min_views:
                continue
            if posted_date and posted_date not in record.posted_date:
                continue
            if min_rating and record.rating < min_rating:
                continue
            result.append(record)
        return result

    def export_report_csv(self, report: AnalyticsReport, output_path: Path) -> Path:
        try:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            with output_path.open("w", encoding="utf-8-sig", newline="") as file:
                writer = csv.writer(file)
                writer.writerow(["title", "genre", "views", "likes", "comments", "like_rate", "comment_rate", "rating", "posted_date", "platform"])
                for record in report.records:
                    writer.writerow(
                        [
                            record.title,
                            record.genre,
                            record.views,
                            record.likes,
                            record.comments,
                            f"{record.like_rate:.2f}",
                            f"{record.comment_rate:.2f}",
                            record.rating,
                            record.posted_date,
                            record.platform,
                        ]
                    )
        except OSError as exc:
            raise AnalyticsError(f"分析結果CSVの保存に失敗しました: {exc}") from exc
        return output_path

    def render_dashboard_graphs(self, report: AnalyticsReport, output_path: Path) -> Path:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
            from matplotlib import font_manager
        except Exception as exc:  # pragma: no cover - depends on runtime package state
            raise AnalyticsError("matplotlibの読み込みに失敗しました。requirements.txtを確認してください。") from exc

        for font_path in [Path("C:/Windows/Fonts/YuGothM.ttc"), Path("C:/Windows/Fonts/meiryo.ttc"), Path("C:/Windows/Fonts/msgothic.ttc")]:
            if font_path.exists():
                font_manager.fontManager.addfont(str(font_path))
                plt.rcParams["font.family"] = font_manager.FontProperties(fname=str(font_path)).get_name()
                break
        plt.rcParams["axes.unicode_minus"] = False

        output_path.parent.mkdir(parents=True, exist_ok=True)
        records = report.records
        fig, axes = plt.subplots(2, 2, figsize=(12, 9))
        fig.patch.set_facecolor("#1e1e1e")
        for axis in axes.flat:
            axis.set_facecolor("#252526")
            axis.tick_params(colors="#d4d4d4")
            axis.title.set_color("#ffffff")
            axis.xaxis.label.set_color("#d4d4d4")
            axis.yaxis.label.set_color("#d4d4d4")
            for spine in axis.spines.values():
                spine.set_color("#555555")

        dated = sorted(records, key=lambda item: self._date_key(item.posted_date))
        axes[0][0].plot([item.posted_date or str(index + 1) for index, item in enumerate(dated)], [item.views for item in dated], marker="o")
        axes[0][0].set_title("再生数推移")
        axes[0][0].tick_params(axis="x", rotation=35)

        counts = Counter(item.posted_date[:10] if item.posted_date else "未設定" for item in records)
        axes[0][1].bar(list(counts.keys()), list(counts.values()))
        axes[0][1].set_title("投稿本数推移")
        axes[0][1].tick_params(axis="x", rotation=35)

        genres = Counter(item.genre or "未分類" for item in records)
        if genres:
            axes[1][0].pie(list(genres.values()), labels=list(genres.keys()), autopct="%1.0f%%", textprops={"color": "#d4d4d4"})
        axes[1][0].set_title("ジャンル割合")

        top_views = self._top(records, lambda item: item.views)
        axes[1][1].barh([item.title[:18] for item in reversed(top_views)], [item.views for item in reversed(top_views)])
        axes[1][1].set_title("再生数TOP10")

        fig.tight_layout()
        fig.savefig(output_path, dpi=140, facecolor=fig.get_facecolor())
        plt.close(fig)
        return output_path

    def title_pattern(self, record: AnalyticsRecord) -> str:
        title = record.title
        if re.search(r"(TOP|トップ)\s*\d+", title, re.IGNORECASE):
            return "TOP形式"
        if "ランキング" in title:
            return "ランキング"
        if "とは" in title:
            return "〜とは？"
        if "できる" in title:
            return "〜できる？"
        if "なぜ" in title or "何故" in title:
            return "〜なぜ？"
        if "すると" in title or "したら" in title:
            return "○○すると？"
        if "?" in title or "？" in title:
            return "疑問形"
        return "その他"

    def _summary(self, records: list[AnalyticsRecord]) -> AnalyticsSummary:
        if not records:
            return AnalyticsSummary()
        total_views = sum(item.views for item in records)
        return AnalyticsSummary(
            total_videos=len(records),
            total_views=total_views,
            average_views=total_views / len(records),
            max_views=max(item.views for item in records),
            min_views=min(item.views for item in records),
            total_likes=sum(item.likes for item in records),
            total_comments=sum(item.comments for item in records),
            average_like_rate=sum(item.like_rate for item in records) / len(records),
            average_comment_rate=sum(item.comment_rate for item in records) / len(records),
        )

    def _rating(self, record: AnalyticsRecord, summary: AnalyticsSummary) -> int:
        if summary.total_videos == 0:
            return 1
        score = 1
        if record.views >= summary.average_views * 0.5:
            score += 1
        if record.views >= summary.average_views:
            score += 1
        if record.views >= summary.average_views * 1.5:
            score += 1
        if record.like_rate >= summary.average_like_rate and record.likes > 0:
            score += 1
        return max(1, min(5, score))

    def _top(self, records: list[AnalyticsRecord], key_func) -> list[AnalyticsRecord]:
        return sorted(records, key=key_func, reverse=True)[:10]

    def _group_metrics(self, records: list[AnalyticsRecord], name_func) -> list[GroupMetric]:
        groups: dict[str, list[AnalyticsRecord]] = defaultdict(list)
        for record in records:
            groups[name_func(record)].append(record)
        metrics = [
            GroupMetric(
                name=name,
                count=len(items),
                average_views=sum(item.views for item in items) / len(items),
                average_likes=sum(item.likes for item in items) / len(items),
            )
            for name, items in groups.items()
            if items
        ]
        return sorted(metrics, key=lambda item: item.average_views, reverse=True)

    def _word_metrics(self, records: list[AnalyticsRecord]) -> list[WordMetric]:
        word_records: dict[str, list[AnalyticsRecord]] = defaultdict(list)
        for record in records:
            for word in set(self._title_words(record.title)):
                word_records[word].append(record)
        metrics = [
            WordMetric(word=word, count=len(items), average_views=sum(item.views for item in items) / len(items))
            for word, items in word_records.items()
            if len(items) >= 1
        ]
        return sorted(metrics, key=lambda item: (item.count, item.average_views), reverse=True)[:20]

    def _title_words(self, title: str) -> list[str]:
        words = re.findall(r"[A-Za-z0-9]+|[一-龥ぁ-んァ-ンー]{2,}", title)
        return [word for word in words if word.lower() not in self.STOP_WORDS and word not in self.STOP_WORDS]

    def _comments(self, report: AnalyticsReport) -> list[str]:
        if not report.records:
            return ["CSVを読み込むと、ここに分析コメントが表示されます。"]
        comments: list[str] = []
        average_views = report.summary.average_views or 1
        if report.genre_metrics:
            top_genre = report.genre_metrics[0]
            diff = (top_genre.average_views - average_views) / average_views * 100
            comments.append(f"{top_genre.name}系は平均より{diff:.0f}%再生されています。")
        if report.pattern_metrics:
            top_pattern = report.pattern_metrics[0]
            comments.append(f"{top_pattern.name}タイトルの平均再生数が高いです。")
            if top_pattern.name in {"TOP形式", "ランキング"}:
                comments.append("ランキング形式を増やすことをおすすめします。")
            elif "？" in top_pattern.name or top_pattern.name == "疑問形":
                comments.append("疑問形タイトルは視聴者のクリック理由を作りやすい傾向です。")
        if report.summary.average_like_rate < 1:
            comments.append("いいね率が低めです。冒頭で共感や驚きを強めると改善しやすいです。")
        return comments

    def _field_map(self, headers) -> dict[str, str]:
        result: dict[str, str] = {}
        for header in headers:
            normalized = self._normalize_header(header)
            for key, aliases in self.HEADER_ALIASES.items():
                if normalized in {self._normalize_header(alias) for alias in aliases}:
                    result[key] = header
        return result

    def _project_index(self, projects: list[ProjectInfo]) -> dict[str, ProjectInfo]:
        index: dict[str, ProjectInfo] = {}
        for project in projects:
            for value in [project.title, project.topic, project.name, project.series]:
                normalized = self._normalize_match_text(value)
                if normalized:
                    index[normalized] = project
        return index

    def _match_project(self, title: str, index: dict[str, ProjectInfo]) -> ProjectInfo | None:
        normalized_title = self._normalize_match_text(title)
        if normalized_title in index:
            return index[normalized_title]
        for key, project in index.items():
            if key and (key in normalized_title or normalized_title in key):
                return project
        return None

    def _detect_platform(self, path: Path, headers) -> str:
        haystack = f"{path.name} {' '.join(headers)}".lower()
        if "tiktok" in haystack:
            return "TikTok"
        if "youtube" in haystack or "高評価" in haystack:
            return "YouTube"
        return "CSV"

    def _parse_int(self, value: object) -> int:
        text = self._clean_text(value).replace(",", "")
        match = re.search(r"-?\d+", text)
        return max(0, int(match.group(0))) if match else 0

    def _clean_text(self, value: object) -> str:
        return str(value or "").strip()

    def _normalize_header(self, value: str) -> str:
        return re.sub(r"\s+", " ", str(value or "").strip().lower())

    def _normalize_match_text(self, value: str) -> str:
        return re.sub(r"\s+", "", str(value or "").strip().lower())

    def _date_key(self, value: str) -> datetime:
        for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y-%m-%d %H:%M:%S", "%Y/%m/%d %H:%M:%S"):
            try:
                return datetime.strptime(value[:19], fmt)
            except ValueError:
                continue
        return datetime.min
