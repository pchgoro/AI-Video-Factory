from __future__ import annotations

from pathlib import Path

from models import AppSettings, ProjectInfo
from services.compilation_service import CompilationService
from services.subtitle_service import SubtitleError, SubtitleService
from video_editors.base import VideoEditRequest, VideoEditResult, VideoEditor


class VideoRenderService:
    """アプリ本体と動画編集エンジンの間に置く薄いサービスです。"""

    def __init__(self, editor: VideoEditor, settings: AppSettings) -> None:
        self.editor = editor
        self.settings = settings
        self.subtitle_service = SubtitleService()
        self.compilation_service = CompilationService(
            ffmpeg_path=settings.ffmpeg_path,
            width=settings.output_width,
            height=settings.output_height,
        )

    def render_project(self, project: ProjectInfo) -> VideoEditResult:
        bgm_path = self._find_bgm_file(self._bgm_dir_for_project(project.path))
        intro_path = self._find_intro_file(self._intro_dir_for_project(project.path))
        ending_path = self._find_ending_file(self._ending_dir_for_project(project.path))
        needs_branding = intro_path is not None or ending_path is not None
        output_path = project.path / "video" / "final.mp4"
        body_output_path = project.path / "video" / "final_body.mp4"
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
            output_path=body_output_path if needs_branding else output_path,
            width=self.settings.output_width,
            height=self.settings.output_height,
            seconds_per_image=self.settings.seconds_per_image,
            zoom_enabled=self.settings.zoom_enabled,
            bgm_path=bgm_path,
            bgm_volume=max(0.0, min(1.0, self.settings.bgm_volume_percent / 100)),
            subtitles_path=subtitles_path,
        )
        result = self.editor.render(request)
        if not result.success or not needs_branding:
            return result
        if not request.output_path.exists():
            return VideoEditResult(False, "本編動画の生成に失敗しました。final_body.mp4 が見つかりません。", command=result.command)
        media_paths = [path for path in [intro_path, request.output_path, ending_path] if path is not None]
        branded_result = self.compilation_service.concat(media_paths, output_path)
        if branded_result.success:
            return VideoEditResult(True, "video/final.mp4 を生成しました。", branded_result.output_path, branded_result.command)
        return branded_result

    def _find_bgm_file(self, bgm_dir: Path) -> Path | None:
        if not self.settings.bgm_enabled or not bgm_dir.exists():
            return None
        extensions = {".mp3", ".wav"}
        return next((path for path in sorted(bgm_dir.iterdir()) if path.is_file() and path.suffix.lower() in extensions), None)

    def _find_intro_file(self, intro_dir: Path) -> Path | None:
        if not self.settings.intro_enabled:
            return None
        return self.compilation_service.first_asset(intro_dir)

    def _find_ending_file(self, ending_dir: Path) -> Path | None:
        if not self.settings.ending_enabled:
            return None
        return self.compilation_service.first_asset(ending_dir)

    def _bgm_dir_for_project(self, project_dir: Path) -> Path:
        if project_dir.parent.name == "projects":
            return project_dir.parent.parent / "assets" / "bgm"
        return project_dir.parent / "assets" / "bgm"

    def _intro_dir_for_project(self, project_dir: Path) -> Path:
        if project_dir.parent.name == "projects":
            return project_dir.parent.parent / "assets" / "intro"
        return project_dir.parent / "assets" / "intro"

    def _ending_dir_for_project(self, project_dir: Path) -> Path:
        if project_dir.parent.name == "projects":
            return project_dir.parent.parent / "assets" / "ending"
        return project_dir.parent / "assets" / "ending"
