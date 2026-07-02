from __future__ import annotations

import json

from config import AppPaths


DEFAULT_VERSION = {
    "version": "0.4.5",
    "phase": "Phase4.5",
    "release_date": "2026-07-02",
}


class VersionService:
    """version.jsonを読み込みます。なければ既定値を作成します。"""

    def __init__(self, paths: AppPaths) -> None:
        self.paths = paths

    def load(self) -> dict[str, str]:
        if not self.paths.version_path.exists():
            self.paths.version_path.write_text(
                json.dumps(DEFAULT_VERSION, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            return DEFAULT_VERSION.copy()
        try:
            data = json.loads(self.paths.version_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return DEFAULT_VERSION.copy()
        return {**DEFAULT_VERSION, **{key: str(value) for key, value in data.items()}}
