from __future__ import annotations

import shutil
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from config import AppPaths
from models import AppSettings


@dataclass(frozen=True)
class DiagnosticItem:
    name: str
    status: str
    message: str


class DiagnosticsService:
    """設定画面の環境チェック用サービスです。"""

    def __init__(self, paths: AppPaths, settings: AppSettings) -> None:
        self.paths = paths
        self.settings = settings

    def run(self) -> list[DiagnosticItem]:
        return [
            self._check_python(),
            self._check_ffmpeg(),
            self._check_voicevox(),
            self._check_directory("projects", self.paths.projects_dir),
            self._check_directory("exports", self.paths.exports_dir),
            self._check_directory("assets", self.paths.assets_dir),
            self._check_writable(),
        ]

    def _check_python(self) -> DiagnosticItem:
        version = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
        return DiagnosticItem("Python", "OK", f"Python {version} を使用しています。")

    def _check_ffmpeg(self) -> DiagnosticItem:
        path = self.settings.ffmpeg_path
        if shutil.which(path) or (Path(path).exists() if path else False):
            return DiagnosticItem("FFmpeg", "OK", "FFmpegを検出しました。")
        return DiagnosticItem("FFmpeg", "WARNING", "FFmpegが見つかりません。動画生成にはFFmpegが必要です。")

    def _check_voicevox(self) -> DiagnosticItem:
        try:
            with urllib.request.urlopen(f"{self.settings.voicevox_url.rstrip('/')}/version", timeout=2) as response:
                if response.status == 200:
                    return DiagnosticItem("VOICEVOX", "OK", "VOICEVOX Engineに接続できました。")
        except (urllib.error.URLError, TimeoutError, OSError):
            pass
        return DiagnosticItem("VOICEVOX", "WARNING", "VOICEVOXが起動していない可能性があります。")

    def _check_directory(self, name: str, path: Path) -> DiagnosticItem:
        try:
            path.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            return DiagnosticItem(name, "ERROR", f"{path} を作成できません: {exc}")
        return DiagnosticItem(name, "OK", f"{path} を確認しました。")

    def _check_writable(self) -> DiagnosticItem:
        test_path = self.paths.base_dir / ".write_test"
        try:
            test_path.write_text("ok", encoding="utf-8")
            test_path.unlink(missing_ok=True)
        except OSError as exc:
            return DiagnosticItem("書き込み権限", "ERROR", f"保存先に書き込めません: {exc}")
        return DiagnosticItem("書き込み権限", "OK", "保存先へ書き込めます。")
