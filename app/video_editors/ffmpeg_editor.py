from __future__ import annotations

import json
import math
import shutil
import subprocess
from pathlib import Path

from video_editors.base import VideoEditRequest, VideoEditResult, VideoEditor


class FFmpegEditor(VideoEditor):
    """FFmpegで画像とVOICEVOX音声から縦動画を生成します。"""

    engine_name = "ffmpeg"

    def __init__(self, ffmpeg_path: str = "ffmpeg") -> None:
        self.ffmpeg_path = ffmpeg_path

    def render(self, request: VideoEditRequest) -> VideoEditResult:
        if shutil.which(self.ffmpeg_path) is None and not Path(self.ffmpeg_path).exists():
            return VideoEditResult(False, "FFmpegが見つかりません。FFmpegをインストールしてPATHを設定するか、設定画面でFFmpeg pathを指定してください。")

        images = self._find_images(request.images_dir)
        if not images:
            return VideoEditResult(False, "imagesフォルダに画像がありません。001.png / 001.jpg / 001.webp のように保存してください。")

        request.video_dir.mkdir(parents=True, exist_ok=True)
        audio_file = request.audio_dir / "voice.wav"
        total_duration = self._audio_duration(audio_file) if audio_file.exists() else None
        seconds_per_image = (total_duration / len(images)) if total_duration else float(request.seconds_per_image)
        frames_per_image = max(1, math.ceil(seconds_per_image * request.fps))

        input_args: list[str] = []
        filter_parts: list[str] = []
        video_labels: list[str] = []
        for index, image in enumerate(images):
            input_args.extend(["-loop", "1", "-t", f"{seconds_per_image:.3f}", "-i", str(image)])
            label = f"v{index}"
            video_labels.append(f"[{label}]")
            filter_parts.append(self._image_filter(index, label, request, frames_per_image))

        concat_inputs = "".join(video_labels)
        filter_parts.append(f"{concat_inputs}concat=n={len(images)}:v=1:a=0,format=yuv420p[vout]")

        command = [self.ffmpeg_path, "-y", *input_args]
        if audio_file.exists():
            command.extend(["-i", str(audio_file)])
        command.extend(["-filter_complex", ";".join(filter_parts), "-map", "[vout]"])
        if audio_file.exists():
            command.extend(["-map", f"{len(images)}:a", "-shortest"])
        command.extend(["-r", str(request.fps), "-pix_fmt", "yuv420p", str(request.output_path)])

        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        except OSError as exc:
            return VideoEditResult(False, f"FFmpegの実行に失敗しました: {exc}", command=command)

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            return VideoEditResult(False, f"FFmpegで動画生成に失敗しました。\n{detail}", command=command)

        return VideoEditResult(True, "video/final.mp4 を生成しました。", request.output_path, command)

    def _find_images(self, images_dir: Path) -> list[Path]:
        extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
        if not images_dir.exists():
            return []
        return sorted(path for path in images_dir.iterdir() if path.suffix.lower() in extensions and path.is_file())

    def _audio_duration(self, audio_file: Path) -> float | None:
        ffprobe = "ffprobe"
        if Path(self.ffmpeg_path).name.lower().startswith("ffmpeg"):
            candidate = Path(self.ffmpeg_path).with_name("ffprobe.exe")
            if candidate.exists():
                ffprobe = str(candidate)
        if shutil.which(ffprobe) is None and not Path(ffprobe).exists():
            return None
        command = [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "json",
            str(audio_file),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        if completed.returncode != 0:
            return None
        try:
            data = json.loads(completed.stdout)
            return float(data["format"]["duration"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError):
            return None

    def _image_filter(self, index: int, label: str, request: VideoEditRequest, frames_per_image: int) -> str:
        base = f"[{index}:v]scale={request.width}:{request.height}:force_original_aspect_ratio=increase,crop={request.width}:{request.height}"
        if not request.zoom_enabled:
            return f"{base},setsar=1,fps={request.fps},trim=duration={frames_per_image / request.fps:.3f},setpts=PTS-STARTPTS[{label}]"

        return (
            f"{base},setsar=1,"
            f"zoompan=z='min(zoom+0.0015,1.12)':"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
            f"d={frames_per_image}:s={request.width}x{request.height}:fps={request.fps},"
            f"trim=duration={frames_per_image / request.fps:.3f},setpts=PTS-STARTPTS[{label}]"
        )
