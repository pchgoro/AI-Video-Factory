from __future__ import annotations

import json

import pytest

from config import AppPaths
from services.project_service import ProjectService
from services.story_composer import StoryService, StoryValidationError


def _payload(title: str = "ブラックホールとは？") -> dict:
    return {
        "title": title,
        "description": "ブラックホール解説",
        "hook": "ブラックホールは穴なのでしょうか。",
        "summary": "重力と光の関係を説明する",
        "estimated_duration": 18.0,
        "tags": ["宇宙", "#ブラックホール"],
        "memo": "Story memo",
        "scenes": [
            {"scene_index": 1, "start_time": 0, "end_time": 6, "duration": 6, "scene_type": "hook", "narration": "ブラックホールは本当に穴なのでしょうか。", "subtitle": "本当に穴なの？", "image_prompt": "black hole hook", "notes": "note1"},
            {"scene_index": 2, "start_time": 6, "end_time": 12, "duration": 6, "scene_type": "fact", "narration": "強い重力で光も逃げられません。", "subtitle": "光も逃げられない", "image_prompt": "gravitational lensing", "notes": ""},
            {"scene_index": 3, "start_time": 12, "end_time": 18, "duration": 6, "scene_type": "ending", "narration": "宇宙最大級の謎です。", "subtitle": "宇宙最大級の謎", "image_prompt": "ending deep space", "notes": "note3"},
        ],
    }


def _service_project(tmp_path):
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("ブラックホール", "宇宙", "60秒", 3, "prompt")
    return StoryService(project_service), project_service, project


def test_export_preview_writes_no_factory_files(tmp_path) -> None:
    service, _project_service, project = _service_project(tmp_path)
    service.import_story_json(project, json.dumps(_payload(), ensure_ascii=False))
    before = (project.path / "title.txt").read_text(encoding="utf-8")

    preview = service.export_preview(project)

    assert preview.title == "ブラックホールとは？"
    assert preview.subtitle_count == 3
    assert (project.path / "title.txt").read_text(encoding="utf-8") == before


def test_export_blocks_validation_errors(tmp_path) -> None:
    service, _project_service, project = _service_project(tmp_path)
    bad = _payload()
    bad["scenes"][0]["narration"] = ""
    service.import_story_json(project, json.dumps(bad, ensure_ascii=False))

    with pytest.raises(StoryValidationError):
        service.export_to_factory(project)


def test_successful_export_writes_expected_factory_files_and_metadata(tmp_path) -> None:
    service, project_service, project = _service_project(tmp_path)
    (project.path / "title.txt").write_text("old title\n", encoding="utf-8")
    service.import_story_json(project, json.dumps(_payload(), ensure_ascii=False))

    result = service.export_to_factory(project)
    reloaded = project_service.load_project(project.path)
    subtitles = json.loads((project.path / "subtitles.txt").read_text(encoding="utf-8"))

    assert (project.path / "title.txt").read_text(encoding="utf-8").strip() == "ブラックホールとは？"
    assert "強い重力で光も逃げられません。" in (project.path / "voice.txt").read_text(encoding="utf-8")
    assert (project.path / "image_prompts.txt").read_text(encoding="utf-8").splitlines()[0] == "black hole hook"
    assert subtitles[0] == {"start": 0.0, "end": 6.0, "text": "本当に穴なの？"}
    assert (project.path / "hashtags.txt").read_text(encoding="utf-8").strip() == "#宇宙 #ブラックホール"
    assert result.backup_dir.exists()
    assert (result.backup_dir / "title.txt").read_text(encoding="utf-8") == "old title\n"
    assert reloaded.content_source == "story_composer"
    assert reloaded.content_exported_at
    assert reloaded.youtube_upload == {}
    assert reloaded.tiktok_upload == {}


def test_partial_export_failure_restores_previous_files(tmp_path, monkeypatch) -> None:
    service, _project_service, project = _service_project(tmp_path)
    service.import_story_json(project, json.dumps(_payload(), ensure_ascii=False))
    (project.path / "title.txt").write_text("old title\n", encoding="utf-8")

    original_atomic = service.adapter._atomic_write

    def fail_on_script(path, text):
        if path.name == "script.txt":
            raise OSError("disk full")
        original_atomic(path, text)

    monkeypatch.setattr(service.adapter, "_atomic_write", fail_on_script)

    with pytest.raises(OSError):
        service.export_to_factory(project)

    assert (project.path / "title.txt").read_text(encoding="utf-8") == "old title\n"
    assert "content_source" not in json.loads((project.path / "project.json").read_text(encoding="utf-8"))
