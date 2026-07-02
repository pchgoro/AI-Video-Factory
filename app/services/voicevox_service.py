from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class VoicevoxResult:
    success: bool
    message: str
    output_path: Path | None = None


class VoicevoxService:
    """VOICEVOX EngineのローカルAPIで音声を生成します。"""

    def __init__(self, base_url: str, speaker_id: int) -> None:
        self.base_url = base_url.rstrip("/")
        self.speaker_id = speaker_id

    def synthesize_project(self, project_dir: Path) -> VoicevoxResult:
        voice_text = self._read_text(project_dir / "voice.txt").strip()
        if not voice_text:
            return VoicevoxResult(False, "voice.txt が空です。ChatGPT回答を解析するか、音声用テキストを入力してください。")

        audio_dir = project_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        output_path = audio_dir / "voice.wav"

        try:
            query = self._post_json(
                "/audio_query",
                query={"text": voice_text, "speaker": str(self.speaker_id)},
                body=None,
            )
            wav_bytes = self._post_bytes(
                "/synthesis",
                query={"speaker": str(self.speaker_id)},
                body=json.dumps(query).encode("utf-8"),
            )
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            return VoicevoxResult(
                False,
                "VOICEVOXが起動していない可能性があります。\nVOICEVOXを起動してから再実行してください。\n"
                f"詳細: {exc}",
            )

        output_path.write_bytes(wav_bytes)
        return VoicevoxResult(True, "audio/voice.wav を生成しました。", output_path)

    def _post_json(self, path: str, query: dict[str, str], body: bytes | None) -> dict:
        data = self._post(path, query, body, "application/json")
        return json.loads(data.decode("utf-8"))

    def _post_bytes(self, path: str, query: dict[str, str], body: bytes | None) -> bytes:
        return self._post(path, query, body, "application/json")

    def _post(self, path: str, query: dict[str, str], body: bytes | None, content_type: str) -> bytes:
        url = f"{self.base_url}{path}?{urllib.parse.urlencode(query)}"
        request = urllib.request.Request(url, data=body or b"", method="POST")
        request.add_header("Content-Type", content_type)
        with urllib.request.urlopen(request, timeout=60) as response:
            return response.read()

    def _read_text(self, path: Path) -> str:
        try:
            return path.read_text(encoding="utf-8")
        except OSError:
            return ""
