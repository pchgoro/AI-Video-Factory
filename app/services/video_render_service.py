from __future__ import annotations

from pathlib import Path

from models import AppSettings, ProjectInfo
from services.subtitle_service import SubtitleError, SubtitleService
from video_editors.base import VideoEditRequest, VideoEditResult, VideoEditor


class VideoRenderService:
    """アプリ本体と動画編集エンジンの間に置く薄いサービスです。"""

    def __init__(self, editor: VideoEditor, settings: AppSettings) -> None:
        self.editor = editor
        self.settings = settings
        self.subtitle_service = SubtitleService()

    def render_project(self, project: ProjectInfo) -> VideoEditResult:
        bgm_path = self._find_bgm_file(self._bgm_dir_for_project(project.path))
        subtitles_path = None
        if self.settings.subtitles_enabled or self.settings.title_enabled:
            try:
                subtitles_path = self.subtitle_service.generate_for_project(project.path, self.settings)
            except SubtitleError as exc:
                return VideoEditResult(False, str(exc))
        request = VideoEditRequest(
            project_dir=project.path,
            images_dir=project.path / "images",
            audio_dir=project.path / "audio",
            video_dir=project.path / "video",
            output_path=project.path / "video" / "final.mp4",
            width=self.settings.output_width,
            height=self.settings.output_height,
            seconds_per_image=self.settings.seconds_per_image,
            zoom_enabled=self.settings.zoom_enabled,
            bgm_path=bgm_path,
            bgm_volume=max(0.0, min(1.0, self.settings.bgm_volume_percent / 100)),
            subtitles_path=subtitles_path,
        )
        return self.editor.render(request)

    def _find_bgm_file(self, bgm_dir: Path) -> Path | None:
        if not self.settings.bgm_enabled or not bgm_dir.exists():
            return None
        extensions = {".mp3", ".wav"}
        return next((path for path in sorted(bgm_dir.iterdir()) if path.is_file() and path.suffix.lower() in extensions), None)

    def _bgm_dir_for_project(self, project_dir: Path) -> Path:
        if project_dir.parent.name == "projects":
            return project_dir.parent.parent / "assets" / "bgm"
        return project_dir.parent / "assets" / "bgm"
