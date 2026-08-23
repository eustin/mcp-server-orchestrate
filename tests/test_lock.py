import json
import os
from pathlib import Path
from typing import Any

import pytest

from orchestrator_mcp.lock import LockError, SessionLockManager


def test_acquire_lock_atomic(temp_workspace: Path) -> None:
    lock_mgr = SessionLockManager(temp_workspace)
    acquired = lock_mgr.acquire_lock("2026-08-23-test-session")

    assert acquired is True
    lock_file = temp_workspace / ".orchestrator" / "session.lock"
    assert lock_file.exists()
    data = json.loads(lock_file.read_text())
    assert data["session_id"] == "2026-08-23-test-session"
    assert data["pid"] == os.getpid()


def test_prevent_concurrent_lock(temp_workspace: Path, mock_alive_pid: Any) -> None:
    lock_mgr = SessionLockManager(temp_workspace)
    lock_mgr.acquire_lock("session-1")

    with pytest.raises(LockError, match="Active orchestration session"):
        lock_mgr.acquire_lock("session-2")


def test_stale_lock_recovery(temp_workspace: Path, mock_dead_pid: Any) -> None:
    lock_mgr = SessionLockManager(temp_workspace)
    lock_file = temp_workspace / ".orchestrator" / "session.lock"
    lock_file.write_text(json.dumps({"session_id": "stale-session", "pid": 99999}))

    acquired = lock_mgr.acquire_lock("new-session")
    assert acquired is True
    assert json.loads(lock_file.read_text())["session_id"] == "new-session"


def test_release_lock(temp_workspace: Path) -> None:
    lock_mgr = SessionLockManager(temp_workspace)
    lock_mgr.acquire_lock("session-1")
    assert lock_mgr.release_lock() is True
    assert not (temp_workspace / ".orchestrator" / "session.lock").exists()


def test_force_archive(temp_workspace: Path) -> None:
    lock_mgr = SessionLockManager(temp_workspace)
    orch_dir = temp_workspace / ".orchestrator"
    (orch_dir / "session.json").write_text(json.dumps({"session_id": "test-arch"}))
    (orch_dir / "design.md").write_text("## Requirements")
    (orch_dir / "plan.md").write_text("## Tasks")
    lock_mgr.acquire_lock("test-arch")

    res = lock_mgr.force_archive("test-arch")
    assert res["success"] is True
    assert not (orch_dir / "session.lock").exists()
    assert not (orch_dir / "session.json").exists()
    assert (orch_dir / "archive" / "test-arch" / "session.json").exists()
