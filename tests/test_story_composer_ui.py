from __future__ import annotations

from pathlib import Path


def _method_source(source: str, name: str) -> str:
    start = source.index(f"    def {name}")
    try:
        end = source.index("\n    def ", start + 1)
    except ValueError:
        end = len(source)
    return source[start:end]


def test_story_composer_is_separate_widget_and_main_window_only_connects_it() -> None:
    widget_source = Path("app/views/story_composer_widget.py").read_text(encoding="utf-8")
    main_source = Path("app/views/main_window.py").read_text(encoding="utf-8")

    assert "class StoryComposerWidget" in widget_source
    assert "StoryComposerWidget" in main_source
    assert "story_composer_widget.exported.connect" in main_source
    assert "def import_story_json" not in main_source
    assert "class StoryComposerWidget" not in main_source


def test_story_composer_buttons_exist() -> None:
    source = Path("app/views/story_composer_widget.py").read_text(encoding="utf-8")

    for label in [
        "Generate Prompt",
        "Copy Prompt",
        "Import Story JSON",
        "Validate",
        "Save",
        "Resume",
        "Reset",
        "Export Preview",
        "Export to Factory",
    ]:
        assert label in source


def test_generate_import_validate_resume_preview_do_not_call_external_workflows() -> None:
    source = Path("app/views/story_composer_widget.py").read_text(encoding="utf-8")
    snippets = "\n".join(
        _method_source(source, name)
        for name in [
            "generate_prompt",
            "import_story_json",
            "validate_story",
            "resume_story",
            "show_export_preview",
        ]
    )

    forbidden = [
        "generate_missing_images",
        "synthesize_project",
        "render_project",
        "upload_to_youtube",
        "upload_to_tiktok",
        "requests.",
        "urllib.request",
        "OpenAI",
        "Cloudflare",
    ]
    for text in forbidden:
        assert text not in snippets


def test_export_preview_writes_no_files_and_export_is_explicit() -> None:
    source = Path("app/views/story_composer_widget.py").read_text(encoding="utf-8")
    preview = _method_source(source, "show_export_preview")
    export = _method_source(source, "export_to_factory")

    assert "export_preview" in preview
    assert "export_to_factory" not in preview
    assert "export_to_factory" in export
    assert "QMessageBox.question" in export


def test_reset_requires_confirmation_and_does_not_name_factory_assets_for_delete() -> None:
    source = Path("app/views/story_composer_widget.py").read_text(encoding="utf-8")
    reset = _method_source(source, "reset_story")

    assert "QMessageBox.question" in reset
    assert "story_service.reset" in reset
    assert "final.mp4" in reset
    assert "title.txt" in reset
