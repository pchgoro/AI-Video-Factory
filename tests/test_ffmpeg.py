from __future__ import annotations

import subprocess

from models import AppSettings, ProjectInfo
from services.video_render_service import VideoRenderService
from video_editors.base import VideoEditRequest, VideoEditResult
from video_editors.factory import create_video_editor


def test_ffmpeg_missing_binary(tmp_path) -> None:
    project = ProjectInfo(name="p", path=tmp_path, image_count=3)
    (tmp_path / "images").mkdir()
    editor = create_video_editor("ffmpeg", "missing_ffmpeg_for_test")
    result = VideoRenderService(editor, AppSettings(ffmpeg_path="missing_ffmpeg_for_test")).render_project(project)
    assert not result.success
    assert "FFmpegが見つかりません" in result.message


def test_ffmpeg_no_images(tmp_path) -> None:
    project = ProjectInfo(name="p", path=tmp_path, image_count=3)
    (tmp_path / "images").mkdir()
    editor = create_video_editor("ffmpeg", "ffmpeg")
    result = VideoRenderService(editor, AppSettings()).render_project(project)
    if result.message.startswith("FFmpegが見つかりません"):
        assert not result.success
    else:
        assert "画像がありません" in result.message


class CaptureEditor:
    engine_name = "capture"

    def __init__(self) -> None:
        self.request: VideoEditRequest | None = None

    def render(self, request: VideoEditRequest) -> VideoEditResult:
        self.request = request
        request.output_path.parent.mkdir(parents=True, exist_ok=True)
        request.output_path.write_bytes(b"video")
        return VideoEditResult(True, "ok")


def test_video_render_service_uses_first_bgm(tmp_path) -> None:
    base = tmp_path / "workspace"
    project_dir = base / "projects" / "p"
    bgm_dir = base / "assets" / "bgm"
    project_dir.mkdir(parents=True)
    bgm_dir.mkdir(parents=True)
    (bgm_dir / "002.wav").write_bytes(b"wav")
    (bgm_dir / "001.mp3").write_bytes(b"mp3")
    (bgm_dir / "ignore.txt").write_text("no", encoding="utf-8")

    editor = CaptureEditor()
    project = ProjectInfo(name="p", path=project_dir, image_count=3)
    result = VideoRenderService(editor, AppSettings(bgm_volume_percent=35)).render_project(project)

    assert result.success
    assert editor.request is not None
    assert editor.request.bgm_path == bgm_dir / "001.mp3"
    assert editor.request.bgm_volume == 0.35


def test_video_render_service_uses_intro_and_ending_when_enabled(tmp_path) -> None:
    base = tmp_path / "workspace"
    project_dir = base / "projects" / "p"
    intro_dir = base / "assets" / "intro"
    ending_dir = base / "assets" / "ending"
    project_dir.mkdir(parents=True)
    intro_dir.mkdir(parents=True)
    ending_dir.mkdir(parents=True)
    intro = intro_dir / "001.mp4"
    ending = ending_dir / "001.png"
    intro.write_bytes(b"intro")
    ending.write_bytes(b"ending")

    editor = CaptureEditor()
    service = VideoRenderService(editor, AppSettings(intro_enabled=True, ending_enabled=True))
    captured: dict[str, object] = {}

    def fake_concat(paths, output_path, *_args, **_kwargs):
        captured["paths"] = paths
        captured["output_path"] = output_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"final")
        return VideoEditResult(True, "ok", output_path)

    service.compilation_service.concat = fake_concat
    result = service.render_project(ProjectInfo(name="p", path=project_dir, image_count=3))

    assert result.success
    assert editor.request is not None
    assert editor.request.output_path == project_dir / "video" / "final_body.mp4"
    assert captured["paths"] == [intro, project_dir / "video" / "final_body.mp4", ending]
    assert captured["output_path"] == project_dir / "video" / "final.mp4"


def test_video_render_service_skips_intro_and_ending_when_disabled(tmp_path) -> None:
    base = tmp_path / "workspace"
    project_dir = base / "projects" / "p"
    intro_dir = base / "assets" / "intro"
    ending_dir = base / "assets" / "ending"
    project_dir.mkdir(parents=True)
    intro_dir.mkdir(parents=True)
    ending_dir.mkdir(parents=True)
    (intro_dir / "001.mp4").write_bytes(b"intro")
    (ending_dir / "001.mp4").write_bytes(b"ending")

    editor = CaptureEditor()
    service = VideoRenderService(editor, AppSettings(intro_enabled=False, ending_enabled=False))
    result = service.render_project(ProjectInfo(name="p", path=project_dir, image_count=3))

    assert result.success
    assert editor.request is not None
    assert editor.request.output_path == project_dir / "video" / "final.mp4"


def test_video_render_service_sets_random_motion_and_overlay(tmp_path) -> None:
    base = tmp_path / "workspace"
    project_dir = base / "projects" / "p"
    images_dir = project_dir / "images"
    overlay_dir = base / "assets" / "overlay"
    images_dir.mkdir(parents=True)
    overlay_dir.mkdir(parents=True)
    for index in range(1, 6):
        (images_dir / f"{index:03d}.png").write_bytes(b"image")
    overlay = overlay_dir / "stars.png"
    overlay.write_bytes(b"overlay")
    (project_dir / "image_prompts.txt").write_text("ブラックホール\n\n銀河\n\n宇宙船", encoding="utf-8")

    editor = CaptureEditor()
    settings = AppSettings(motion_style="Random Motion", overlay_opacity=35, light_effect="Soft Light")
    result = VideoRenderService(editor, settings).render_project(ProjectInfo(name="p", path=project_dir, image_count=5))

    assert result.success
    assert editor.request is not None
    assert editor.request.overlay_path == overlay
    assert editor.request.overlay_opacity == 35
    assert editor.request.light_effect == "Soft Light"
    assert len(editor.request.image_motions) == 5
    assert all(
        current != previous
        for previous, current in zip(editor.request.image_motions, editor.request.image_motions[1:])
    )


def test_ffmpeg_command_mixes_looped_bgm_with_fades(tmp_path, monkeypatch) -> None:
    from video_editors.ffmpeg_editor import FFmpegEditor

    project_dir = tmp_path / "project"
    images_dir = project_dir / "images"
    audio_dir = project_dir / "audio"
    video_dir = project_dir / "video"
    bgm_path = tmp_path / "assets" / "bgm" / "song.mp3"
    images_dir.mkdir(parents=True)
    audio_dir.mkdir(parents=True)
    bgm_path.parent.mkdir(parents=True)
    (images_dir / "001.png").write_bytes(b"image")
    (audio_dir / "voice.wav").write_bytes(b"voice")
    bgm_path.write_bytes(b"bgm")

    captured: dict[str, list[str]] = {}
    monkeypatch.setattr("video_editors.ffmpeg_editor.shutil.which", lambda _path: "ffmpeg")

    def fake_run(command, **_kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("video_editors.ffmpeg_editor.subprocess.run", fake_run)
    editor = FFmpegEditor("ffmpeg")
    monkeypatch.setattr(editor, "_audio_duration", lambda _audio: 4.0)

    result = editor.render(
        VideoEditRequest(
            project_dir=project_dir,
            images_dir=images_dir,
            audio_dir=audio_dir,
            video_dir=video_dir,
            output_path=video_dir / "final.mp4",
            bgm_path=bgm_path,
            bgm_volume=0.2,
        )
    )

    command = captured["command"]
    filter_complex = command[command.index("-filter_complex") + 1]
    assert result.success
    assert "-nostdin" in command
    assert "-stream_loop" in command
    assert command[command.index("-stream_loop") + 2] == "-t"
    assert command[command.index("-stream_loop") + 3] == "4.000"
    assert str(bgm_path) in command
    assert "volume=1.000[voice]" in filter_complex
    assert "volume=0.200" in filter_complex
    assert "afade=t=in:st=0:d=0.5" in filter_complex
    assert "afade=t=out:st=3.000:d=1.0" in filter_complex
    assert "atrim=duration=4.000" in filter_complex
    assert "amix=inputs=2:duration=first" in filter_complex


def test_ffmpeg_command_burns_ass_subtitles(tmp_path, monkeypatch) -> None:
    from video_editors.ffmpeg_editor import FFmpegEditor

    project_dir = tmp_path / "project"
    images_dir = project_dir / "images"
    audio_dir = project_dir / "audio"
    video_dir = project_dir / "video"
    subtitles_path = video_dir / "subtitles.ass"
    images_dir.mkdir(parents=True)
    audio_dir.mkdir(parents=True)
    video_dir.mkdir(parents=True)
    (images_dir / "001.png").write_bytes(b"image")
    subtitles_path.write_text("[Script Info]\n", encoding="utf-8")

    captured: dict[str, list[str]] = {}
    monkeypatch.setattr("video_editors.ffmpeg_editor.shutil.which", lambda _path: "ffmpeg")

    def fake_run(command, **_kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("video_editors.ffmpeg_editor.subprocess.run", fake_run)
    result = FFmpegEditor("ffmpeg").render(
        VideoEditRequest(
            project_dir=project_dir,
            images_dir=images_dir,
            audio_dir=audio_dir,
            video_dir=video_dir,
            output_path=video_dir / "final.mp4",
            subtitles_path=subtitles_path,
        )
    )

    filter_complex = captured["command"][captured["command"].index("-filter_complex") + 1]
    assert result.success
    assert "subtitles='" in filter_complex
    assert "subtitles.ass" in filter_complex
    assert "[vmerged]" in filter_complex


def test_ffmpeg_command_applies_motion_transition_overlay_and_light(tmp_path, monkeypatch) -> None:
    from video_editors.ffmpeg_editor import FFmpegEditor

    project_dir = tmp_path / "project"
    images_dir = project_dir / "images"
    audio_dir = project_dir / "audio"
    video_dir = project_dir / "video"
    overlay_path = tmp_path / "assets" / "overlay" / "stars.png"
    images_dir.mkdir(parents=True)
    audio_dir.mkdir(parents=True)
    overlay_path.parent.mkdir(parents=True)
    (images_dir / "001.png").write_bytes(b"image")
    (images_dir / "002.png").write_bytes(b"image")
    overlay_path.write_bytes(b"overlay")

    captured: dict[str, list[str]] = {}
    monkeypatch.setattr("video_editors.ffmpeg_editor.shutil.which", lambda _path: "ffmpeg")

    def fake_run(command, **_kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("video_editors.ffmpeg_editor.subprocess.run", fake_run)
    result = FFmpegEditor("ffmpeg").render(
        VideoEditRequest(
            project_dir=project_dir,
            images_dir=images_dir,
            audio_dir=audio_dir,
            video_dir=video_dir,
            output_path=video_dir / "final.mp4",
            seconds_per_image=5,
            image_motions=["Slow Zoom In", "Pan Left"],
            zoom_speed="Fast",
            transition_type="Slide",
            overlay_path=overlay_path,
            overlay_opacity=40,
            light_effect="Glow",
        )
    )

    command = captured["command"]
    filter_complex = command[command.index("-filter_complex") + 1]
    assert result.success
    assert "zoompan=z='1.0+0.2200*on/" in filter_complex
    assert "xfade=transition=slideleft" in filter_complex
    assert "colorchannelmixer=aa=0.400" in filter_complex
    assert "overlay=shortest=1" in filter_complex
    assert "unsharp=5:5:0.5" in filter_complex
