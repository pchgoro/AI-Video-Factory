from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import ImageGenerationError, UsageEstimate


@dataclass
class UsageDecision:
    allowed: bool
    message: str
    daily_count: int
    project_count: int


class ImageGenerationUsageService:
    """Local counters for Cloudflare usage guardrails; not a Cloudflare billing source."""

    def __init__(self, usage_path: Path) -> None:
        self.usage_path = usage_path

    def check_limits(
        self,
        project_id: str,
        request_count: int,
        max_images_per_run: int,
        daily_request_limit: int,
        per_project_image_limit: int,
    ) -> UsageDecision:
        data = self._load()
        today = self._today_utc()
        if data.get("date") != today:
            data = {"date": today, "daily_count": 0, "projects": {}}
        daily_count = int(data.get("daily_count", 0) or 0)
        projects = data.setdefault("projects", {})
        project_count = int(projects.get(project_id, 0) or 0) if isinstance(projects, dict) else 0
        if request_count > max_images_per_run:
            return UsageDecision(False, "1回の画像生成上限を超えています。", daily_count, project_count)
        if daily_request_limit > 0 and daily_count + request_count > daily_request_limit:
            return UsageDecision(False, "アプリ内の日次生成リクエスト上限を超えます。", daily_count, project_count)
        if per_project_image_limit > 0 and project_count + request_count > per_project_image_limit:
            return UsageDecision(False, "このプロジェクトの画像生成上限を超えます。", daily_count, project_count)
        return UsageDecision(True, "OK", daily_count, project_count)

    def record_success(self, project_id: str, count: int = 1) -> None:
        data = self._load()
        today = self._today_utc()
        if data.get("date") != today:
            data = {"date": today, "daily_count": 0, "projects": {}}
        data["daily_count"] = int(data.get("daily_count", 0) or 0) + count
        projects = data.setdefault("projects", {})
        if not isinstance(projects, dict):
            projects = {}
            data["projects"] = projects
        projects[project_id] = int(projects.get(project_id, 0) or 0) + count
        self._save(data)

    def summary(self, project_id: str) -> dict[str, object]:
        data = self._load()
        projects = data.get("projects", {})
        return {
            "date": data.get("date") or self._today_utc(),
            "daily_count": int(data.get("daily_count", 0) or 0),
            "project_count": int(projects.get(project_id, 0) or 0) if isinstance(projects, dict) else 0,
            "note": "アプリ内推定です。Cloudflare Dashboardの実使用量とは差が出る可能性があります。",
        }

    def _load(self) -> dict[str, object]:
        if not self.usage_path.exists():
            return {"date": self._today_utc(), "daily_count": 0, "projects": {}}
        try:
            data = json.loads(self.usage_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"date": self._today_utc(), "daily_count": 0, "projects": {}}
        return data if isinstance(data, dict) else {"date": self._today_utc(), "daily_count": 0, "projects": {}}

    def _save(self, data: dict[str, object]) -> None:
        self.usage_path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.usage_path.with_suffix(self.usage_path.suffix + ".tmp")
        temp_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        temp_path.replace(self.usage_path)

    def _today_utc(self) -> str:
        return datetime.now(timezone.utc).date().isoformat()
