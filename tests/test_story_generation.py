from __future__ import annotations

import json

from config import AppPaths
from services.project_service import ProjectService
from services.story_composer import StoryService
from services.story_provider import MockStoryProvider, StoryGenerationRequest, StoryProviderManager


def _service_and_project(tmp_path):
    paths = AppPaths(tmp_path)
    paths.ensure()
    project_service = ProjectService(paths)
    project = project_service.create_project("story-ai", "space", "60sec", 3, "prompt")
    manager = StoryProviderManager([MockStoryProvider()], default_provider="mock")
    return StoryService(project_service, provider_manager=manager), project


def test_generate_story_saves_candidate_not_story_json(tmp_path) -> None:
    service, project = _service_and_project(tmp_path)

    result = service.generate_story(project, StoryGenerationRequest(project_id=project.name, theme="space"), provider_id="mock")

    assert result.status == "completed"
    assert (project.path / "story_generated_candidate.json").exists()
    assert not (project.path / "story.json").exists()
    assert service.load_generation_state(project).status == "completed"


def test_use_generated_story_requires_explicit_action_and_backs_up_existing(tmp_path) -> None:
    service, project = _service_and_project(tmp_path)
    service.generate_story(project, StoryGenerationRequest(project_id=project.name, theme="space"), provider_id="mock")
    (project.path / "story.json").write_text(json.dumps({"title": "old", "scenes": []}), encoding="utf-8")

    story = service.use_generated_story(project)

    assert story.title
    assert (project.path / "story.json").exists()
    assert list((project.path / "backups").glob("story_ai_*/story.json"))


def test_invalid_generated_story_is_not_adopted(tmp_path) -> None:
    service, project = _service_and_project(tmp_path)
    (project.path / "story_generated_candidate.json").write_text(json.dumps({"title": "", "scenes": []}), encoding="utf-8")

    try:
        service.use_generated_story(project)
    except Exception:
        pass

    assert not (project.path / "story.json").exists()


def test_story_generation_does_not_change_upload_states(tmp_path) -> None:
    service, project = _service_and_project(tmp_path)
    original_youtube = dict(project.youtube_upload)
    original_tiktok = dict(project.tiktok_upload)

    service.generate_story(project, StoryGenerationRequest(project_id=project.name, theme="space"), provider_id="mock")

    reloaded = service.project_service.load_project(project.path)
    assert reloaded.youtube_upload == original_youtube
    assert reloaded.tiktok_upload == original_tiktok
