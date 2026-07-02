from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

from services.voicevox_service import VoicevoxService


class VoicevoxHandler(BaseHTTPRequestHandler):
    def do_POST(self):  # noqa: N802
        length = int(self.headers.get("Content-Length", "0"))
        if length:
            self.rfile.read(length)
        if self.path.startswith("/audio_query"):
            body = json.dumps({"query": "ok"}).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path.startswith("/synthesis"):
            import io
            import wave
            out = io.BytesIO()
            with wave.open(out, "wb") as w:
                w.setnchannels(1)
                w.setsampwidth(2)
                w.setframerate(24000)
                w.writeframes(b"\x00" * 48000)  # 24000 frames = 1.0 sec
            body = out.getvalue()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format, *args):  # noqa: A002
        return


def test_voicevox_success(tmp_path) -> None:
    server = HTTPServer(("127.0.0.1", 0), VoicevoxHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        (tmp_path / "voice.txt").write_text("こんにちは", encoding="utf-8")
        service = VoicevoxService(f"http://127.0.0.1:{server.server_port}", 3)
        result = service.synthesize_project(tmp_path)
        assert result.success
        assert (tmp_path / "audio" / "voice.wav").exists()
    finally:
        server.shutdown()


def test_voicevox_with_subtitles(tmp_path) -> None:
    server = HTTPServer(("127.0.0.1", 0), VoicevoxHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        subtitles_json = [
            {"start": 0.0, "end": 2.8, "text": "第1文です。"},
            {"start": 2.8, "end": 5.6, "text": "第2文です。"},
        ]
        (tmp_path / "subtitles.txt").write_text(json.dumps(subtitles_json, ensure_ascii=False), encoding="utf-8")
        (tmp_path / "voice.txt").write_text("", encoding="utf-8")

        service = VoicevoxService(f"http://127.0.0.1:{server.server_port}", 3)
        result = service.synthesize_project(tmp_path)

        assert result.success
        assert (tmp_path / "audio" / "voice.wav").exists()

        # Check that subtitle timings are updated to actual audio length (each segment is 1.0 sec, so total 2.0 sec)
        updated_subtitles_text = (tmp_path / "subtitles.txt").read_text(encoding="utf-8")
        updated_subtitles = json.loads(updated_subtitles_text)
        assert len(updated_subtitles) == 2
        assert updated_subtitles[0]["start"] == 0.0
        assert updated_subtitles[0]["end"] == 1.0
        assert updated_subtitles[0]["text"] == "第1文です。"
        assert updated_subtitles[1]["start"] == 1.0
        assert updated_subtitles[1]["end"] == 2.0
        assert updated_subtitles[1]["text"] == "第2文です。"

        # Check that voice.txt was also updated
        voice_text = (tmp_path / "voice.txt").read_text(encoding="utf-8")
        assert voice_text == "第1文です。\n第2文です。"
    finally:
        server.shutdown()


def test_voicevox_stopped(tmp_path) -> None:
    (tmp_path / "voice.txt").write_text("こんにちは", encoding="utf-8")
    service = VoicevoxService("http://127.0.0.1:1", 3)
    result = service.synthesize_project(tmp_path)
    assert not result.success
    assert "VOICEVOX" in result.message
