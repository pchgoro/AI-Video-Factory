from __future__ import annotations

from pathlib import Path


def test_upload_ui_handler_does_not_call_video_generation() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    start = source.index("    def _start_youtube_upload")
    end = source.index("    def on_youtube_upload_progress", start)
    handler_source = source[start:end]

    assert "render_project" not in handler_source
    assert "render_video" not in handler_source


def test_upload_thread_quits_before_success_dialog_handler() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    quit_index = source.index("self.youtube_upload_worker.finished.connect(self.youtube_upload_thread.quit)")
    ui_index = source.index("self.youtube_upload_worker.finished.connect(self.on_youtube_upload_finished)")

    assert quit_index < ui_index
    assert "self.youtube_upload_thread = None" in source
