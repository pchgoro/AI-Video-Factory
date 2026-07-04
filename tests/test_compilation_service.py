from __future__ import annotations

import subprocess

from models import ProjectInfo
from services.compilation_service import CompilationService


def _fake_media(path, duration: float = 10.0) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"media")


def test_compilation_concat_one_video(tmp_path, monkeypatch) -> None:
    video = tmp_path / "001.mp4"
    output = tmp_path / "exports" / "series.mp4"
    _fake_media(video)
    captured: dict[str, list[str]] = {}
    service = CompilationService("ffmpeg")
    monkeypatch.setattr("services.compilation_service.shutil.which", lambda _path: "ffmpeg")
    monkeypatch.setattr(service, "media_duration", lambda _path: 10.0)
    monkeypatch.setattr(service, "has_audio", lambda _path: True)

    def fake_run(command, **_kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("services.compilation_service.subprocess.run", fake_run)

    result = service.concat([video], output)

    assert result.success
    filter_complex = captured["command"][captured["command"].index("-filter_complex") + 1]
    assert "concat=n=1:v=1:a=1" in filter_complex


def test_compilation_concat_multiple_with_intro_and_ending(tmp_path, monkeypatch) -> None:
    intro = tmp_path / "assets" / "intro" / "intro.png"
    video1 = tmp_path / "projects" / "001" / "video" / "final.mp4"
    video2 = tmp_path / "projects" / "002" / "video" / "final.mp4"
    ending = tmp_path / "assets" / "ending" / "ending.mp4"
    output = tmp_path / "exports" / "series" / "complete.mp4"
    for path in [intro, video1, video2, ending]:
        _fake_media(path)
    captured: dict[str, list[str]] = {}
    service = CompilationService("ffmpeg")
    monkeypatch.setattr("services.compilation_service.shutil.which", lambda _path: "ffmpeg")
    monkeypatch.setattr(service, "media_duration", lambda path: 3.0 if path == intro else 10.0)
    monkeypatch.setattr(service, "has_audio", lambda path: path.suffix.lower() == ".mp4")

    def fake_run(command, **_kwargs):
        captured["command"] = command
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr("services.compilation_service.subprocess.run", fake_run)

    result = service.concat([intro, video1, video2, ending], output)

    assert result.success
    command = captured["command"]
    filter_complex = command[command.index("-filter_complex") + 1]
    assert "-loop" in command
    assert "concat=n=4:v=1:a=1" in filter_complex
    assert str(intro) in command
    assert str(ending) in command


def test_compilation_failure_returns_japanese_error(tmp_path, monkeypatch) -> None:
    video = tmp_path / "001.mp4"
    output = tmp_path / "out.mp4"
    _fake_media(video)
    service = CompilationService("ffmpeg")
    monkeypatch.setattr("services.compilation_service.shutil.which", lambda _path: "ffmpeg")
    monkeypatch.setattr(service, "media_duration", lambda _path: 10.0)
    monkeypatch.setattr(service, "has_audio", lambda _path: True)
    monkeypatch.setattr(
        "services.compilation_service.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 1, stdout="", stderr="broken"),
    )

    result = service.concat([video], output)

    assert not result.success
    assert "動画結合に失敗" in result.message


def test_series_compilation_writes_chapter_txt(tmp_path, monkeypatch) -> None:
    project1 = ProjectInfo(name="p1", path=tmp_path / "projects" / "p1", title="ブラックホールとは？", series="blackhole", series_number=1)
    project2 = ProjectInfo(name="p2", path=tmp_path / "projects" / "p2", title="ホーキング放射", series="blackhole", series_number=2)
    intro = tmp_path / "assets" / "intro" / "intro.mp4"
    ending = tmp_path / "assets" / "ending" / "ending.jpg"
    for path in [project1.path / "video" / "final.mp4", project2.path / "video" / "final.mp4", intro, ending]:
        _fake_media(path)
    service = CompilationService("ffmpeg")
    monkeypatch.setattr("services.compilation_service.shutil.which", lambda _path: "ffmpeg")
    durations = {
        intro: 3.0,
        project1.path / "video" / "final.mp4": 60.0,
        project2.path / "video" / "final.mp4": 30.0,
        ending: 3.0,
    }
    monkeypatch.setattr(service, "media_duration", lambda path: durations.get(path, 10.0))
    monkeypatch.setattr(service, "has_audio", lambda path: path.suffix.lower() == ".mp4")
    monkeypatch.setattr(
        "services.compilation_service.subprocess.run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, stdout="", stderr=""),
    )

    result = service.create_series_compilation([project1, project2], tmp_path / "exports" / "series", intro, ending)

    assert result.success
    chapter_text = (tmp_path / "exports" / "series" / "chapter.txt").read_text(encoding="utf-8")
    assert "00:03 ブラックホールとは？" in chapter_text
    assert "01:03 ホーキング放射" in chapter_text
