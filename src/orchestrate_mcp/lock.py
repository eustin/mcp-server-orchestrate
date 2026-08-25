import json
import os
import shutil
import stat
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .config import get_orchestrator_dir


class LockError(Exception):
    """Raised when lock acquisition fails or active session exists."""


class SessionLockManager:
    """Manages atomic session locking and stale lock recovery."""

    def __init__(self, workspace_root: Path | None = None) -> None:
        self.orch_dir = get_orchestrator_dir(workspace_root)
        self.lock_file = self.orch_dir / "session.lock"

    def is_process_alive(self, pid: int) -> bool:
        """Check if process with given PID is alive."""
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False

    def acquire_lock(self, session_id: str) -> bool:
        """Acquire atomic lock for session, handling stale locks if PID is dead."""
        if self.lock_file.exists():
            try:
                data = json.loads(self.lock_file.read_text())
                pid = data.get("pid", 0)
                if self.is_process_alive(pid):
                    raise LockError(
                        f"Active orchestration session '{data.get('session_id')}' in progress (PID {pid}). "
                        "Run archive tool to force release lock."
                    )
                self.release_lock(force=True)
            except (json.JSONDecodeError, KeyError, OSError):
                self.release_lock(force=True)

        payload = {
            "session_id": session_id,
            "pid": os.getpid(),
            "created_at": datetime.now(UTC).isoformat(),
            "status": "ACTIVE",
        }
        try:
            fd = os.open(str(self.lock_file), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)
            with os.fdopen(fd, "w") as f:
                json.dump(payload, f, indent=2)
            os.chmod(self.lock_file, stat.S_IRUSR | stat.S_IRGRP | stat.S_IROTH)
            return True
        except FileExistsError:
            raise LockError("Concurrent lock acquisition failed.")

    def release_lock(self, force: bool = False) -> bool:
        """Release session lock file."""
        if not self.lock_file.exists():
            return True
        try:
            os.chmod(self.lock_file, stat.S_IWUSR | stat.S_IRUSR)
            self.lock_file.unlink()
            return True
        except OSError:
            if force and self.lock_file.exists():
                try:
                    os.remove(str(self.lock_file))
                    return True
                except OSError:
                    return False
            return False

    def force_archive(self, session_id: str | None = None) -> dict[str, Any]:
        """Force archive session deliverables and release lock."""
        self.release_lock(force=True)
        session_file = self.orch_dir / "session.json"
        design_file = self.orch_dir / "design.md"
        plan_file = self.orch_dir / "plan.md"

        target_sid = session_id
        if not target_sid and session_file.exists():
            try:
                data = json.loads(session_file.read_text())
                target_sid = data.get("session_id", "unnamed-session")
            except (json.JSONDecodeError, OSError):
                target_sid = "unnamed-session"

        target_sid = target_sid or datetime.now(UTC).strftime("%Y-%m-%d-archived")
        archive_dir = self.orch_dir / "archive" / target_sid
        archive_dir.mkdir(parents=True, exist_ok=True)

        for src in [session_file, design_file, plan_file]:
            if src.exists():
                shutil.move(str(src), str(archive_dir / src.name))

        return {"success": True, "archived_session_id": target_sid}
