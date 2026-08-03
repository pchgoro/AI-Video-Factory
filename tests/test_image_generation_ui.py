from __future__ import annotations

from pathlib import Path


def test_image_generation_ui_handler_does_not_call_render_or_upload() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    start = source.index("    def _start_image_generation")
    end = source.index("    def on_image_generation_progress", start)
    snippet = source[start:end]

    assert "render_project" not in snippet
    assert "upload_to_youtube" not in snippet
    assert "upload_to_tiktok" not in snippet
    assert "ImageGenerationWorker" in snippet


def test_image_generation_ui_confirms_before_worker_start() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    start = source.index("    def _start_image_generation")
    end = source.index("    def on_image_generation_progress", start)
    snippet = source[start:end]

    assert "QMessageBox.question" in snippet
    assert snippet.index("QMessageBox.question") < snippet.index("ImageGenerationWorker")


def test_prompt_preview_does_not_call_provider_or_uploads() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    start = source.index("    def update_image_generation_prompt_preview")
    end = source.index("    def copy_optimized_prompt", start)
    snippet = source[start:end]

    assert "generate_image" not in snippet
    assert "render_project" not in snippet
    assert "upload_to_youtube" not in snippet
    assert "upload_to_tiktok" not in snippet
    assert "build_prompt_optimization" in snippet


def test_image_generation_ui_exposes_optimizer_controls() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")

    assert "Prompt Optimizer ON" in source
    assert "Template Mode" in source
    assert "Manual Template" in source
    assert "Resolved" in source
    assert "Detected Keywords" in source
    assert "Reload Templates" in source
    assert "Original Prompt" in source
    assert "Optimized Prompt" in source
    assert "Applied / Skipped" in source
    assert "Copy Optimized Prompt" in source
    assert "Refresh Preview" in source


def test_template_reload_and_preview_do_not_call_api_or_generate() -> None:
    source = Path("app/views/main_window.py").read_text(encoding="utf-8")
    start = source.index("    def reload_prompt_templates")
    end = source.index("    def image_generation_settings", start)
    reload_snippet = source[start:end]
    start = source.index("    def update_image_generation_prompt_preview")
    end = source.index("    def copy_optimized_prompt", start)
    preview_snippet = source[start:end]
    snippet = reload_snippet + preview_snippet

    assert "generate_image" not in snippet
    assert "_start_image_generation" not in snippet
    assert "ImageGenerationWorker" not in snippet
    assert "upload_to_youtube" not in snippet
    assert "upload_to_tiktok" not in snippet
