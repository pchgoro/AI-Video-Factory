from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from PySide6.QtGui import QImage

from models import AppSettings, ProjectInfo


QUALITY_CHECK_FILE = "quality_check.json"
QUALITY_LEVELS = {"PASS", "WARNING", "ERROR"}
OVERALL_STATUSES = {"PASS", "WARNING", "ERROR"}
MIN_IMAGE_WIDTH = 720
MIN_IMAGE_HEIGHT = 1280
MIN_VIDEO_WIDTH = 1080
MIN_VIDEO_HEIGHT = 1920
SHORTS_ASPECT_RATIO = 9 / 16
ASPECT_TOLERANCE = 0.04
SUBTITLE_SHORT_WARNING = 2
SUBTITLE_LONG_WARNING = 80
MIN_AUDIO_SECONDS = 1.0
MIN_VIDEO_SECONDS = 1.0
VIDEO_DURATION_WARNING_SECONDS = 10.0


@dataclass
class QualityCheckItem:
    level: str
    category: str
    check_id: str
    message: str
    target: str = ""
    scene_index: int | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        data = {
            "level": self.level if self.level in QUALITY_LEVELS else "WARNING",
            "category": self.category,
            "check_id": self.check_id,
            "message": self.message,
            "target": self.target,
            "details": self.details,
        }
        if self.scene_index is not None:
            data["scene_index"] = self.scene_index
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QualityCheckItem":
        return cls(
            level=str(data.get("level") or "WARNING"),
            category=str(data.get("category") or ""),
            check_id=str(data.get("check_id") or ""),
            message=str(data.get("message") or ""),
            target=str(data.get("target") or ""),
            scene_index=data.get("scene_index") if isinstance(data.get("scene_index"), int) else None,
            details=dict(data.get("details") or {}) if isinstance(data.get("details"), dict) else {},
        )


@dataclass
class QualityCheckResult:
    project_id: str
    checked_at: str
    overall_status: str = "PASS"
    items: list[QualityCheckItem] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)

    @property
    def error_count(self) -> int:
        return int(self.summary.get("errors", 0))

    @property
    def warning_count(self) -> int:
        return int(self.summary.get("warnings", 0))

    def add(self, item: QualityCheckItem) -> None:
        self.items.append(item)
        self._recalculate()

    def _recalculate(self) -> None:
        errors = sum(1 for item in self.items if item.level == "ERROR")
        warnings = sum(1 for item in self.items if item.level == "WARNING")
        passes = sum(1 for item in self.items if item.level == "PASS")
        self.summary = {"passes": passes, "warnings": warnings, "errors": errors, "total": len(self.items)}
        if errors:
            self.overall_status = "ERROR"
        elif warnings:
            self.overall_status = "WARNING"
        else:
            self.overall_status = "PASS"

    def to_dict(self) -> dict[str, Any]:
        self._recalculate()
        return {
            "schema_version": "1.0",
            "project_id": self.project_id,
            "checked_at": self.checked_at,
            "overall_status": self.overall_status,
            "summary": self.summary,
            "items": [item.to_dict() for item in self.items],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "QualityCheckResult":
        result = cls(
            project_id=str(data.get("project_id") or ""),
            checked_at=str(data.get("checked_at") or ""),
            overall_status=str(data.get("overall_status") or "WARNING"),
            items=[QualityCheckItem.from_dict(item) for item in data.get("items", []) if isinstance(item, dict)],
            summary=dict(data.get("summary") or {}) if isinstance(data.get("summary"), dict) else {},
        )
        result._recalculate()
        return result


ProbeRunner = Callable[[Path], dict[str, Any]]


class QualityCheckService:
    def __init__(
        self,
        settings: AppSettings,
        story_service=None,
        probe_runner: ProbeRunner | None = None,
        silence_detector: Callable[[Path], bool] | None = None,
    ) -> None:
        self.settings = settings
        self.story_service = story_service
        self.probe_runner = probe_runner or self._run_ffprobe
        self.silence_detector = silence_detector or self._detect_long_silence

    def run(self, project: ProjectInfo) -> QualityCheckResult:
        result = QualityCheckResult(project_id=project.name, checked_at=self._now())
        story = self._load_story(project, result)
        self._check_text(project, story, result)
        self._check_images(project, result)
        audio_info = self._check_audio(project, result)
        video_info = self._check_video(project, story, result)
        self._check_publishing(project, video_info, result)
        if audio_info and video_info:
            self._compare_audio_video_duration(audio_info, video_info, result)
        self.save_result(project, result)
        return result

    def load_result(self, project: ProjectInfo) -> QualityCheckResult | None:
        path = project.path / QUALITY_CHECK_FILE
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        return QualityCheckResult.from_dict(data)

    def save_result(self, project: ProjectInfo, result: QualityCheckResult) -> None:
        self._atomic_json(project.path / QUALITY_CHECK_FILE, result.to_dict())

    def has_blocking_errors(self, project: ProjectInfo) -> tuple[bool, QualityCheckResult]:
        result = self.run(project)
        return result.overall_status == "ERROR", result

    def _load_story(self, project: ProjectInfo, result: QualityCheckResult):
        if self.story_service is None:
            return None
        try:
            story = self.story_service.load_story(project)
        except Exception as exc:
            self._add(result, "ERROR", "Story", "story_load", f"story.json could not be loaded: {self._safe_error(exc)}", "story.json")
            return None
        if story is None:
            self._add(result, "WARNING", "Story", "story_missing", "story.json is not available.", "story.json")
            return None
        self._add(result, "PASS", "Story", "story_load", "story.json loaded.", "story.json")
        try:
            validation = self.story_service.validator.validate(story)
        except Exception as exc:
            self._add(result, "ERROR", "Story", "story_validation", f"Story validation failed: {self._safe_error(exc)}", "story.json")
            return story
        for issue in validation.errors:
            self._add(result, "ERROR", "Story", "story_validation", issue.message, issue.field, issue.scene_index)
        for issue in validation.warnings:
            self._add(result, "WARNING", "Story", "story_validation", issue.message, issue.field, issue.scene_index)
        if not validation.errors:
            self._add(result, "PASS", "Story", "story_validation", "Story validation has no blocking errors.", "story.json")
        return story

    def _check_text(self, project: ProjectInfo, story, result: QualityCheckResult) -> None:
        self._check_nonempty_file(project, result, "Text", "title_present", project.path / "title.txt", "title.txt is present.")
        self._check_nonempty_file(project, result, "Text", "script_present", project.path / "script.txt", "script.txt is present.")
        self._check_nonempty_file(project, result, "Text", "voice_present", project.path / "voice.txt", "voice.txt is present.")
        self._check_nonempty_file(project, result, "Text", "subtitles_present", project.path / "subtitles.txt", "subtitles.txt is present.")
        if story is None:
            return
        scenes = list(getattr(story, "scenes", []) or [])
        indices = [int(getattr(scene, "scene_index", 0) or 0) for scene in scenes]
        duplicates = sorted({index for index in indices if indices.count(index) > 1})
        if duplicates:
            self._add(result, "ERROR", "Story", "scene_duplicate_index", f"Duplicate scene_index values: {duplicates}", "scenes")
        expected = list(range(1, len(scenes) + 1))
        if sorted(indices) != expected:
            self._add(result, "ERROR", "Story", "scene_missing_index", f"Scene indices should be contiguous: {expected}", "scenes")
        else:
            self._add(result, "PASS", "Story", "scene_indices", "Scene indices are contiguous.", "scenes")
        if int(project.image_count or 0) and scenes and len(scenes) != int(project.image_count or 0):
            self._add(
                result,
                "WARNING",
                "Story",
                "scene_image_count_mismatch",
                f"Story scenes ({len(scenes)}) differ from required images ({project.image_count}).",
                "story.json",
            )
        for scene in scenes:
            index = int(getattr(scene, "scene_index", 0) or 0)
            if not str(getattr(scene, "narration", "") or "").strip():
                self._add(result, "ERROR", "Story", "scene_narration_required", "Scene narration is empty.", "narration", index)
            if not str(getattr(scene, "subtitle", "") or "").strip():
                self._add(result, "ERROR", "Story", "scene_subtitle_required", "Scene subtitle is empty.", "subtitle", index)
            else:
                length = len(str(scene.subtitle).strip())
                if length < SUBTITLE_SHORT_WARNING or length > SUBTITLE_LONG_WARNING:
                    self._add(result, "WARNING", "Story", "scene_subtitle_length", f"Subtitle length is unusual: {length} chars.", "subtitle", index)
            if not str(getattr(scene, "image_prompt", "") or "").strip():
                self._add(result, "ERROR", "Story", "scene_image_prompt_required", "Scene image_prompt is empty.", "image_prompt", index)

    def _check_images(self, project: ProjectInfo, result: QualityCheckResult) -> None:
        expected_count = int(project.image_count or 0)
        if expected_count <= 0:
            self._add(result, "WARNING", "Images", "image_count", "Project image count is not set.", "images")
            return
        previous_hash = ""
        for index in range(1, expected_count + 1):
            path = project.path / "images" / f"{index:03d}.png"
            target = self._relative(project, path)
            if not path.exists():
                self._add(result, "ERROR", "Images", "image_missing", "Required image is missing.", target, index)
                previous_hash = ""
                continue
            if path.stat().st_size <= 0:
                self._add(result, "ERROR", "Images", "image_empty", "Image file is 0 bytes.", target, index)
                previous_hash = ""
                continue
            image = QImage(str(path))
            if image.isNull() or image.width() <= 0 or image.height() <= 0:
                self._add(result, "ERROR", "Images", "image_decode", "Image cannot be opened.", target, index)
                previous_hash = ""
                continue
            self._add(result, "PASS", "Images", "image_valid", f"Image is readable ({image.width()}x{image.height()}).", target, index)
            if image.width() < MIN_IMAGE_WIDTH or image.height() < MIN_IMAGE_HEIGHT:
                self._add(result, "WARNING", "Images", "image_resolution", f"Image resolution is small: {image.width()}x{image.height()}.", target, index)
            digest = self._sha256(path)
            if previous_hash and digest == previous_hash:
                self._add(result, "WARNING", "Images", "consecutive_duplicate_image", "Consecutive images are identical.", target, index)
            previous_hash = digest

    def _check_audio(self, project: ProjectInfo, result: QualityCheckResult) -> dict[str, Any] | None:
        path = project.path / "audio" / "voice.wav"
        target = self._relative(project, path)
        if not path.exists():
            self._add(result, "ERROR", "Audio", "audio_missing", "VOICEVOX audio is missing.", target)
            return None
        if path.stat().st_size <= 0:
            self._add(result, "ERROR", "Audio", "audio_empty", "VOICEVOX audio is 0 bytes.", target)
            return None
        try:
            info = self.probe_runner(path)
        except Exception as exc:
            self._add(result, "ERROR", "Audio", "audio_probe", f"Audio cannot be read by ffprobe: {self._safe_error(exc)}", target)
            return None
        duration = self._duration(info)
        if duration <= 0:
            self._add(result, "ERROR", "Audio", "audio_duration_zero", "Audio duration is 0 seconds.", target)
        elif duration < MIN_AUDIO_SECONDS:
            self._add(result, "ERROR", "Audio", "audio_duration_short", f"Audio is too short: {duration:.2f}s.", target)
        else:
            self._add(result, "PASS", "Audio", "audio_probe", f"Audio is readable ({duration:.2f}s).", target)
        try:
            if self.silence_detector(path):
                self._add(result, "WARNING", "Audio", "audio_long_silence", "Long silence was detected.", target)
        except Exception as exc:
            self._add(result, "WARNING", "Audio", "audio_silence_check", f"Silence check could not complete: {self._safe_error(exc)}", target)
        return info

    def _check_video(self, project: ProjectInfo, story, result: QualityCheckResult) -> dict[str, Any] | None:
        path = project.path / "video" / "final.mp4"
        target = self._relative(project, path)
        if not path.exists():
            self._add(result, "ERROR", "Video", "video_missing", "final.mp4 is missing.", target)
            return None
        if path.stat().st_size <= 0:
            self._add(result, "ERROR", "Video", "video_empty", "final.mp4 is 0 bytes.", target)
            return None
        try:
            info = self.probe_runner(path)
        except Exception as exc:
            self._add(result, "ERROR", "Video", "video_probe", f"final.mp4 cannot be read by ffprobe: {self._safe_error(exc)}", target)
            return None
        duration = self._duration(info)
        if duration <= 0:
            self._add(result, "ERROR", "Video", "video_duration_zero", "Video duration is 0 seconds.", target)
        elif duration < MIN_VIDEO_SECONDS:
            self._add(result, "ERROR", "Video", "video_duration_short", f"Video is too short: {duration:.2f}s.", target)
        video_stream = self._first_stream(info, "video")
        audio_stream = self._first_stream(info, "audio")
        if not video_stream:
            self._add(result, "ERROR", "Video", "video_stream_missing", "Video stream is missing.", target)
        if not audio_stream:
            self._add(result, "ERROR", "Video", "audio_stream_missing", "Audio stream is missing from final.mp4.", target)
        if video_stream:
            width = int(video_stream.get("width") or 0)
            height = int(video_stream.get("height") or 0)
            fps = self._fps(video_stream)
            self._add(result, "PASS", "Video", "video_probe", f"Video is readable ({width}x{height}, {fps:.2f}fps, {duration:.2f}s).", target)
            if width < MIN_VIDEO_WIDTH or height < MIN_VIDEO_HEIGHT:
                self._add(result, "WARNING", "Video", "video_resolution", f"Resolution is below 1080x1920: {width}x{height}.", target)
            if height and abs((width / height) - SHORTS_ASPECT_RATIO) > ASPECT_TOLERANCE:
                self._add(result, "WARNING", "Video", "video_aspect_ratio", f"Video is not close to 9:16: {width}x{height}.", target)
            if fps <= 0:
                self._add(result, "WARNING", "Video", "video_fps", "FPS could not be detected.", target)
        if story is not None and duration > 0:
            estimated = float(getattr(story, "estimated_duration", 0.0) or 0.0)
            if estimated and abs(duration - estimated) > VIDEO_DURATION_WARNING_SECONDS:
                self._add(
                    result,
                    "WARNING",
                    "Video",
                    "video_duration_estimate_mismatch",
                    f"Video duration ({duration:.2f}s) differs from story estimate ({estimated:.2f}s).",
                    target,
                )
        return info

    def _check_publishing(self, project: ProjectInfo, video_info: dict[str, Any] | None, result: QualityCheckResult) -> None:
        title = (project.title or self._read_text(project.path / "title.txt")).strip()
        if title:
            self._add(result, "PASS", "Publishing", "youtube_title", "YouTube title is available.", "title.txt")
        else:
            self._add(result, "ERROR", "Publishing", "youtube_title", "YouTube title is missing.", "title.txt")
        final = project.path / "video" / "final.mp4"
        if video_info is not None and final.exists() and final.stat().st_size > 0:
            self._add(result, "PASS", "Publishing", "tiktok_video", "TikTok upload video is available.", self._relative(project, final))
        else:
            self._add(result, "ERROR", "Publishing", "tiktok_video", "TikTok upload requires a valid final.mp4.", self._relative(project, final))
        youtube = project.youtube_upload or {}
        if youtube.get("video_id"):
            self._add(result, "WARNING", "Publishing", "youtube_duplicate", "This project already has a YouTube video ID.", "project.json")
        tiktok = project.tiktok_upload or {}
        if tiktok.get("publish_id") or tiktok.get("status") == "uploaded":
            self._add(result, "WARNING", "Publishing", "tiktok_duplicate", "This project already has a TikTok upload state.", "project.json")

    def _compare_audio_video_duration(self, audio_info: dict[str, Any], video_info: dict[str, Any], result: QualityCheckResult) -> None:
        audio_duration = self._duration(audio_info)
        video_duration = self._duration(video_info)
        if audio_duration > 0 and video_duration > 0 and abs(audio_duration - video_duration) > VIDEO_DURATION_WARNING_SECONDS:
            self._add(
                result,
                "WARNING",
                "Audio",
                "audio_video_duration_mismatch",
                f"Audio duration ({audio_duration:.2f}s) differs from video duration ({video_duration:.2f}s).",
                "audio/voice.wav",
            )

    def _check_nonempty_file(self, project: ProjectInfo, result: QualityCheckResult, category: str, check_id: str, path: Path, pass_message: str) -> None:
        target = self._relative(project, path)
        if not path.exists():
            self._add(result, "ERROR", category, check_id, f"{path.name} is missing.", target)
            return
        if not self._read_text(path).strip():
            self._add(result, "ERROR", category, check_id, f"{path.name} is empty.", target)
            return
        self._add(result, "PASS", category, check_id, pass_message, target)

    def _run_ffprobe(self, path: Path) -> dict[str, Any]:
        command = [
            self._ffprobe_path(),
            "-v",
            "error",
            "-show_entries",
            "format=duration:stream=index,codec_type,width,height,r_frame_rate,avg_frame_rate",
            "-of",
            "json",
            str(path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=15)
        if completed.returncode != 0:
            raise RuntimeError((completed.stderr or "ffprobe failed").strip())
        try:
            data = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise RuntimeError("ffprobe returned invalid JSON") from exc
        if not isinstance(data, dict):
            raise RuntimeError("ffprobe returned an invalid payload")
        return data

    def _ffprobe_path(self) -> str:
        ffmpeg_path = getattr(self.settings, "ffmpeg_path", "ffmpeg") or "ffmpeg"
        path = Path(ffmpeg_path)
        if path.name.lower().startswith("ffmpeg"):
            candidate = path.with_name(path.name.replace("ffmpeg", "ffprobe", 1))
            if candidate.exists():
                return str(candidate)
        return "ffprobe"

    def _detect_long_silence(self, path: Path) -> bool:
        ffmpeg_path = getattr(self.settings, "ffmpeg_path", "ffmpeg") or "ffmpeg"
        if shutil.which(ffmpeg_path) is None and not Path(ffmpeg_path).exists():
            return False
        command = [
            ffmpeg_path,
            "-hide_banner",
            "-nostats",
            "-i",
            str(path),
            "-af",
            "silencedetect=noise=-45dB:d=2.0",
            "-f",
            "null",
            "-",
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False, timeout=20)
        output = f"{completed.stdout}\n{completed.stderr}"
        return "silence_start" in output and "silence_end" in output

    def _add(
        self,
        result: QualityCheckResult,
        level: str,
        category: str,
        check_id: str,
        message: str,
        target: str = "",
        scene_index: int | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        result.add(QualityCheckItem(level, category, check_id, message, target, scene_index, details or {}))

    def _duration(self, info: dict[str, Any]) -> float:
        format_info = info.get("format", {}) if isinstance(info.get("format"), dict) else {}
        try:
            return float(format_info.get("duration") or 0.0)
        except (TypeError, ValueError):
            return 0.0

    def _first_stream(self, info: dict[str, Any], codec_type: str) -> dict[str, Any] | None:
        streams = info.get("streams", [])
        if not isinstance(streams, list):
            return None
        for stream in streams:
            if isinstance(stream, dict) and stream.get("codec_type") == codec_type:
                return stream
        return None

    def _fps(self, stream: dict[str, Any]) -> float:
        raw = str(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "")
        if "/" in raw:
            left, right = raw.split("/", 1)
            try:
                denominator = float(right)
                return 0.0 if denominator == 0 else float(left) / denominator
            except ValueError:
                return 0.0
        try:
            return float(raw)
        except ValueError:
            return 0.0

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return ""

    def _relative(self, project: ProjectInfo, path: Path) -> str:
        try:
            return path.relative_to(project.path).as_posix()
        except ValueError:
            return path.name

    def _sha256(self, path: Path) -> str:
        digest = hashlib.sha256()
        with path.open("rb") as file:
            for chunk in iter(lambda: file.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _atomic_json(self, path: Path, data: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(f"{path.name}.tmp")
        with tmp.open("w", encoding="utf-8") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)

    def _safe_error(self, exc: Exception) -> str:
        text = str(exc).strip()
        return text[:500] if text else exc.__class__.__name__

    def _now(self) -> str:
        return datetime.now().isoformat(timespec="seconds")
