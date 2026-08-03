from __future__ import annotations

from pathlib import Path


def test_tiktok_upload_ui_handler_does_not_call_video_generation() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    start = source.index("    def _start_tiktok_upload")
    end = source.index("    def check_tiktok_status", start)
    handler_source = source[start:end]

    assert "render_project" not in handler_source
    assert "render_video" not in handler_source


def test_tiktok_thread_quits_before_success_dialog_handler() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    quit_index = source.index("worker.finished.connect(self.tiktok_thread.quit)")
    ui_index = source.index("worker.finished.connect(self.on_tiktok_connect_finished)")

    assert quit_index < ui_index
    assert "self.tiktok_thread = None" in source


def test_tiktok_ui_does_not_expose_direct_post_or_open_tiktok_button() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")

    assert "Open TikTok" not in source
    assert "Direct Post" not in source
