from __future__ import annotations

from pathlib import Path


def _method_source(source: str, name: str) -> str:
    start = source.index(f"    def {name}")
    try:
        end = source.index("\n    def ", start + 1)
    except ValueError:
        end = len(source)
    return source[start:end]


def test_production_orchestrator_is_separate_widget() -> None:
    widget_source = Path("app/views/production_orchestrator_widget.py").read_text(encoding="utf-8")
    main_source = Path("app/views/main_window.py").read_text(encoding="utf-8")

    assert "class ProductionOrchestratorWidget" in widget_source
    assert "ProductionOrchestratorWidget" in main_source
    assert "production_orchestrator_widget.run_updated.connect" in main_source
    assert "class ProductionOrchestratorWidget" not in main_source
    assert "def start_run" not in main_source


def test_widget_buttons_exist_and_differentiate_dry_run() -> None:
    source = Path("app/views/production_orchestrator_widget.py").read_text(encoding="utf-8")

    for label in [
        "Run Preflight",
        "Start Dry Run",
        "Start Production",
        "Cancel",
        "Resume",
        "Retry Failed Step",
        "Open Output Folder",
        "Dry Run",
        "Normal",
    ]:
        assert label in source


def test_start_runs_in_qthread_and_blocks_double_clicks() -> None:
    source = Path("app/views/production_orchestrator_widget.py").read_text(encoding="utf-8")
    start_worker = _method_source(source, "start_worker")

    assert "QThread" in source
    assert "self.thread is not None and self.thread.isRunning()" in start_worker
    assert "moveToThread" in start_worker
    assert "_set_active(True)" in start_worker


def test_preview_and_preflight_do_not_call_generation_or_upload_directly() -> None:
    source = Path("app/views/production_orchestrator_widget.py").read_text(encoding="utf-8")
    preflight = _method_source(source, "run_preflight")

    forbidden = [
        "generate_missing(",
        "synthesize_project(",
        "generate_for_project(",
        "render_project(",
        "upload_project(",
    ]
    for text in forbidden:
        assert text not in preflight
