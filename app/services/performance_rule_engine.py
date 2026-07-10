from __future__ import annotations

from dataclasses import dataclass, field

from services.analytics_service import AnalyticsRecord, AnalyticsReport


@dataclass
class VideoPerformanceInsight:
    rating: int = 1
    label: str = "要改善"
    reasons: list[str] = field(default_factory=list)
    improvements: list[str] = field(default_factory=list)


class PerformanceRuleEngine:
    LABELS = {
        5: "非常に好調",
        4: "好調",
        3: "平均的",
        2: "改善余地あり",
        1: "要改善",
    }

    def evaluate(self, record: AnalyticsRecord | None, report: AnalyticsReport) -> VideoPerformanceInsight:
        if record is None:
            return VideoPerformanceInsight(reasons=["分析データ不足"], improvements=["分析データ不足"])
        summary = report.summary
        score = 1
        if summary.average_views and record.views >= summary.average_views:
            score += 1
        if summary.average_views and record.views >= summary.average_views * 1.5:
            score += 1
        if summary.average_like_rate and record.like_rate >= summary.average_like_rate:
            score += 1
        if record.ctr and record.ctr >= 5:
            score += 1
        if (record.average_percentage_viewed and record.average_percentage_viewed >= 55) or (record.completion_rate and record.completion_rate >= 45):
            score += 1
        rating = max(1, min(5, score))
        return VideoPerformanceInsight(
            rating=rating,
            label=self.LABELS[rating],
            reasons=self.reasons(record, report),
            improvements=self.improvements(record, report),
        )

    def reasons(self, record: AnalyticsRecord, report: AnalyticsReport) -> list[str]:
        if not record:
            return ["分析データ不足"]
        lines: list[str] = []
        average_views = report.summary.average_views or 0
        if record.ctr >= 5:
            lines.append("CTRが高いため、タイトルやサムネイルが効果的だった可能性があります。")
        if record.average_percentage_viewed >= 55 or record.completion_rate >= 45:
            lines.append("視聴維持率が高いため、冒頭のフックや動画テンポが良かった可能性があります。")
        if average_views and record.views >= average_views * 1.3 and record.like_rate < max(report.summary.average_like_rate * 0.8, 1):
            lines.append("再生数は高いですが、いいね率が低いため、内容への満足度改善を試す価値があります。")
        if record.comment_rate >= max(report.summary.average_comment_rate * 1.2, 0.5):
            lines.append("コメント率が高く、視聴者の反応を引き出せている可能性があります。")
        if record.impressions and record.ctr and record.ctr < 3:
            lines.append("表示回数はありますがCTRが低いため、タイトル改善をおすすめします。")
        if average_views and record.views < average_views * 0.7 and (record.average_percentage_viewed >= 55 or record.completion_rate >= 45):
            lines.append("再生数は少ないですが視聴維持率が高いため、再投稿やタイトル変更の候補と考えられます。")
        if not lines:
            lines.append("取得できる指標では大きな偏りは少なく、平均的な成績と考えられます。")
        return lines

    def improvements(self, record: AnalyticsRecord, report: AnalyticsReport) -> list[str]:
        if not record or record.views <= 0:
            return ["分析データ不足"]
        items: list[str] = []
        title = record.title
        if len(title) > 32:
            items.append("タイトルを短くする")
        if "？" not in title and "?" not in title:
            items.append("疑問形タイトルにする")
        if not any(char.isdigit() for char in title):
            items.append("数字を入れる")
        if record.ctr and record.ctr < 3:
            items.append("タイトルやサムネイルの訴求を強める")
        if (record.average_percentage_viewed and record.average_percentage_viewed < 35) or (record.completion_rate and record.completion_rate < 30):
            items.append("冒頭3秒を強くする")
            items.append("画像切り替えを早くする")
            items.append("字幕量を減らす")
        if record.like_rate < max(report.summary.average_like_rate * 0.8, 1):
            items.append("BGM音量を下げる")
        if record.rating >= 4 or record.views >= (report.summary.average_views or 0) * 1.3:
            items.append("続編を作る")
            items.append("同テーマで別角度の動画を作る")
            items.append("高評価だったタイトル構造を再利用する")
        return list(dict.fromkeys(items))[:5] or ["分析データ不足"]

    def cross_platform(self, youtube: AnalyticsRecord | None, tiktok: AnalyticsRecord | None, report: AnalyticsReport) -> list[str]:
        if not youtube or not tiktok:
            return ["YouTube / TikTokの両方に紐付くと横断比較を表示します。"]
        yt_records = [item for item in report.records if item.platform == "YouTube"]
        tt_records = [item for item in report.records if item.platform == "TikTok"]
        yt_average = sum(item.views for item in yt_records) / len(yt_records) if yt_records else report.summary.average_views
        tt_average = sum(item.views for item in tt_records) / len(tt_records) if tt_records else report.summary.average_views
        lines: list[str] = []
        if yt_average and youtube.views / yt_average > (tiktok.views / tt_average if tt_average else 0):
            lines.append("YouTubeではチャンネル平均比で再生が強い傾向です。")
        else:
            lines.append("TikTokではチャンネル平均比で再生が強い傾向です。")
        if youtube.average_percentage_viewed and youtube.average_percentage_viewed >= 50:
            lines.append("YouTubeでは視聴維持率が高い可能性があります。")
        if tiktok.like_rate > youtube.like_rate:
            lines.append("TikTokでは反応率が高い可能性があります。")
        if youtube.subscriber_change > 0:
            lines.append("YouTubeでは登録者増加につながった可能性があります。")
        return lines
