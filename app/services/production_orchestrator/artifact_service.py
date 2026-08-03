from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import wave
from pathlib import Path
from typing import Any

from PySide6.QtGui import QImage

from models import AppSettings, ProjectInfo


SMALL_INPUT_FILES = [
    "story.json",
    "title.txt",
    "script.txt",
    "voice.txt",
    "image_prompts.txt",
    "subtitles.txt",
    "hashtags.txt",
]


class ArtifactService:
    def __init__(self, settings: AppSettings) -> None:
        self.settings = settings

    def snapshot(self, project: ProjectInfo) -> dict[str, Any]:
        hashes = {}
        for name in SMALL_INPUT_FILES:
            path = project.path / name
            if path.exists() and path.is_file():
                hashes[name] = self.sha256(path)
        return {
            "story_hash": hashes.get("story.json", ""),
            "factory_export_hashes": {key: value for key, value in hashes.items() if key != "story.json"},
            "settings_hash": self.settings_hash(),
            "artifact_fingerprints": {
                "images": self.images_fingerprint(project),
                "audio": self.file_fingerprint(project.path / "audio" / "voice.wav"),
                "subtitles": self.file_fingerprint(project.path / "video" / "subtitles.ass"),
                "video": self.file_fingerprint(project.path / "video" / "final.mp4"),
            },
        }

    def artifact_status(self, project: ProjectInfo, snapshot: dict[str, Any] | None = None) -> dict[str, dict[str, Any]]:
        snapshot = snapshot or {}
        statuses = {
            "factory_export": self.factory_export_status(project),
            "images": self.images_status(project),
            "audio": self.audio_status(project),
            "subtitles": self.subtitle_status(project),
            "video": self.video_status(project),
            "youtube": self.youtube_status(project),
            "tiktok": self.tiktok_status(project),
        }
        self._apply_stale(project, statuses, snapshot)
        return statuses

    def factory_export_status(self, project: ProjectInfo) -> dict[str, Any]:
        required = ["title.txt", "script.txt", "voice.txt", "image_prompts.txt", "subtitles.txt"]
        missing = [name for name in required if not (project.path / name).exists() or (project.path / name).stat().st_size <= 0]
        return {"state": "missing" if missing else "fresh", "missing": missing}

    def images_status(self, project: ProjectInfo) -> dict[str, Any]:
        valid = []
        invalid = []
        for index in range(1, int(project.image_count or 0) + 1):
            path = project.path / "images" / f"{index:03d}.png"
            if not path.exists():
                invalid.append(index)
                continue
            if self.is_valid_image(path):
                valid.append(index)
            else:
                invalid.append(index)
        state = "fresh" if len(valid) >= int(project.image_count or 0) else "missing"
        if invalid and any((project.path / "images" / f"{index:03d}.png").exists() for index in invalid):
            state = "invalid"
        return {"state": state, "valid_indices": valid, "invalid_indices": invalid}

    def audio_status(self, project: ProjectInfo) -> dict[str, Any]:
        path = project.path / "audio" / "voice.wav"
        if not path.exists():
            return {"state": "missing"}
        if path.stat().st_size <= 0:
            return {"state": "invalid"}
        try:
            with wave.open(str(path), "rb") as stream:
                frames = stream.getnframes()
                rate = stream.getframerate()
            if frames <= 0 or rate <= 0:
                return {"state": "invalid"}
        except Exception:
            return {"state": "invalid"}
        return {"state": "fresh", "path": "audio/voice.wav"}

    def subtitle_status(self, project: ProjectInfo) -> dict[str, Any]:
        path = project.path / "video" / "subtitles.ass"
        if not path.exists():
            return {"state": "missing"}
        if path.stat().st_size <= 0:
            return {"state": "invalid"}
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return {"state": "invalid"}
        if "[Script Info]" not in text or "[Events]" not in text:
            return {"state": "invalid"}
        return {"state": "fresh", "path": "video/subtitles.ass"}

    def video_status(self, project: ProjectInfo) -> dict[str, Any]:
        path = project.path / "video" / "final.mp4"
        if not path.exists():
            return {"state": "missing"}
        if path.stat().st_size <= 0:
            return {"state": "invalid"}
        try:
            header = path.read_bytes()[:64]
        except OSError:
            return {"state": "invalid"}
        if b"ftyp" not in header:
            return {"state": "invalid"}
        return {"state": "fresh", "path": "video/final.mp4"}

    def youtube_status(self, project: ProjectInfo) -> dict[str, Any]:
        state = dict(project.youtube_upload or {})
        video_id = str(state.get("video_id") or "")
        if video_id:
            return {"state": "fresh", "video_id": video_id, "duplicate": True}
        return {"state": "missing"}

    def tiktok_status(self, project: ProjectInfo) -> dict[str, Any]:
        state = dict(project.tiktok_upload or {})
        publish_id = str(state.get("publish_id") or "")
        if publish_id:
            return {"state": "fresh", "publish_id": publish_id, "duplicate": True}
        return {"state": "missing"}

    def is_valid_image(self, path: Path) -> bool:
        if not path.exists() or path.stat().st_size <= 0:
            return False
        image = QImage(str(path))
        return not image.isNull() and image.width() > 0 and image.height() > 0

    def ffmpeg_available(self) -> bool:
        return shutil.which(self.settings.ffmpeg_path) is not None or Path(self.settings.ffmpeg_path).exists()

    def ffprobe_available(self) -> bool:
        return shutil.which(self.ffprobe_path()) is not None or Path(self.ffprobe_path()).exists()

    def ffprobe_path(self) -> str:
        ffmpeg_path = self.settings.ffmpeg_path
        path = Path(ffmpeg_path)
        if path.name.lower().startswith("ffmpeg"):
            candidate = path.with_name(path.name.replace("ffmpeg", "ffprobe", 1))
            if candidate.exists():
                return str(candidate)
        return "ffprobe"

    def probe_video(self, path: Path) -> bool:
        if not self.ffprobe_available():
            return self.video_status(ProjectInfo(path.parent.parent.name, path.parent.parent))["state"] == "fresh"
        command = [self.ffprobe_path(), "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        return completed.returncode == 0

    def sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def settings_hash(self) -> str:
        relevant = {
            "image_count": getattr(self.settings, "default_image_count", 5),
            "subtitles_enabled": getattr(self.settings, "subtitles_enabled", True),
            "title_enabled": getattr(self.settings, "title_enabled", False),
            "ffmpeg_path": getattr(self.settings, "ffmpeg_path", "ffmpeg"),
            "voicevox_url": getattr(self.settings, "voicevox_url", ""),
            "voicevox_speaker_id": getattr(self.settings, "voicevox_speaker_id", 0),
        }
        data = json.dumps(relevant, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return hashlib.sha256(data).hexdigest()

    def file_fingerprint(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"exists": False}
        stat = path.stat()
        return {"exists": True, "size": stat.st_size, "mtime": stat.st_mtime}

    def images_fingerprint(self, project: ProjectInfo) -> dict[str, Any]:
        values = {}
        for index in range(1, int(project.image_count or 0) + 1):
            values[f"{index:03d}.png"] = self.file_fingerprint(project.path / "images" / f"{index:03d}.png")
        return values

    def _apply_stale(self, project: ProjectInfo, statuses: dict[str, dict[str, Any]], snapshot: dict[str, Any]) -> None:
        if not snapshot:
            return
        hashes = snapshot.get("factory_export_hashes", {}) if isinstance(snapshot.get("factory_export_hashes"), dict) else {}
        current_hashes = {}
        for name in ["voice.txt", "image_prompts.txt", "subtitles.txt"]:
            path = project.path / name
            if path.exists():
                current_hashes[name] = self.sha256(path)
        if hashes.get("voice.txt") and current_hashes.get("voice.txt") and hashes["voice.txt"] != current_hashes["voice.txt"]:
            self._mark_stale(statuses, ["audio", "subtitles", "video"], "voice.txt changed")
        if hashes.get("image_prompts.txt") and current_hashes.get("image_prompts.txt") and hashes["image_prompts.txt"] != current_hashes["image_prompts.txt"]:
            self._mark_stale(statuses, ["images", "video"], "image_prompts.txt changed")
        if hashes.get("subtitles.txt") and current_hashes.get("subtitles.txt") and hashes["subtitles.txt"] != current_hashes["subtitles.txt"]:
            self._mark_stale(statuses, ["subtitles", "video"], "subtitles.txt changed")

        final = project.path / "video" / "final.mp4"
        if final.exists():
            final_mtime = final.stat().st_mtime
            for path in [project.path / "audio" / "voice.wav", project.path / "video" / "subtitles.ass"]:
                if path.exists() and path.stat().st_mtime > final_mtime:
                    self._mark_stale(statuses, ["video"], f"{path.name} newer than final.mp4")
            images_dir = project.path / "images"
            if images_dir.exists():
                if any(path.is_file() and path.stat().st_mtime > final_mtime for path in images_dir.glob("*.png")):
                    self._mark_stale(statuses, ["video"], "images newer than final.mp4")

    def _mark_stale(self, statuses: dict[str, dict[str, Any]], keys: list[str], reason: str) -> None:
        for key in keys:
            if key in statuses and statuses[key].get("state") == "fresh":
                statuses[key]["state"] = "stale"
                statuses[key]["stale_reason"] = reason
