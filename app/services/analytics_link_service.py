from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from difflib import SequenceMatcher
from pathlib import Path

from models import ProjectInfo
from services.analytics_service import AnalyticsRecord


@dataclass
class LinkResult:
    record_key: str
    title: str
    platform: str
    project_name: str = ""
    match_type: str = "unmatched"
    score: float = 0.0


@dataclass
class AnalyticsLinkSummary:
    results: list[LinkResult] = field(default_factory=list)

    @property
    def linked_count(self) -> int:
        return sum(1 for item in self.results if item.project_name)

    @property
    def unlinked_count(self) -> int:
        return sum(1 for item in self.results if not item.project_name)

    @property
    def link_rate(self) -> float:
        return self.linked_count / len(self.results) * 100 if self.results else 0.0

    def platform_counts(self) -> dict[str, tuple[int, int]]:
        counts: dict[str, list[int]] = {}
        for item in self.results:
            current = counts.setdefault(item.platform or "CSV", [0, 0])
            current[1] += 1
            if item.project_name:
                current[0] += 1
        return {key: (value[0], value[1]) for key, value in counts.items()}


class AnalyticsLinkService:
    """CSV動画とローカルプロジェクトの紐付けを管理します。"""

    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir
        self.link_path = base_dir / "analytics_links.json"

    def apply_links(self, records: list[AnalyticsRecord], projects: list[ProjectInfo]) -> AnalyticsLinkSummary:
        manual = self._read_links()
        project_index = self._project_candidates(projects)
        results: list[LinkResult] = []
        for record in records:
            key = self.record_key(record)
            manual_project = manual.get(key, {}).get("project_name", "")
            if manual_project:
                record.project_name = manual_project
                result = LinkResult(key, record.title, record.platform, manual_project, "manual", 1.0)
            else:
                project, match_type, score = self.match_project(record, project_index)
                if project:
                    record.project_name = project.name
                    if not record.genre or record.genre == "未分類":
                        record.genre = project.genre or "未分類"
                    result = LinkResult(key, record.title, record.platform, project.name, match_type, score)
                else:
                    result = LinkResult(key, record.title, record.platform)
            results.append(result)
        return AnalyticsLinkSummary(results)

    def save_manual_link(self, record: AnalyticsRecord, project_name: str) -> None:
        links = self._read_links()
        links[self.record_key(record)] = {
            "project_name": project_name,
            "title": record.title,
            "platform": record.platform,
            "updated_at": datetime.now().isoformat(timespec="seconds"),
        }
        self._write_links(links)

    def remove_manual_link(self, record: AnalyticsRecord) -> None:
        links = self._read_links()
        links.pop(self.record_key(record), None)
        self._write_links(links)

    def record_key(self, record: AnalyticsRecord) -> str:
        raw = "|".join([record.platform, record.video_id, record.url, record.title, record.posted_date])
        return hashlib.sha1(raw.encode("utf-8")).hexdigest()

    def match_project(self, record: AnalyticsRecord, project_index: list[tuple[ProjectInfo, list[str]]]) -> tuple[ProjectInfo | None, str, float]:
        raw_title = record.title.strip()
        normalized_title = self.normalize(raw_title)
        for project, candidates in project_index:
            if raw_title and raw_title in candidates:
                return project, "完全一致", 1.0
        for project, candidates in project_index:
            if normalized_title and normalized_title in [self.normalize(candidate) for candidate in candidates]:
                return project, "正規化一致", 1.0
        for project, candidates in project_index:
            for candidate in candidates:
                normalized_candidate = self.normalize(candidate)
                if normalized_title and normalized_candidate and (normalized_title in normalized_candidate or normalized_candidate in normalized_title):
                    return project, "部分一致", 0.9

        best_project: ProjectInfo | None = None
        best_score = 0.0
        for project, candidates in project_index:
            for candidate in candidates:
                score = SequenceMatcher(None, normalized_title, self.normalize(candidate)).ratio()
                if score > best_score:
                    best_score = score
                    best_project = project
        if best_project and best_score >= 0.72:
            return best_project, "類似度一致", best_score
        return None, "未紐付け", 0.0

    def normalize(self, value: str) -> str:
        text = unicodedata.normalize("NFKC", value or "").strip().lower()
        text = re.sub(r"#\s*shorts?\b", "", text, flags=re.IGNORECASE)
        text = re.sub(r"#\S+", "", text)
        text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
        text = re.sub(r"[^\w一-龥ぁ-んァ-ンー]+", "", text)
        text = re.sub(r"(第?\d+話|\d{1,4})$", "", text)
        return re.sub(r"\s+", "", text)

    def _project_candidates(self, projects: list[ProjectInfo]) -> list[tuple[ProjectInfo, list[str]]]:
        result: list[tuple[ProjectInfo, list[str]]] = []
        for project in projects:
            candidates = [project.title, project.topic, project.name, project.series]
            for file_name in ["title.txt", "topic.txt"]:
                try:
                    candidates.append((project.path / file_name).read_text(encoding="utf-8").strip())
                except OSError:
                    pass
            video_dir = project.path / "video"
            if video_dir.exists():
                candidates.extend(path.stem for path in video_dir.glob("*.mp4"))
            result.append((project, [candidate for candidate in candidates if candidate]))
        return result

    def _read_links(self) -> dict[str, dict[str, str]]:
        if not self.link_path.exists():
            return {}
        try:
            data = json.loads(self.link_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {}
        return data if isinstance(data, dict) else {}

    def _write_links(self, data: dict[str, dict[str, str]]) -> None:
        self.link_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
