from __future__ import annotations

from datetime import datetime
from pathlib import Path

from models import JOB_STATUSES, ProjectInfo
from services.project_service import ProjectService


class JobService:
    """Persist and restore production job state without replacing progress checks."""

    def __init__(self, project_service: ProjectService) -> None:
        self.project_service = project_service

    def ensure_job(self, project: ProjectInfo) -> ProjectInfo:
        job = dict(project.job or {})
        now = self._now()
        changed = False
        if not job:
            job = {
                "project_id": project.name,
                "status": self.infer_status(project.path),
                "retry_count": 0,
                "last_error": "",
                "created_time": now,
                "updated_time": now,
            }
            changed = True
        else:
            for key, value in {
                "project_id": project.name,
                "status": self.infer_status(project.path),
                "retry_count": 0,
                "last_error": "",
                "created_time": now,
                "updated_time": now,
            }.items():
                if key not in job:
                    job[key] = value
                    changed = True
            if job.get("status") not in JOB_STATUSES:
                job["status"] = self.infer_status(project.path)
                changed = True
        if changed:
            self.project_service.update_metadata(project.path, {"job": job})
            return self.project_service.load_project(project.path)
        return project

    def set_status(self, project: ProjectInfo, status: str, last_error: str = "") -> ProjectInfo:
        if status not in JOB_STATUSES:
            raise ValueError(f"Unsupported job status: {status}")
        job = dict(project.job or {})
        now = self._now()
        job.update(
            {
                "project_id": project.name,
                "status": status,
                "last_error": last_error,
                "updated_time": now,
            }
        )
        job.setdefault("retry_count", 0)
        job.setdefault("created_time", now)
        self.project_service.update_metadata(project.path, {"job": job})
        return self.project_service.load_project(project.path)

    def record_failure(self, project: ProjectInfo, error: str) -> ProjectInfo:
        job = dict(project.job or {})
        retry_count = int(job.get("retry_count", 0) or 0) + 1
        now = self._now()
        job.update(
            {
                "project_id": project.name,
                "status": "failed",
                "retry_count": retry_count,
                "last_error": error,
                "updated_time": now,
            }
        )
        job.setdefault("created_time", now)
        self.project_service.update_metadata(project.path, {"job": job})
        return self.project_service.load_project(project.path)

    def infer_status(self, project_dir: Path) -> str:
        if (project_dir / "posted.txt").exists():
            return "youtube_uploaded"
        if (project_dir / "video" / "final.mp4").exists():
            return "video_ready"
        if (project_dir / "audio" / "voice.wav").exists():
            return "audio_ready"
        if any((project_dir / "images").glob("*.png")):
            return "images_ready"
        if (project_dir / "script.txt").exists() and (project_dir / "script.txt").read_text(encoding="utf-8").strip():
            return "script_ready"
        return "draft"

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
