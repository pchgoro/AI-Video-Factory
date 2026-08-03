from __future__ import annotations

import json

from config import AppPaths
from services.project_service import ProjectService
from services.story_composer import StoryService


def _payload() -> dict:
    return {
        "title": "時間旅行は本当にできる？",
        "description": "時間旅行の考え方",
        "hook": "未来へ行ける乗り物があるなら？",
        "summary": "相対性理論と時間のずれを説明する",
        "estimated_duration": 18.0,
        "tags": ["宇宙", "時間旅行"],
        "memo": "派生ファイルへはExportまで反映しない",
        "scenes": [
            {"scene_index": 1, "start_time": 0, "end_time": 6, "duration": 6, "scene_type": "hook", "narration": "未来へ行けるかもしれません。", "subtitle": "未来へ行ける？", "image_prompt": "time machine in space", "notes": "hook"},
            {"scene_index": 2, "start_time": 6, "end_time": 12, "duration": 6, "scene_type": "explanation", "narration": "高速で動くと時間の進み方が変わります。", "subtitle": "時間の進み方が変わる", "image_prompt": "relativistic spacecraft", "notes": ""},
            {"scene_index": 3, "start_time": 12, "end_time": 18, "duration": 6, "scene_type": "ending", "narration": "過去へ戻る方法はまだ分かっていません。", "subtitle": "過去へ戻る方法は未解明", "image_prompt": "cosmic clock ending", "notes": ""},
        ],
    }


def _service_and_project(tmp_path):
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("時間旅行", "宇宙", "60秒", 3, "prompt")
    return StoryService(project_service), project_service, project


def test_story_save_load_manifest_and_resume_do_not_touch_factory_files(tmp_path) -> None:
    service, _project_service, project = _service_and_project(tmp_path)
    original_title = (project.path / "title.txt").read_text(encoding="utf-8")

    prompt = service.build_prompt(project, scene_count=3)
    story = service.import_story_json(project, json.dumps(_payload(), ensure_ascii=False))
    reloaded = service.load_story(project)
    manifest = service.load_manifest(project)

    assert prompt.prompt
    assert story.title == "時間旅行は本当にできる？"
    assert reloaded is not None
    assert reloaded.tags == ["宇宙", "時間旅行"]
    assert manifest["raw_response"]
    assert (project.path / "title.txt").read_text(encoding="utf-8") == original_title


def test_validate_missing_story_returns_error(tmp_path) -> None:
    service, _project_service, project = _service_and_project(tmp_path)

    result = service.validate_story(project)

    assert result.has_errors


def test_reset_removes_only_story_files(tmp_path) -> None:
    service, _project_service, project = _service_and_project(tmp_path)
    service.import_story_json(project, json.dumps(_payload(), ensure_ascii=False))
    (project.path / "video" / "final.mp4").write_bytes(b"video")

    service.reset(project)

    assert not (project.path / "story.json").exists()
    assert not (project.path / "story_manifest.json").exists()
    assert (project.path / "title.txt").exists()
    assert (project.path / "video" / "final.mp4").exists()
