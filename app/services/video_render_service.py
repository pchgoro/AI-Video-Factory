from __future__ import annotations

from models import AppSettings, ProjectInfo
from video_editors.base import VideoEditRequest, VideoEditResult, VideoEditor


class VideoRenderService:
    """アプリ本体と動画編集エンジンの間に置く薄いサービスです。"""

    def __init__(self, editor: VideoEditor, settings: AppSettings) -> None:
        self.editor = editor
        self.settings = settings

    def render_project(self, project: ProjectInfo) -> VideoEditResult:
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
        )
        return self.editor.render(request)
