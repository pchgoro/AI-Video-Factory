from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


LOCK_FILE = ".production.lock"
STALE_LOCK_SECONDS = 12 * 60 * 60


class ProductionLockError(RuntimeError):
    pass


@dataclass(frozen=True)
class LockInfo:
    run_id: str
    pid: int
    timestamp: str
    stale: bool = False


class ProductionRunLock:
    def __init__(self, project_dir: Path, run_id: str) -> None:
        self.project_dir = project_dir
        self.run_id = run_id
        self.path = project_dir / LOCK_FILE
        self.acquired = False

    def acquire(self) -> None:
        self.project_dir.mkdir(parents=True, exist_ok=True)
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        payload = {
            "run_id": self.run_id,
            "pid": os.getpid(),
            "timestamp": datetime.now().isoformat(timespec="seconds"),
        }
        try:
            fd = os.open(str(self.path), flags)
        except FileExistsError as exc:
            info = self.read_info()
            suffix = " Stale lock detected." if info and info.stale else ""
            raise ProductionLockError(f"Production run is already locked for this project.{suffix}") from exc
        with os.fdopen(fd, "w", encoding="utf-8") as file:
            json.dump(payload, file, ensure_ascii=False, indent=2)
            file.write("\n")
            file.flush()
            os.fsync(file.fileno())
        self.acquired = True

    def release(self) -> None:
        if not self.acquired:
            return
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            data = {}
        if data.get("run_id") == self.run_id:
            self.path.unlink(missing_ok=True)
        self.acquired = False

    def read_info(self) -> LockInfo | None:
        if not self.path.exists():
            return None
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
            mtime = self.path.stat().st_mtime
        except (OSError, json.JSONDecodeError):
            return LockInfo("", 0, "", stale=True)
        stale = (datetime.now().timestamp() - mtime) > STALE_LOCK_SECONDS
        return LockInfo(
            run_id=str(data.get("run_id") or ""),
            pid=int(data.get("pid", 0) or 0),
            timestamp=str(data.get("timestamp") or ""),
            stale=stale,
        )

    def __enter__(self) -> "ProductionRunLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, traceback) -> None:
        self.release()
