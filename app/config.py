from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass
class AppPaths:
    """アプリ全体で使う保存先をまとめて管理します。"""

    base_dir: Path

    @classmethod
    def from_app_file(cls, app_file: str) -> "AppPaths":
        return cls(base_dir=Path(app_file).resolve().parents[1])

    def update_base_dir(self, save_dir: str | None) -> None:
        if save_dir:
            self.base_dir = Path(save_dir).expanduser().resolve()

    @property
    def app_dir(self) -> Path:
        return self.base_dir / "app"

    @property
    def projects_dir(self) -> Path:
        return self.base_dir / "projects"

    @property
    def exports_dir(self) -> Path:
        return self.base_dir / "exports"

    @property
    def assets_dir(self) -> Path:
        return self.base_dir / "assets"

    @property
    def bgm_dir(self) -> Path:
        return self.assets_dir / "bgm"

    @property
    def logs_dir(self) -> Path:
        return self.base_dir / "logs"

    @property
    def samples_dir(self) -> Path:
        return self.base_dir / "samples"

    @property
    def sample_images_dir(self) -> Path:
        return self.base_dir / "sample_images"

    @property
    def settings_path(self) -> Path:
        return self.base_dir / "settings.json"

    @property
    def topics_path(self) -> Path:
        return self.base_dir / "topics.json"

    @property
    def templates_path(self) -> Path:
        return self.base_dir / "templates.json"

    @property
    def version_path(self) -> Path:
        return self.base_dir / "version.json"

    def ensure(self) -> None:
        for path in [
            self.base_dir,
            self.app_dir,
            self.projects_dir,
            self.exports_dir,
            self.assets_dir,
            self.bgm_dir,
            self.logs_dir,
            self.samples_dir,
            self.sample_images_dir,
        ]:
            path.mkdir(parents=True, exist_ok=True)
