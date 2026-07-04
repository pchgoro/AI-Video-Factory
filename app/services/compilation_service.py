from __future__ import annotations

import json
import re
import shutil
import subprocess
import unicodedata
from dataclasses import dataclass
from pathlib import Path

from models import ProjectInfo
from video_editors.base import VideoEditResult


@dataclass(frozen=True)
class CompilationChapter:
    start: float
    title: str


class CompilationService:
    """Create branded and compilation videos from existing media with FFmpeg."""

    ASSET_EXTENSIONS = {".mp4", ".png", ".jpg", ".jpeg"}
    VIDEO_EXTENSIONS = {".mp4"}
    IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg"}

    def __init__(self, ffmpeg_path: str = "ffmpeg", width: int = 1080, height: int = 1920, fps: int = 30) -> None:
        self.ffmpeg_path = ffmpeg_path
        self.width = width
        self.height = height
        self.fps = fps

    def first_asset(self, folder: Path) -> Path | None:
        if not folder.exists():
            return None
        return next(
            (path for path in sorted(folder.iterdir()) if path.is_file() and path.suffix.lower() in self.ASSET_EXTENSIONS),
            None,
        )

    def concat(
        self,
        media_paths: list[Path],
        output_path: Path,
        chapter_path: Path | None = None,
        chapters: list[CompilationChapter] | None = None,
    ) -> VideoEditResult:
        valid_paths = [path for path in media_paths if path.exists() and path.suffix.lower() in self.ASSET_EXTENSIONS]
        if not valid_paths:
            return VideoEditResult(False, "結合する動画がありません。")
        if shutil.which(self.ffmpeg_path) is None and not Path(self.ffmpeg_path).exists():
            return VideoEditResult(False, "FFmpegが見つかりません。設定画面でFFmpeg pathを確認してください。")

        output_path.parent.mkdir(parents=True, exist_ok=True)
        command = [self.ffmpeg_path, "-y", "-nostdin"]
        filter_parts: list[str] = []
        concat_inputs: list[str] = []

        for index, path in enumerate(valid_paths):
            duration = self.media_duration(path)
            is_image = path.suffix.lower() in self.IMAGE_EXTENSIONS
            if is_image:
                duration = duration or 3.0
                command.extend(["-loop", "1", "-t", f"{duration:.3f}", "-i", str(path)])
            else:
                command.extend(["-i", str(path)])

            filter_parts.append(
                f"[{index}:v]scale={self.width}:{self.height}:force_original_aspect_ratio=increase,"
                f"crop={self.width}:{self.height},setsar=1,fps={self.fps},format=yuv420p[v{index}]"
            )
            if self.has_audio(path):
                filter_parts.append(f"[{index}:a]aformat=sample_rates=48000:channel_layouts=stereo[a{index}]")
            else:
                safe_duration = duration or 3.0
                filter_parts.append(
                    f"anullsrc=channel_layout=stereo:sample_rate=48000,"
                    f"atrim=duration={safe_duration:.3f},asetpts=PTS-STARTPTS[a{index}]"
                )
            concat_inputs.append(f"[v{index}][a{index}]")

        filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(valid_paths)}:v=1:a=1[vout][aout]")
        command.extend(
            [
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                "[vout]",
                "-map",
                "[aout]",
                "-r",
                str(self.fps),
                "-pix_fmt",
                "yuv420p",
                str(output_path),
            ]
        )

        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            return VideoEditResult(False, f"FFmpegで動画結合に失敗しました。\n{detail}", command=command)

        if chapter_path is not None and chapters is not None:
            self.write_chapters(chapter_path, chapters)
        return VideoEditResult(True, f"{output_path.name} を生成しました。", output_path, command)

    def create_series_compilation(
        self,
        projects: list[ProjectInfo],
        output_dir: Path,
        intro_path: Path | None = None,
        ending_path: Path | None = None,
    ) -> VideoEditResult:
        selected_projects = [project for project in projects if (project.path / "video" / "final.mp4").exists()]
        if not selected_projects:
            return VideoEditResult(False, "総集編に使える完成動画がありません。")

        series_name = selected_projects[0].series or selected_projects[0].topic or selected_projects[0].name
        output_path = output_dir / f"{self.slugify(series_name)}_complete.mp4"
        chapter_path = output_dir / "chapter.txt"

        media_paths: list[Path] = []
        chapters: list[CompilationChapter] = []
        current_time = 0.0
        if intro_path is not None and intro_path.exists():
            media_paths.append(intro_path)
            current_time += self.media_duration(intro_path) or 3.0

        for project in selected_projects:
            video_path = project.path / "video" / "final.mp4"
            media_paths.append(video_path)
            chapters.append(CompilationChapter(current_time, project.title or project.topic or project.name))
            current_time += self.media_duration(video_path) or self._duration_from_project(project)

        if ending_path is not None and ending_path.exists():
            media_paths.append(ending_path)

        return self.concat(media_paths, output_path, chapter_path, chapters)

    def write_chapters(self, chapter_path: Path, chapters: list[CompilationChapter]) -> None:
        chapter_path.parent.mkdir(parents=True, exist_ok=True)
        lines = [f"{self.format_timestamp(chapter.start)} {chapter.title}".rstrip() for chapter in chapters]
        chapter_path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")

    def media_duration(self, path: Path) -> float | None:
        ffprobe = self._ffprobe_path()
        if shutil.which(ffprobe) is None and not Path(ffprobe).exists():
            return None
        command = [ffprobe, "-v", "error", "-show_entries", "format=duration", "-of", "json", str(path)]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if completed.returncode != 0:
            return None
        try:
            return float(json.loads(completed.stdout)["format"]["duration"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def has_audio(self, path: Path) -> bool:
        if path.suffix.lower() in self.IMAGE_EXTENSIONS:
            return False
        ffprobe = self._ffprobe_path()
        if shutil.which(ffprobe) is None and not Path(ffprobe).exists():
            return True
        command = [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "a",
            "-show_entries",
            "stream=index",
            "-of",
            "json",
            str(path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if completed.returncode != 0:
            return True
        try:
            return bool(json.loads(completed.stdout).get("streams"))
        except json.JSONDecodeError:
            return True

    def format_timestamp(self, seconds: float) -> str:
        total_seconds = max(0, int(seconds))
        minutes, second = divmod(total_seconds, 60)
        hour, minute = divmod(minutes, 60)
        if hour:
            return f"{hour:02d}:{minute:02d}:{second:02d}"
        return f"{minute:02d}:{second:02d}"

    def slugify(self, text: str) -> str:
        normalized = unicodedata.normalize("NFKC", text).strip().lower()
        ascii_slug = normalized.encode("ascii", "ignore").decode("ascii")
        slug = re.sub(r"[^a-z0-9]+", "_", ascii_slug).strip("_")
        if slug:
            return slug[:60]
        compact = re.sub(r"\s+", "", normalized)
        safe = re.sub(r'[<>:"/\\|?*]+', "", compact)
        return (safe or "series")[:40]

    def _ffprobe_path(self) -> str:
        candidate = Path(self.ffmpeg_path)
        if candidate.name.lower().startswith("ffmpeg"):
            ffprobe = candidate.with_name("ffprobe.exe")
            if ffprobe.exists():
                return str(ffprobe)
        return "ffprobe"

    def _duration_from_project(self, project: ProjectInfo) -> float:
        digits = re.findall(r"\d+", project.duration or "")
        if not digits:
            return 60.0
        value = float(digits[0])
        if "分" in project.duration:
            return value * 60.0
        return value
