from __future__ import annotations

import json

import pytest

from services.production_orchestrator.lock import ProductionLockError, ProductionRunLock
from services.production_orchestrator.models import ProductionOptions, ProductionRun
from services.production_orchestrator.run_repository import ProductionRunRepository


def test_atomic_save_failure_preserves_existing_run(tmp_path, monkeypatch) -> None:
    repository = ProductionRunRepository()
    run = ProductionRun.create("run1", "project", "normal", ProductionOptions())
    repository.save(tmp_path, run, force=True)
    original = (tmp_path / "production_run.json").read_text(encoding="utf-8")

    def fail_replace(src, dst):
        raise OSError("replace failed")

    monkeypatch.setattr("os.replace", fail_replace)
    run.status = "failed"
    with pytest.raises(OSError):
        repository.save(tmp_path, run, force=True)

    assert (tmp_path / "production_run.json").read_text(encoding="utf-8") == original


def test_lock_blocks_second_run_and_releases(tmp_path) -> None:
    first = ProductionRunLock(tmp_path, "run1")
    first.acquire()
    try:
        second = ProductionRunLock(tmp_path, "run2")
        with pytest.raises(ProductionLockError):
            second.acquire()
    finally:
        first.release()

    third = ProductionRunLock(tmp_path, "run3")
    third.acquire()
    third.release()
    assert not (tmp_path / ".production.lock").exists()


def test_active_lock_is_not_deleted_by_other_run(tmp_path) -> None:
    first = ProductionRunLock(tmp_path, "run1")
    first.acquire()
    (tmp_path / ".production.lock").write_text(json.dumps({"run_id": "different"}), encoding="utf-8")

    first.release()

    assert (tmp_path / ".production.lock").exists()
