from __future__ import annotations

from video_editors.base import VideoEditor
from video_editors.ffmpeg_editor import FFmpegEditor
from video_editors.future_editor import FutureEditor
from video_editors.video_use_editor import VideoUseEditor


def create_video_editor(engine_name: str, ffmpeg_path: str = "ffmpeg") -> VideoEditor:
    """設定名から動画編集エンジンを生成します。"""
    normalized = engine_name.strip().lower()
    if normalized == "ffmpeg":
        return FFmpegEditor(ffmpeg_path=ffmpeg_path)
    if normalized in {"video-use", "videouse"}:
        return VideoUseEditor()
    if normalized == "future":
        return FutureEditor()
    return FFmpegEditor(ffmpeg_path=ffmpeg_path)
