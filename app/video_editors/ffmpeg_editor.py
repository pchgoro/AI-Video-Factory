from __future__ import annotations

import json
import logging
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
        self.logger = logging.getLogger("ai_video_factory")

    def render(self, request: VideoEditRequest) -> VideoEditResult:
        self.logger.info("FFmpeg: 動画生成開始")
        if shutil.which(self.ffmpeg_path) is None and not Path(self.ffmpeg_path).exists():
            self.logger.warning("FFmpeg: 実行ファイルが見つかりません")
            return VideoEditResult(False, "FFmpegが見つかりません。FFmpegをインストールしてPATHを設定するか、設定画面でFFmpeg pathを指定してください。")

        images = self._find_images(request.images_dir)
        if not images:
            self.logger.warning("FFmpeg: 画像なし")
            return VideoEditResult(False, "imagesフォルダに画像がありません。001.png / 001.jpg / 001.webp のように保存してください。")

        request.video_dir.mkdir(parents=True, exist_ok=True)
        audio_file = request.audio_dir / "voice.wav"
        total_duration = self._audio_duration(audio_file) if audio_file.exists() else None
        seconds_per_image = (total_duration / len(images)) if total_duration else float(request.seconds_per_image)
        frames_per_image = max(1, math.ceil(seconds_per_image * request.fps))
        video_duration = seconds_per_image * len(images)
        output_duration = total_duration or video_duration

        input_args: list[str] = []
        filter_parts: list[str] = []
        video_labels: list[str] = []
        segment_duration = seconds_per_image
        transition_duration = self._transition_duration(request.transition_type, seconds_per_image, len(images))
        input_duration = segment_duration + (transition_duration if transition_duration else 0.0)
        for index, image in enumerate(images):
            input_args.extend(["-loop", "1", "-t", f"{input_duration:.3f}", "-i", str(image)])
            label = f"v{index}"
            video_labels.append(f"[{label}]")
            filter_parts.append(self._image_filter(index, label, request, frames_per_image, input_duration))

        command = [self.ffmpeg_path, "-y", "-nostdin", *input_args]
        next_input_index = len(images)
        overlay_input_index: int | None = None
        if request.overlay_path and request.overlay_path.exists():
            overlay_input_index = next_input_index
            next_input_index += 1
            if request.overlay_path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
                command.extend(["-loop", "1", "-t", f"{output_duration:.3f}", "-i", str(request.overlay_path)])
            else:
                command.extend(["-stream_loop", "-1", "-t", f"{output_duration:.3f}", "-i", str(request.overlay_path)])

        merged_label = self._merge_video_segments(filter_parts, video_labels, len(images), request, transition_duration, segment_duration)
        current_label = merged_label
        if overlay_input_index is not None:
            opacity = max(0.1, min(0.5, request.overlay_opacity / 100))
            filter_parts.append(
                f"[{overlay_input_index}:v]scale={request.width}:{request.height}:force_original_aspect_ratio=increase,"
                f"crop={request.width}:{request.height},format=rgba,colorchannelmixer=aa={opacity:.3f}[overlay]"
            )
            filter_parts.append(f"{current_label}[overlay]overlay=shortest=1:format=auto[voverlay]")
            current_label = "[voverlay]"

        light_filter = self._light_effect_filter(request.light_effect)
        if light_filter:
            filter_parts.append(f"{current_label}{light_filter}[vlight]")
            current_label = "[vlight]"

        if request.subtitles_path and request.subtitles_path.exists():
            subtitles_filter = self._subtitles_filter(request.subtitles_path)
            filter_parts.append(f"{current_label}{subtitles_filter},format=yuv420p[vout]")
        else:
            filter_parts.append(f"{current_label}format=yuv420p[vout]")

        voice_input_index: int | None = None
        bgm_input_index: int | None = None
        if audio_file.exists():
            voice_input_index = next_input_index
            next_input_index += 1
            command.extend(["-i", str(audio_file)])
        if request.bgm_path and request.bgm_path.exists():
            bgm_input_index = next_input_index
            next_input_index += 1
            command.extend(["-stream_loop", "-1", "-t", f"{output_duration:.3f}", "-i", str(request.bgm_path)])

        audio_output = self._build_audio_filter(
            filter_parts=filter_parts,
            voice_input_index=voice_input_index,
            bgm_input_index=bgm_input_index,
            duration=output_duration,
            bgm_volume=request.bgm_volume,
            voice_volume=request.voice_volume,
        )
        command.extend(["-filter_complex", ";".join(filter_parts), "-map", "[vout]"])
        if audio_output:
            command.extend(["-map", audio_output, "-shortest"])
        command.extend(["-t", f"{output_duration:.3f}", "-r", str(request.fps), "-pix_fmt", "yuv420p", str(request.output_path)])

        try:
            completed = subprocess.run(command, capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
        except OSError as exc:
            self.logger.error("FFmpeg実行エラー: %s", exc)
            return VideoEditResult(False, f"FFmpegの実行に失敗しました: {exc}", command=command)

        if completed.returncode != 0:
            detail = completed.stderr.strip() or completed.stdout.strip()
            self.logger.error("FFmpeg生成失敗: %s", detail)
            if request.subtitles_path and "subtitles" in detail.lower():
                return VideoEditResult(
                    False,
                    "FFmpegで字幕焼き込みに失敗しました。フォントが見つからない可能性があります。\n" + detail,
                    command=command,
                )
            return VideoEditResult(False, f"FFmpegで動画生成に失敗しました。\n{detail}", command=command)

        self.logger.info("FFmpeg: %s を生成", request.output_path)
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

    def _image_filter(self, index: int, label: str, request: VideoEditRequest, frames_per_image: int, duration: float) -> str:
        base = f"[{index}:v]scale={request.width}:{request.height}:force_original_aspect_ratio=increase,crop={request.width}:{request.height}"
        motion = request.image_motions[index] if index < len(request.image_motions) else "Static"
        output_frames = max(frames_per_image, math.ceil(duration * request.fps))
        if not request.zoom_enabled or motion == "Static":
            return f"{base},setsar=1,fps={request.fps},trim=duration={duration:.3f},setpts=PTS-STARTPTS[{label}]"

        strength = self._motion_strength(request.zoom_speed)
        motion_frames = output_frames
        zoom_in = f"1.0+{strength:.4f}*on/{motion_frames}"
        zoom_out = f"1.0+{strength:.4f}-{strength:.4f}*on/{motion_frames}"
        pan_zoom = "1.12"
        center_x = "iw/2-(iw/zoom/2)"
        center_y = "ih/2-(ih/zoom/2)"
        x_expr = center_x
        y_expr = center_y
        z_expr = zoom_in
        if motion == "Slow Zoom Out":
            z_expr = zoom_out
        elif motion == "Pan Left":
            z_expr = pan_zoom
            x_expr = f"(iw-iw/zoom)*on/{motion_frames}"
        elif motion == "Pan Right":
            z_expr = pan_zoom
            x_expr = f"(iw-iw/zoom)*(1-on/{motion_frames})"
        elif motion == "Pan Up":
            z_expr = pan_zoom
            y_expr = f"(ih-ih/zoom)*on/{motion_frames}"
        elif motion == "Pan Down":
            z_expr = pan_zoom
            y_expr = f"(ih-ih/zoom)*(1-on/{motion_frames})"
        elif motion == "Ken Burns":
            z_expr = f"1.0+{strength:.4f}*on/{motion_frames}"
            x_expr = f"(iw-iw/zoom)*on/{motion_frames}"
            y_expr = f"(ih-ih/zoom)*(1-on/{motion_frames})"

        return (
            f"{base},setsar=1,"
            f"zoompan=z='{z_expr}':"
            f"x='{x_expr}':y='{y_expr}':"
            f"d={output_frames}:s={request.width}x{request.height}:fps={request.fps},"
            f"trim=duration={duration:.3f},setpts=PTS-STARTPTS[{label}]"
        )

    def _merge_video_segments(
        self,
        filter_parts: list[str],
        video_labels: list[str],
        image_count: int,
        request: VideoEditRequest,
        transition_duration: float,
        segment_duration: float,
    ) -> str:
        if transition_duration <= 0 or image_count <= 1:
            concat_inputs = "".join(video_labels)
            filter_parts.append(f"{concat_inputs}concat=n={image_count}:v=1:a=0,format=yuv420p[vmerged]")
            return "[vmerged]"

        transition = self._xfade_transition(request.transition_type)
        current = video_labels[0]
        for index in range(1, image_count):
            output = f"[vx{index}]"
            offset = max(0.0, segment_duration * index)
            filter_parts.append(
                f"{current}{video_labels[index]}xfade=transition={transition}:duration={transition_duration:.3f}:"
                f"offset={offset:.3f},format=yuv420p{output}"
            )
            current = output
        filter_parts.append(f"{current}trim=duration={segment_duration * image_count:.3f},setpts=PTS-STARTPTS[vmerged]")
        return "[vmerged]"

    def _transition_duration(self, transition_type: str, seconds_per_image: float, image_count: int) -> float:
        if image_count <= 1 or transition_type == "None":
            return 0.0
        return min(0.75, max(0.25, seconds_per_image * 0.18))

    def _xfade_transition(self, transition_type: str) -> str:
        if transition_type == "Fade":
            return "fadeblack"
        if transition_type == "Slide":
            return "slideleft"
        return "fade"

    def _motion_strength(self, zoom_speed: str) -> float:
        if zoom_speed == "Slow":
            return 0.08
        if zoom_speed == "Fast":
            return 0.22
        return 0.15

    def _light_effect_filter(self, light_effect: str) -> str:
        if light_effect == "Lens Flare":
            return "drawbox=x=0:y=0:w=iw:h=ih:color=white@0.035:t=fill,drawbox=x=iw*0.60:y=ih*0.18:w=260:h=10:color=white@0.22:t=fill"
        if light_effect == "Glow":
            return "eq=brightness=0.04:saturation=1.08,unsharp=5:5:0.5"
        if light_effect == "Soft Light":
            return "eq=brightness=0.03:contrast=1.03:saturation=1.05"
        return ""

    def _build_audio_filter(
        self,
        filter_parts: list[str],
        voice_input_index: int | None,
        bgm_input_index: int | None,
        duration: float,
        bgm_volume: float,
        voice_volume: float,
    ) -> str | None:
        if voice_input_index is None and bgm_input_index is None:
            return None

        fade_out_start = max(0.0, duration - 1.0)
        safe_bgm_volume = max(0.0, min(1.0, bgm_volume))
        safe_voice_volume = max(0.0, min(1.0, voice_volume))

        if voice_input_index is not None:
            filter_parts.append(f"[{voice_input_index}:a]volume={safe_voice_volume:.3f}[voice]")

        if bgm_input_index is not None:
            filter_parts.append(
                f"[{bgm_input_index}:a]"
                f"volume={safe_bgm_volume:.3f},"
                "afade=t=in:st=0:d=0.5,"
                f"afade=t=out:st={fade_out_start:.3f}:d=1.0,"
                f"atrim=duration={duration:.3f},asetpts=PTS-STARTPTS[bgm]"
            )

        if voice_input_index is not None and bgm_input_index is not None:
            filter_parts.append("[voice][bgm]amix=inputs=2:duration=first:dropout_transition=0[aout]")
            return "[aout]"
        if voice_input_index is not None:
            return "[voice]"
        return "[bgm]"

    def _subtitles_filter(self, subtitles_path: Path) -> str:
        escaped = subtitles_path.resolve().as_posix().replace(":", r"\:")
        escaped = escaped.replace("'", r"\'")
        return f"subtitles='{escaped}'"
