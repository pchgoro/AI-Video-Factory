from __future__ import annotations

import json
import os
import time
from pathlib import Path

from .models import ProductionRun


RUN_FILE = "production_run.json"


class ProductionRunRepository:
    def __init__(self, min_save_interval_seconds: float = 0.25) -> None:
        self.min_save_interval_seconds = min_save_interval_seconds
        self._last_save_at: dict[Path, float] = {}

    def path_for(self, project_dir: Path) -> Path:
        return project_dir / RUN_FILE

    def load(self, project_dir: Path) -> ProductionRun | None:
        path = self.path_for(project_dir)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return None
        if not isinstance(data, dict):
            return None
        run = ProductionRun.from_dict(data)
        if run.status == "interrupted":
            self.save(project_dir, run, force=True)
        return run

    def save(self, project_dir: Path, run: ProductionRun, force: bool = False) -> None:
        path = self.path_for(project_dir)
        now = time.monotonic()
        if not force and now - self._last_save_at.get(path, 0.0) < self.min_save_interval_seconds:
            return
        run.touch()
        self._atomic_json(path, run.to_dict())
        self._last_save_at[path] = now

    def _atomic_json(self, path: Path, data: dict) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(path.suffix + ".tmp")
        with tmp.open("w", encoding="utf-8", newline="\n") as file:
            json.dump(data, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        os.replace(tmp, path)
