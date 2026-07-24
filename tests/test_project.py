from __future__ import annotations

import json

from config import AppPaths
from services.parser import ChatGptAnswerParser
from services.project_service import ProjectService


def test_project_create_save_reload_delete(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    service = ProjectService(paths)
    project = service.create_project("ブラックホール", "宇宙", "90秒", 3, "prompt")
    assert project.path.exists()

    raw = json.dumps(
        {
            "title": "黒い穴",
            "script": "台本",
            "voice_text": "声",
            "image_prompts": ["p1", "p2", "p3"],
            "subtitles": [{"text": "字幕", "start": "0", "end": "1"}],
            "hashtags": ["#宇宙"],
        },
        ensure_ascii=False,
    )
    parsed = ChatGptAnswerParser().parse(raw)
    service.save_chatgpt_import(project, raw, parsed)
    reloaded = service.load_project(project.path)
    assert reloaded.title == "黒い穴"
    assert (project.path / "title.txt").exists()
    assert (project.path / "script.txt").exists()
    assert (project.path / "voice.txt").exists()
    assert (project.path / "image_prompts.txt").exists()
    assert (project.path / "subtitles.txt").exists()
    assert (project.path / "hashtags.txt").exists()
    assert (project.path / "project.json").exists()
    assert (project.path / "raw_chatgpt.txt").exists()

    tagged = service.save_platform_tags(reloaded, youtube_tags=["宇宙", "AI"], tiktok_tags=["#宇宙", "#AI", "#VOICEVOX"])
    assert tagged.youtube_tags == ["宇宙", "AI"]
    assert tagged.tiktok_tags == ["#宇宙", "#AI", "#VOICEVOX"]
    assert tagged.tags == ["宇宙", "AI"]

    service.mark_image_generated(reloaded, 1)
    service.mark_image_generated(reloaded, 2)
    service.mark_image_generated(reloaded, 3)
    assert service.load_project(project.path).progress["画像"]

    service.delete_project(reloaded)
    assert not project.path.exists()


def test_chatgpt_import_syncs_topic_from_title(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    service = ProjectService(paths)
    project = service.create_project("multiverse", "space", "60s", 3, "prompt")
    raw = json.dumps(
        {
            "title": "The Multiverse Mystery",
            "script": "script",
            "voice_text": "voice",
            "image_prompts": ["p1", "p2", "p3"],
            "subtitles": [{"text": "caption", "start": 0.0, "end": 2.0}],
            "hashtags": ["#space"],
        },
        ensure_ascii=False,
    )
    parsed = ChatGptAnswerParser().parse(raw)

    service.save_chatgpt_import(project, raw, parsed)

    reloaded = service.load_project(project.path)
    assert reloaded.title == "The Multiverse Mystery"
    assert reloaded.topic == "The Multiverse Mystery"
    assert (project.path / "topic.txt").read_text(encoding="utf-8").strip() == "The Multiverse Mystery"


def test_save_topic_updates_project_topic(tmp_path) -> None:
    paths = AppPaths(tmp_path)
    paths.ensure()
    service = ProjectService(paths)
    project = service.create_project("old topic", "space", "60s", 3, "prompt")

    reloaded = service.save_topic(project, "new topic")

    assert reloaded.topic == "new topic"
    assert (project.path / "topic.txt").read_text(encoding="utf-8").strip() == "new topic"
