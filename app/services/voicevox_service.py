from __future__ import annotations

import io
import json
import logging
import urllib.error
import urllib.parse
import urllib.request
import wave
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
        self.logger = logging.getLogger("ai_video_factory")

    def synthesize_project(self, project_dir: Path) -> VoicevoxResult:
        subtitles_file = project_dir / "subtitles.txt"
        subtitles_text = self._read_text(subtitles_file).strip()

        cues = []
        if subtitles_text:
            try:
                from services.subtitle_service import SubtitleService
                cues = SubtitleService().parse_subtitles(subtitles_text)
            except Exception as exc:
                self.logger.warning("VOICEVOX: subtitles.txt の解析に失敗しました。フォールバックします: %s", exc)

        # Filter empty texts
        valid_cues = [cue for cue in cues if cue.text.strip()]

        audio_dir = project_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        output_path = audio_dir / "voice.wav"

        if valid_cues:
            self.logger.info("VOICEVOX: 字幕に基づく分割音声生成を開始します。キュー数: %d", len(valid_cues))
            wav_segments = []
            try:
                for index, cue in enumerate(valid_cues):
                    text_to_speak = cue.text.strip()
                    self.logger.info("VOICEVOX: segment %d audio_query 開始: '%s'", index + 1, text_to_speak)
                    query = self._post_json(
                        "/audio_query",
                        query={"text": text_to_speak, "speaker": str(self.speaker_id)},
                        body=None,
                    )
                    self.logger.info("VOICEVOX: segment %d synthesis 開始", index + 1)
                    wav_bytes = self._post_bytes(
                        "/synthesis",
                        query={"speaker": str(self.speaker_id)},
                        body=json.dumps(query).encode("utf-8"),
                    )
                    wav_segments.append(wav_bytes)
            except urllib.error.HTTPError as exc:
                self.logger.error("VOICEVOX HTTPエラー: %s", exc)
                if exc.code == 400:
                    return VoicevoxResult(False, "VOICEVOXのspeaker idが正しくない可能性があります。設定画面でspeaker idを確認してください。")
                return VoicevoxResult(False, f"VOICEVOXで音声生成に失敗しました。HTTP {exc.code}")
            except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
                self.logger.error("VOICEVOX接続エラー: %s", exc)
                return VoicevoxResult(
                    False,
                    "VOICEVOXが起動していない可能性があります。\nVOICEVOXを起動してから再実行してください。",
                )

            # Concatenate WAV files and recalculate subtitle timings
            try:
                concat_wav, durations = self._concatenate_wavs(wav_segments)
                
                updated_cues = []
                current_time = 0.0
                for cue, duration in zip(valid_cues, durations):
                    start_time = current_time
                    end_time = current_time + duration
                    updated_cues.append({
                        "start": round(start_time, 2),
                        "end": round(end_time, 2),
                        "text": cue.text
                    })
                    current_time = end_time

                output_path.write_bytes(concat_wav)
                
                # Write back the updated timings to subtitles.txt
                subtitles_file.write_text(json.dumps(updated_cues, ensure_ascii=False, indent=2), encoding="utf-8")
                
                # Update voice.txt to match the subtitle texts
                voice_file = project_dir / "voice.txt"
                voice_file.write_text("\n".join(cue.text for cue in valid_cues), encoding="utf-8")
                
                self.logger.info("VOICEVOX: 分割生成音声の結合完了、%s を生成、字幕タイミングを更新しました", output_path)
                return VoicevoxResult(True, "audio/voice.wav を生成し、字幕タイミングを一致させました。", output_path)
            except Exception as exc:
                self.logger.error("VOICEVOX: WAVの結合または字幕更新に失敗しました: %s", exc)
                return VoicevoxResult(False, f"音声の結合または字幕更新に失敗しました。\n詳細: {exc}")

        # Fallback to synthesizing the entire voice.txt at once
        voice_text = self._read_text(project_dir / "voice.txt").strip()
        if not voice_text:
            self.logger.warning("VOICEVOX: voice.txt が空")
            return VoicevoxResult(False, "voice.txt が空です。ChatGPT回答を解析するか、音声用テキストを入力してください。")

        try:
            self.logger.info("VOICEVOX: audio_query 開始 (全体フォールバック)")
            query = self._post_json(
                "/audio_query",
                query={"text": voice_text, "speaker": str(self.speaker_id)},
                body=None,
            )
            self.logger.info("VOICEVOX: synthesis 開始 (全体フォールバック)")
            wav_bytes = self._post_bytes(
                "/synthesis",
                query={"speaker": str(self.speaker_id)},
                body=json.dumps(query).encode("utf-8"),
            )
        except urllib.error.HTTPError as exc:
            self.logger.error("VOICEVOX HTTPエラー: %s", exc)
            if exc.code == 400:
                return VoicevoxResult(False, "VOICEVOXのspeaker idが正しくない可能性があります。設定画面でspeaker idを確認してください。")
            return VoicevoxResult(False, f"VOICEVOXで音声生成に失敗しました。HTTP {exc.code}")
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            self.logger.error("VOICEVOX接続エラー: %s", exc)
            return VoicevoxResult(
                False,
                "VOICEVOXが起動していない可能性があります。\nVOICEVOXを起動してから再実行してください。",
            )

        output_path.write_bytes(wav_bytes)
        self.logger.info("VOICEVOX: %s を生成", output_path)
        return VoicevoxResult(True, "audio/voice.wav を生成しました。", output_path)

    def _concatenate_wavs(self, wav_bytes_list: list[bytes]) -> tuple[bytes, list[float]]:
        if not wav_bytes_list:
            return b"", []

        durations = []
        try:
            first_wav = wave.open(io.BytesIO(wav_bytes_list[0]), "rb")
            params = first_wav.getparams()
            first_wav.close()
        except Exception as exc:
            raise ValueError(f"WAVファイルの解析に失敗しました: {exc}")

        out_io = io.BytesIO()
        try:
            out_wav = wave.open(out_io, "wb")
            out_wav.setparams(params)
            for data in wav_bytes_list:
                with wave.open(io.BytesIO(data), "rb") as w:
                    frames = w.readframes(w.getnframes())
                    out_wav.writeframes(frames)
                    duration = w.getnframes() / w.getframerate()
                    durations.append(duration)
            out_wav.close()
        except Exception as exc:
            raise ValueError(f"WAVファイルの結合に失敗しました: {exc}")

        return out_io.getvalue(), durations

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

