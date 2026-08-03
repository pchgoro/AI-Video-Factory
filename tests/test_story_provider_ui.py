from __future__ import annotations

from pathlib import Path


def _method_source(source: str, name: str) -> str:
    start = source.index(f"    def {name}")
    try:
        end = source.index("\n    def ", start + 1)
    except ValueError:
        end = len(source)
    return source[start:end]


def test_story_provider_ui_has_minimal_ai_controls() -> None:
    source = Path("app/views/story_composer_widget.py").read_text(encoding="utf-8")

    for text in [
        "Story AI Provider",
        "Generate Story",
        "Cancel Generation",
        "Retry Generation",
        "Resume Generation",
        "Preview Generated Story",
        "Use Generated Story",
        "gpt-5.6-luna",
        "Gemini",
        "Free-tier-only",
        "Project Tier Free confirmed",
        "Billing disabled confirmed",
    ]:
        assert text in source


def test_story_provider_ui_runs_generation_in_qthread_and_blocks_double_click() -> None:
    source = Path("app/views/story_composer_widget.py").read_text(encoding="utf-8")
    start_generation = _method_source(source, "_start_generation")

    assert "QThread" in source
    assert "self._generation_thread is not None" in start_generation
    assert "moveToThread" in start_generation
    assert "_set_generation_active(True)" in start_generation


def test_story_provider_ui_does_not_auto_export_or_start_production() -> None:
    source = Path("app/views/story_composer_widget.py").read_text(encoding="utf-8")
    generation_methods = "\n".join(
        _method_source(source, name)
        for name in [
            "generate_story_ai",
            "_start_generation",
            "_on_generation_finished",
            "preview_generated_story",
            "use_generated_story",
        ]
    )

    assert "export_to_factory(" not in generation_methods
    assert "ProductionOrchestrator" not in generation_methods
    assert "generate_missing_images" not in generation_methods
    assert "synthesize_project" not in generation_methods
    assert "render_project" not in generation_methods
    assert "upload_to_youtube" not in generation_methods
    assert "upload_to_tiktok" not in generation_methods


def test_settings_do_not_store_openai_api_key() -> None:
    settings_source = Path("app/services/settings_service.py").read_text(encoding="utf-8")
    models_source = Path("app/models.py").read_text(encoding="utf-8")

    assert "OPENAI_API_KEY" not in settings_source
    assert "openai_api_key" not in settings_source.lower()
    assert "openai_api_key" not in models_source.lower()
    assert "GEMINI_API_KEY" not in settings_source
    assert "gemini_api_key" not in settings_source.lower()
    assert "gemini_api_key" not in models_source.lower()
