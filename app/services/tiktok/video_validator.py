from __future__ import annotations

import json
import subprocess
from pathlib import Path

from models import ProjectInfo
from services.tiktok.models import TikTokValidationError


class TikTokVideoValidator:
    MAX_SIZE_BYTES = 4 * 1024 * 1024 * 1024
    MAX_DURATION_SECONDS = 10 * 60
    MIN_DIMENSION = 360
    MAX_DIMENSION = 4096
    SUPPORTED_CODECS = {"h264", "hevc", "h265", "vp8", "vp9"}

    def __init__(self, ffprobe_path: str = "ffprobe") -> None:
        self.ffprobe_path = ffprobe_path

    def validate_final_mp4(self, project: ProjectInfo) -> Path:
        final_mp4 = project.path / "video" / "final.mp4"
        try:
            project_root = project.path.resolve()
            resolved = final_mp4.resolve()
        except OSError as exc:
            raise TikTokValidationError("TikTokアップロード対象動画のパスを確認できません。") from exc
        if project_root not in resolved.parents:
            raise TikTokValidationError("対象プロジェクト外の動画はTikTokへアップロードできません。")
        if resolved.name != "final.mp4" or resolved.suffix.lower() != ".mp4":
            raise TikTokValidationError("TikTokへアップロードできるのはfinal.mp4だけです。")
        if not resolved.exists():
            raise TikTokValidationError("final.mp4が見つかりません。動画生成後にアップロードしてください。")
        size = resolved.stat().st_size
        if size <= 0:
            raise TikTokValidationError("final.mp4のファイルサイズが0です。")
        if size > self.MAX_SIZE_BYTES:
            raise TikTokValidationError("final.mp4がTikTokのサイズ上限を超えています。")
        try:
            header = resolved.read_bytes()[:64]
        except OSError as exc:
            raise TikTokValidationError("final.mp4を読み取れません。") from exc
        if b"ftyp" not in header:
            raise TikTokValidationError("final.mp4をMP4動画として確認できません。")
        self._validate_with_ffprobe(resolved)
        return resolved

    def _validate_with_ffprobe(self, video_path: Path) -> None:
        command = [
            self.ffprobe_path,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,r_frame_rate:format=duration",
            "-of",
            "json",
            str(video_path),
        ]
        try:
            completed = subprocess.run(command, check=False, capture_output=True, text=True, encoding="utf-8", errors="replace")
        except OSError as exc:
            raise TikTokValidationError("ffprobeでfinal.mp4を確認できません。ffprobeのパスを確認してください。") from exc
        if completed.returncode != 0:
            raise TikTokValidationError("ffprobeでfinal.mp4を動画として読み取れません。")
        try:
            data = json.loads(completed.stdout or "{}")
        except json.JSONDecodeError as exc:
            raise TikTokValidationError("ffprobeの応答形式が正しくありません。") from exc
        streams = data.get("streams")
        if not isinstance(streams, list) or not streams:
            raise TikTokValidationError("final.mp4に動画ストリームがありません。")
        stream = streams[0] if isinstance(streams[0], dict) else {}
        codec = str(stream.get("codec_name") or "").lower()
        if codec and codec not in self.SUPPORTED_CODECS:
            raise TikTokValidationError("final.mp4の動画コーデックがTikTok対応形式ではありません。")
        width = int(stream.get("width") or 0)
        height = int(stream.get("height") or 0)
        if width < self.MIN_DIMENSION or height < self.MIN_DIMENSION or width > self.MAX_DIMENSION or height > self.MAX_DIMENSION:
            raise TikTokValidationError("final.mp4の解像度がTikTok対応範囲外です。")
        duration = float((data.get("format") or {}).get("duration") or 0)
        if duration <= 0:
            raise TikTokValidationError("final.mp4の動画時間を確認できません。")
        if duration > self.MAX_DURATION_SECONDS:
            raise TikTokValidationError("final.mp4がTikTokの動画時間上限を超えています。")
        fps = self._fps(stream.get("r_frame_rate"))
        if fps and (fps < 23 or fps > 60):
            raise TikTokValidationError("final.mp4のフレームレートがTikTok対応範囲外です。")

    def _fps(self, value: object) -> float:
        text = str(value or "")
        if "/" in text:
            numerator, denominator = text.split("/", 1)
            try:
                denominator_number = float(denominator)
                if denominator_number == 0:
                    return 0
                return float(numerator) / denominator_number
            except ValueError:
                return 0
        try:
            return float(text)
        except ValueError:
            return 0
