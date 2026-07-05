from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path


@dataclass(frozen=True)
class VideoEditRequest:
    """動画編集エンジンへ渡す共通リクエストです。"""

    project_dir: Path
    images_dir: Path
    audio_dir: Path
    video_dir: Path
    output_path: Path
    width: int = 1080
    height: int = 1920
    fps: int = 30
    seconds_per_image: int = 5
    zoom_enabled: bool = True
    bgm_path: Path | None = None
    bgm_volume: float = 0.2
    voice_volume: float = 1.0
    subtitles_path: Path | None = None
    image_motions: list[str] = field(default_factory=list)
    zoom_speed: str = "Normal"
    transition_type: str = "Cross Fade"
    overlay_path: Path | None = None
    overlay_opacity: int = 30
    light_effect: str = "OFF"


@dataclass(frozen=True)
class VideoEditResult:
    """動画編集エンジンの共通実行結果です。"""

    success: bool
    message: str
    output_path: Path | None = None
    command: list[str] | None = None


class VideoEditor(ABC):
    """FFmpeg、video-use、将来のAI編集ツールを差し替えるためのインターフェースです。"""

    engine_name: str

    @abstractmethod
    def render(self, request: VideoEditRequest) -> VideoEditResult:
        """素材フォルダから縦動画を書き出します。"""
