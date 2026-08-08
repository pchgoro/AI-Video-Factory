from __future__ import annotations

import ctypes
import logging
import sys
import atexit
from pathlib import Path

try:
    from PySide6.QtWidgets import QApplication
except ModuleNotFoundError:
    message = (
        "PySide6がインストールされていません。\n\n"
        "PowerShellで次のコマンドを実行してください。\n"
        "python -m pip install -r requirements.txt"
    )
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "AI Video Factory", 0x10)
    except Exception:
        print(message)
    raise SystemExit(1)

from config import AppPaths
from services.dashboard_service import DashboardService
from services.job_service import JobService
from services.image_generation import CloudflareWorkersAIProvider, ImageGenerationService, PromptLibraryService
from services.image_generation.usage_service import ImageGenerationUsageService
from services.logging_service import (
    setup_image_generation_logging,
    setup_logging,
    setup_production_logging,
    setup_story_provider_logging,
    setup_tiktok_logging,
    setup_youtube_logging,
)
from services.project_service import ProjectService
from services.quality_check_service import QualityCheckService
from services.production_orchestrator import ArtifactService, ProductionOrchestratorService, ProductionPreflightService
from services.production_orchestrator.steps import (
    ExportStoryStep,
    GenerateImagesStep,
    GenerateSubtitlesStep,
    GenerateVoiceStep,
    RenderVideoStep,
    UploadTikTokStep,
    UploadYouTubeStep,
    ValidateStoryStep,
)
from services.settings_service import SettingsService
from services.story_composer import StoryService
from services.story_provider import GeminiStoryProvider, GeminiUsageStore, MockStoryProvider, OpenAIStoryProvider, StoryProviderManager
from services.story_provider.manager import ManualPromptProviderAdapter
from services.subtitle_service import SubtitleService
from services.template_service import TemplateService
from services.topic_service import TopicService
from services.video_render_service import VideoRenderService
from services.version_service import VersionService
from services.voicevox_service import VoicevoxService
from services.youtube.oauth_service import YouTubeOAuthService
from services.youtube.upload_service import YouTubeUploadService
from services.tiktok.api_client import TikTokApiClient
from services.tiktok.oauth_service import TikTokOAuthService
from services.tiktok.status_service import TikTokStatusService
from services.tiktok.upload_service import TikTokUploadService
from services.tiktok.video_validator import TikTokVideoValidator
from video_editors.factory import create_video_editor
from views.main_window import MainWindow


def main() -> int:
    """AI Video Factoryのエントリーポイントです。"""
    app = QApplication(sys.argv)
    app.setApplicationName("AI Video Factory")

    paths = AppPaths.from_app_file(__file__)
    settings_service = SettingsService(paths)
    settings = settings_service.load()
    paths.update_base_dir(settings.save_dir)
    paths.ensure()
    logger = setup_logging(paths)
    youtube_logger = setup_youtube_logging(paths)
    tiktok_logger = setup_tiktok_logging(paths)
    image_generation_logger = setup_image_generation_logging(paths)
    production_logger = setup_production_logging(paths)
    story_provider_logger = setup_story_provider_logging(paths)
    logger.info("起動")
    atexit.register(lambda: logging.getLogger("ai_video_factory").info("終了"))

    project_service = ProjectService(paths)
    image_generation_provider = CloudflareWorkersAIProvider(logger=image_generation_logger)
    image_generation_usage_service = ImageGenerationUsageService(paths.base_dir / "image_generation_usage.json")
    prompt_library_service = PromptLibraryService(paths.prompt_library_dir, logger=image_generation_logger)
    image_generation_service = ImageGenerationService(
        project_service,
        image_generation_provider,
        image_generation_usage_service,
        prompt_library_service,
        logger=image_generation_logger,
    )
    story_service = StoryService(project_service, logger=story_provider_logger)
    quality_check_service = QualityCheckService(settings, story_service)
    story_service.provider_manager = StoryProviderManager(
        [
            ManualPromptProviderAdapter(story_service.provider),
            GeminiStoryProvider(
                logger=story_provider_logger,
                usage_store=GeminiUsageStore(paths.base_dir / "gemini_story_usage.json"),
            ),
            MockStoryProvider(),
            OpenAIStoryProvider(logger=story_provider_logger),
        ],
        default_provider=settings.default_story_provider,
    )
    job_service = JobService(project_service)
    youtube_oauth_service = YouTubeOAuthService(paths.base_dir, logger=youtube_logger)
    youtube_upload_service = YouTubeUploadService(project_service, job_service, youtube_oauth_service, logger=youtube_logger, settings=settings)
    tiktok_api_client = TikTokApiClient()
    tiktok_oauth_service = TikTokOAuthService(paths.base_dir, logger=tiktok_logger)
    tiktok_status_service = TikTokStatusService(project_service, tiktok_oauth_service, tiktok_api_client, logger=tiktok_logger)
    tiktok_upload_service = TikTokUploadService(
        project_service,
        tiktok_oauth_service,
        tiktok_status_service,
        tiktok_api_client,
        TikTokVideoValidator(_ffprobe_path(settings.ffmpeg_path)),
        logger=tiktok_logger,
    )
    topic_service = TopicService(paths)
    template_service = TemplateService(paths)
    dashboard_service = DashboardService()
    version_info = VersionService(paths).load()
    video_editor = create_video_editor(settings.video_editor_engine, settings.ffmpeg_path)
    video_render_service = VideoRenderService(video_editor, settings)
    voicevox_service = VoicevoxService(settings.voicevox_url, settings.voicevox_speaker_id)
    artifact_service = ArtifactService(settings)
    production_preflight_service = ProductionPreflightService(story_service, image_generation_service, artifact_service)
    production_orchestrator_service = ProductionOrchestratorService(
        project_service=project_service,
        settings=settings,
        preflight_service=production_preflight_service,
        adapters={
            "validate_story": ValidateStoryStep(story_service),
            "export_story": ExportStoryStep(story_service),
            "generate_images": GenerateImagesStep(image_generation_service),
            "generate_voice": GenerateVoiceStep(voicevox_service),
            "generate_subtitles": GenerateSubtitlesStep(SubtitleService()),
            "render_video": RenderVideoStep(video_render_service),
            "upload_youtube": UploadYouTubeStep(youtube_upload_service),
            "upload_tiktok": UploadTikTokStep(tiktok_upload_service),
        },
        artifact_service=artifact_service,
        logger=production_logger,
    )

    window = MainWindow(
        paths=paths,
        settings_service=settings_service,
        project_service=project_service,
        image_generation_service=image_generation_service,
        story_service=story_service,
        job_service=job_service,
        youtube_upload_service=youtube_upload_service,
        tiktok_oauth_service=tiktok_oauth_service,
        tiktok_upload_service=tiktok_upload_service,
        topic_service=topic_service,
        template_service=template_service,
        dashboard_service=dashboard_service,
        video_render_service=video_render_service,
        voicevox_service=voicevox_service,
        production_orchestrator_service=production_orchestrator_service,
        quality_check_service=quality_check_service,
        version_info=version_info,
    )
    window.show()
    return app.exec()


def _ffprobe_path(ffmpeg_path: str) -> str:
    if not ffmpeg_path or ffmpeg_path == "ffmpeg":
        return "ffprobe"
    path = Path(ffmpeg_path)
    if path.name.lower().startswith("ffmpeg"):
        return str(path.with_name(path.name.replace("ffmpeg", "ffprobe", 1)))
    return "ffprobe"


if __name__ == "__main__":
    raise SystemExit(main())
