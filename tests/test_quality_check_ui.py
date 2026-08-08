from __future__ import annotations

from pathlib import Path


def test_quality_check_tab_is_registered() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")

    assert "_build_quality_check_tab" in source
    assert '"Quality Check"' in source
    assert "run_quality_check" in source


def test_upload_handlers_run_quality_gate_before_workers() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    youtube_start = source.index("    def _start_youtube_upload")
    youtube_end = source.index("    def on_youtube_upload_progress", youtube_start)
    youtube_handler = source[youtube_start:youtube_end]
    tiktok_start = source.index("    def _start_tiktok_upload")
    tiktok_end = source.index("    def check_tiktok_status", tiktok_start)
    tiktok_handler = source[tiktok_start:tiktok_end]

    assert "_quality_check_blocks_upload" in youtube_handler
    assert youtube_handler.index("_quality_check_blocks_upload") < youtube_handler.index("YouTubeUploadWorker")
    assert "_quality_check_blocks_upload" in tiktok_handler
    assert tiktok_handler.index("_quality_check_blocks_upload") < tiktok_handler.index("TikTokUploadWorker")


def test_quality_gate_does_not_call_render_or_upload_itself() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    start = source.index("    def _quality_check_blocks_upload")
    end = source.index("    def _clear_tiktok_worker", start)
    handler = source[start:end]

    assert "render_project" not in handler
    assert "YouTubeUploadWorker" not in handler
    assert "TikTokUploadWorker" not in handler
