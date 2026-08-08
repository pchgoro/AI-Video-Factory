from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QImage

from models import AppSettings, ProjectInfo
from services.quality_check_service import QualityCheckService
from services.story_composer.models import Scene, Story
from services.story_composer.validator import StoryValidator


class FakeStoryService:
    def __init__(self, story: Story | None) -> None:
        self.story = story
        self.validator = StoryValidator()

    def load_story(self, _project: ProjectInfo) -> Story | None:
        return self.story


def _write_project_files(project_dir: Path) -> None:
    for name, text in {
        "title.txt": "A title",
        "script.txt": "Narration one\nNarration two",
        "voice.txt": "Narration one\nNarration two",
        "subtitles.txt": "Subtitle one\nSubtitle two",
    }.items():
        (project_dir / name).write_text(text, encoding="utf-8")
    (project_dir / "audio").mkdir(parents=True, exist_ok=True)
    (project_dir / "video").mkdir(parents=True, exist_ok=True)
    (project_dir / "audio" / "voice.wav").write_bytes(b"audio")
    (project_dir / "video" / "final.mp4").write_bytes(b"video")


def _make_image(path: Path, color: str = "blue", width: int = 1080, height: int = 1920) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    image = QImage(width, height, QImage.Format_RGB32)
    image.fill(QColor(color))
    assert image.save(str(path), "PNG")


def _valid_story(scene_count: int = 3) -> Story:
    scenes = []
    for index in range(1, scene_count + 1):
        start = float((index - 1) * 5)
        end = float(index * 5)
        scenes.append(
            Scene(
                scene_index=index,
                start_time=start,
                end_time=end,
                duration=5.0,
                scene_type="hook" if index == 1 else "ending",
                narration=f"Narration {index}",
                subtitle=f"Subtitle {index}",
                image_prompt=f"Image prompt {index}",
            )
        )
    return Story(
        project_id="project",
        title="A title",
        description="Description",
        estimated_duration=float(scene_count * 5),
        tags=["tag"],
        scenes=scenes,
    )


def _probe(path: Path) -> dict:
    if path.suffix.lower() == ".mp4":
        return {
            "format": {"duration": "15.0"},
            "streams": [
                {"codec_type": "video", "width": 1080, "height": 1920, "avg_frame_rate": "30/1"},
                {"codec_type": "audio"},
            ],
        }
    return {"format": {"duration": "15.0"}, "streams": [{"codec_type": "audio"}]}


def _project(tmp_path: Path, image_count: int = 3) -> ProjectInfo:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    _write_project_files(project_dir)
    for index in range(1, image_count + 1):
        _make_image(project_dir / "images" / f"{index:03d}.png", ["red", "green", "blue"][index - 1])
    return ProjectInfo("project", project_dir, title="A title", image_count=image_count)


def test_quality_check_passes_and_saves_result(tmp_path) -> None:
    project = _project(tmp_path)
    service = QualityCheckService(AppSettings(), FakeStoryService(_valid_story()), probe_runner=_probe)

    result = service.run(project)

    assert result.overall_status == "PASS"
    saved = service.load_result(project)
    assert saved is not None
    assert saved.overall_status == "PASS"
    assert (project.path / "quality_check.json").exists()


def test_missing_final_video_is_blocking_error(tmp_path) -> None:
    project = _project(tmp_path)
    (project.path / "video" / "final.mp4").unlink()
    service = QualityCheckService(AppSettings(), FakeStoryService(_valid_story()), probe_runner=_probe)

    blocked, result = service.has_blocking_errors(project)

    assert blocked is True
    assert result.overall_status == "ERROR"
    assert any(item.check_id == "video_missing" for item in result.items)


def test_story_scene_required_fields_and_indices_are_errors(tmp_path) -> None:
    project = _project(tmp_path)
    story = _valid_story()
    story.scenes[1].scene_index = 1
    story.scenes[1].subtitle = ""
    story.scenes[1].image_prompt = ""
    service = QualityCheckService(AppSettings(), FakeStoryService(story), probe_runner=_probe)

    result = service.run(project)

    assert result.overall_status == "ERROR"
    check_ids = {item.check_id for item in result.items if item.level == "ERROR"}
    assert "scene_duplicate_index" in check_ids
    assert "scene_missing_index" in check_ids
    assert "scene_subtitle_required" in check_ids
    assert "scene_image_prompt_required" in check_ids


def test_small_and_consecutive_duplicate_images_are_warnings(tmp_path) -> None:
    project = _project(tmp_path)
    duplicate = (project.path / "images" / "001.png").read_bytes()
    (project.path / "images" / "002.png").write_bytes(duplicate)
    _make_image(project.path / "images" / "001.png", "red", 100, 100)
    duplicate = (project.path / "images" / "001.png").read_bytes()
    (project.path / "images" / "002.png").write_bytes(duplicate)
    service = QualityCheckService(AppSettings(), FakeStoryService(_valid_story()), probe_runner=_probe)

    result = service.run(project)

    warning_ids = {item.check_id for item in result.items if item.level == "WARNING"}
    assert "image_resolution" in warning_ids
    assert "consecutive_duplicate_image" in warning_ids
    assert result.overall_status == "WARNING"


def test_video_probe_errors_when_streams_are_missing(tmp_path) -> None:
    project = _project(tmp_path)

    def bad_video_probe(path: Path) -> dict:
        if path.suffix.lower() == ".mp4":
            return {"format": {"duration": "10.0"}, "streams": []}
        return _probe(path)

    service = QualityCheckService(AppSettings(), FakeStoryService(_valid_story()), probe_runner=bad_video_probe)

    result = service.run(project)

    error_ids = {item.check_id for item in result.items if item.level == "ERROR"}
    assert "video_stream_missing" in error_ids
    assert "audio_stream_missing" in error_ids
