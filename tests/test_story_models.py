from __future__ import annotations

from services.story_composer import Scene, Story


def test_story_and_scene_roundtrip_preserve_tags_memo_and_versions() -> None:
    story = Story(
        project_id="project-1",
        theme="宇宙",
        title="宇宙はひとつではない？",
        description="多次元宇宙の概要",
        hook="もし宇宙が複数あったら？",
        summary="多次元宇宙を短く説明する",
        tags=["宇宙", "多次元宇宙"],
        memo="次回は泡宇宙も扱う",
        scenes=[
            Scene(
                scene_index=1,
                start_time=0.0,
                end_time=6.0,
                duration=6.0,
                scene_type="hook",
                narration="宇宙はひとつではないかもしれません。",
                subtitle="宇宙はひとつではない？",
                image_prompt="cinematic multiverse",
                notes="冒頭",
            )
        ],
    )

    data = story.to_dict()
    reloaded = Story.from_dict(data)

    assert reloaded.schema_version == "1.0"
    assert reloaded.story_prompt_version == "1.0"
    assert reloaded.tags == ["宇宙", "多次元宇宙"]
    assert reloaded.memo == "次回は泡宇宙も扱う"
    assert reloaded.scenes[0].scene_type == "hook"


def test_unknown_story_status_and_scene_type_fall_back_safely() -> None:
    story = Story.from_dict(
        {
            "status": "strange",
            "scenes": [
                {
                    "scene_index": 1,
                    "start_time": 0,
                    "end_time": 1,
                    "duration": 1,
                    "scene_type": "mystery",
                }
            ],
        }
    )

    assert story.status == "draft"
    assert story.scenes[0].scene_type == "custom"
