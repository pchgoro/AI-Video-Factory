from __future__ import annotations

import ctypes
import logging
import sys
import atexit

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
from services.logging_service import setup_logging
from services.project_service import ProjectService
from services.settings_service import SettingsService
from services.template_service import TemplateService
from services.topic_service import TopicService
from services.video_render_service import VideoRenderService
from services.version_service import VersionService
from services.voicevox_service import VoicevoxService
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
    logger.info("起動")
    atexit.register(lambda: logging.getLogger("ai_video_factory").info("終了"))

    project_service = ProjectService(paths)
    topic_service = TopicService(paths)
    template_service = TemplateService(paths)
    dashboard_service = DashboardService()
    version_info = VersionService(paths).load()
    video_editor = create_video_editor(settings.video_editor_engine, settings.ffmpeg_path)
    video_render_service = VideoRenderService(video_editor, settings)
    voicevox_service = VoicevoxService(settings.voicevox_url, settings.voicevox_speaker_id)

    window = MainWindow(
        paths=paths,
        settings_service=settings_service,
        project_service=project_service,
        topic_service=topic_service,
        template_service=template_service,
        dashboard_service=dashboard_service,
        video_render_service=video_render_service,
        voicevox_service=voicevox_service,
        version_info=version_info,
    )
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
