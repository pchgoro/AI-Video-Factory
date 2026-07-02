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
            body = b"RIFFfakeWAVE"
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


def test_voicevox_stopped(tmp_path) -> None:
    (tmp_path / "voice.txt").write_text("こんにちは", encoding="utf-8")
    service = VoicevoxService("http://127.0.0.1:1", 3)
    result = service.synthesize_project(tmp_path)
    assert not result.success
    assert "VOICEVOX" in result.message
