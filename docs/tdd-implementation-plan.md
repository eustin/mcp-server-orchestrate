# Orchestrator Python MCP Server — Test-Driven Development (TDD) Implementation Plan

## Overview
This document outlines the phased, test-first implementation strategy for the **Orchestrator Python MCP Server**, translating behavioral specifications in `docs/gherkin-scenarios.md` and architecture in `docs/mcp-server-design.md` into concrete, verified Python code.

The development follows strict Red-Green-Refactor cycles across 6 phases.

---

## Phase 1: Project Scaffolding & Environment Setup

### 1.1 Tasks
1. Initialize `pyproject.toml` with `hatchling` build backend and project dependencies:
   - **Core**: `mcp>=1.0.0`, `pydantic>=2.0.0`, `anyio>=4.0.0`
   - **Dev**: `pytest>=8.0.0`, `pytest-asyncio>=0.23.0`, `pytest-bdd>=7.0.0`, `ruff>=0.4.0`, `mypy>=1.10.0`
2. Create package source directories:
   - `src/orchestrator_mcp/`
   - `src/orchestrator_mcp/prompts/`
   - `src/orchestrator_mcp/tools/`
   - `tests/`
3. Setup `tests/conftest.py` with shared test fixtures.

### 1.2 Test Code Snippet (`tests/conftest.py`)

```python
import os
import shutil
import subprocess
from pathlib import Path
from unittest.mock import patch
import pytest


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create an isolated temporary workspace initialized with git."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    orch_dir = ws / ".orchestrator"
    orch_dir.mkdir()
    return ws


@pytest.fixture
def mock_alive_pid():
    """Mock os.kill to simulate a running process."""
    with patch("os.kill", return_value=None):
        yield


@pytest.fixture
def mock_dead_pid():
    """Mock os.kill to simulate a dead process."""
    with patch("os.kill", side_effect=ProcessLookupError):
        yield
```

### 1.3 Implementation Snippet (`pyproject.toml`)

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "orchestrator-mcp"
version = "0.1.0"
description = "Python MCP Server port of OpenCode Orchestrator 4-phase workflow"
readme = "README.md"
requires-python = ">=3.11"
dependencies = [
    "mcp>=1.0.0",
    "pydantic>=2.0.0",
    "anyio>=4.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=8.0.0",
    "pytest-asyncio>=0.23.0",
    "pytest-bdd>=7.0.0",
    "ruff>=0.4.0",
    "mypy>=1.10.0",
]

[project.scripts]
orchestrator-mcp = "orchestrator_mcp.server:main"

[tool.hatch.build.targets.wheel]
packages = ["src/orchestrator_mcp"]
```

---

## Phase 2: State Management & Cryptographic Anti-Tamper (`state.py` & `models.py`)

### 2.1 Red (Tests First: `tests/test_state.py`)

```python
import json
from pathlib import Path
import pytest
from orchestrator_mcp.state import StateManager, StateTamperError


def test_init_session(temp_workspace: Path):
    mgr = StateManager(temp_workspace)
    state = mgr.init_session("Add JWT Authentication")

    assert state["current_phase"] == "DESIGN"
    assert state["current_phase_approved"] is False
    assert state["task_description"] == "Add JWT Authentication"
    assert "session_id" in state
    assert "_hmac" in state
    assert (temp_workspace / ".orchestrator" / "session.json").exists()


def test_hmac_calculation_and_verification(temp_workspace: Path):
    mgr = StateManager(temp_workspace)
    state = mgr.init_session("Test Task")
    loaded = mgr.load_state()

    assert loaded["session_id"] == state["session_id"]
    assert loaded["_hmac"] == mgr.calculate_hmac(loaded)


def test_state_tampering_detection(temp_workspace: Path):
    mgr = StateManager(temp_workspace)
    mgr.init_session("Tamper Test")

    state_file = temp_workspace / ".orchestrator" / "session.json"
    data = json.loads(state_file.read_text())
    data["current_phase"] = "PLAN"  # Direct manual tampering without HMAC update
    state_file.write_text(json.dumps(data))

    with pytest.raises(StateTamperError, match="TAMPERING DETECTED"):
        mgr.load_state()


def test_approve_current_phase(temp_workspace: Path):
    mgr = StateManager(temp_workspace)
    mgr.init_session("Approval Test")

    updated = mgr.approve_current_phase()
    assert updated["current_phase_approved"] is True
    assert updated["history"][-1]["event"] == "phase_approved"


def test_update_phase(temp_workspace: Path):
    mgr = StateManager(temp_workspace)
    mgr.init_session("Phase Transition Test")
    mgr.approve_current_phase()

    updated = mgr.update_phase("PLAN")
    assert updated["current_phase"] == "PLAN"
    assert updated["current_phase_approved"] is False  # Resets on transition
    assert updated["history"][-1]["event"] == "phase_transition"


def test_parse_plan_tasks(temp_workspace: Path):
    mgr = StateManager(temp_workspace)
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.write_text(
        "## Tasks\n"
        "- [ ] **T1**: Create user model (Agent: coder) (Target: src/models.py) (blocked_by: [])\n"
        "- [x] **T2**: Add auth routes (Agent: coder) (Target: src/auth.py) (blocked_by: [T1])\n"
    )

    tasks = mgr.parse_plan_tasks()
    assert len(tasks) == 2
    assert tasks[0]["id"] == "T1"
    assert tasks[0]["checked"] is False
    assert tasks[0]["target"] == "src/models.py"
    assert tasks[0]["blocked_by"] == []
    assert tasks[1]["id"] == "T2"
    assert tasks[1]["checked"] is True
    assert tasks[1]["target"] == "src/auth.py"
    assert tasks[1]["blocked_by"] == ["T1"]
```

### 2.2 Green (Implementation)

#### `src/orchestrator_mcp/models.py`
```python
from pydantic import BaseModel, Field


class InitResult(BaseModel):
    success: bool
    session_id: str | None = None
    phase: str | None = None
    sop_instructions: str | None = None
    error: str | None = None


class StatusResult(BaseModel):
    active_session: bool
    phase: str | None = None
    message: str


class ApproveResult(BaseModel):
    success: bool
    phase: str | None = None
    message: str | None = None
    error: str | None = None


class VerifyResult(BaseModel):
    success: bool
    phase: str
    previous_phase: str | None = None
    next_sop_instructions: str | None = None
    errors: list[str] = Field(default_factory=list)


class ArchiveResult(BaseModel):
    success: bool
    archived_session_id: str | None = None
    message: str | None = None
    error: str | None = None


class DAGBatch(BaseModel):
    batch_number: int
    tasks: list[dict]


class DAGResult(BaseModel):
    success: bool
    batches: list[DAGBatch] = Field(default_factory=list)
    total_tasks: int = 0
    error: str | None = None
```

#### `src/orchestrator_mcp/config.py`
```python
from pathlib import Path


def resolve_workspace_root(start_path: Path | None = None) -> Path:
    curr = (start_path or Path.cwd()).resolve()
    for parent in [curr] + list(curr.parents):
        if (parent / ".git").exists() or (parent / ".opencode").exists():
            return parent
    return curr


def get_orchestrator_dir(workspace_root: Path | None = None) -> Path:
    root = workspace_root or resolve_workspace_root()
    orch_dir = root / ".orchestrator"
    orch_dir.mkdir(parents=True, exist_ok=True)
    return orch_dir
```

#### `src/orchestrator_mcp/state.py`
```python
import hashlib
import hmac
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import ClassVar
from .config import get_orchestrator_dir

SECRET_KEY = b"opencode-orchestrator-anti-tamper-key"


class StateTamperError(Exception):
    pass


class StateManager:
    PHASES: ClassVar[list[str]] = ["DESIGN", "PLAN", "EXECUTE", "VERIFY", "COMPLETE"]

    def __init__(self, workspace_root: Path | None = None):
        self.orch_dir = get_orchestrator_dir(workspace_root)
        self.state_file = self.orch_dir / "session.json"
        self.plan_file = self.orch_dir / "plan.md"
        self.design_file = self.orch_dir / "design.md"

    def calculate_hmac(self, data_dict: dict) -> str:
        clean = {k: v for k, v in data_dict.items() if k != "_hmac"}
        serialized = json.dumps(clean, sort_keys=True)
        return hmac.new(SECRET_KEY, serialized.encode("utf-8"), hashlib.sha256).hexdigest()

    def init_session(self, task_description: str) -> dict:
        slug = re.sub(r"[^a-z0-9]+", "-", task_description.lower()).strip("-")[:30]
        session_id = f"{datetime.now(timezone.utc).strftime('%Y-%m-%d')}-{slug}"
        state = {
            "session_id": session_id,
            "current_phase": "DESIGN",
            "current_phase_approved": False,
            "task_description": task_description,
            "retry_counts": {},
            "history": [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "event": "session_created",
                    "phase": "DESIGN",
                }
            ],
        }
        state["_hmac"] = self.calculate_hmac(state)
        self.state_file.write_text(json.dumps(state, indent=2))
        return state

    def load_state(self) -> dict | None:
        if not self.state_file.exists():
            return None
        try:
            data = json.loads(self.state_file.read_text())
            if data.get("_hmac") != self.calculate_hmac(data):
                raise StateTamperError("TAMPERING DETECTED: Internal state file session.json was manually modified.")
            return data
        except json.JSONDecodeError:
            raise StateTamperError("Corrupted state file session.json.")

    def save_state(self, state: dict) -> None:
        state["_hmac"] = self.calculate_hmac(state)
        self.state_file.write_text(json.dumps(state, indent=2))

    def approve_current_phase(self) -> dict:
        state = self.load_state()
        if not state:
            raise ValueError("No active session state found.")
        state["current_phase_approved"] = True
        state["history"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "phase_approved",
            "phase": state.get("current_phase"),
        })
        self.save_state(state)
        return state

    def update_phase(self, new_phase: str) -> dict:
        state = self.load_state()
        if not state:
            raise ValueError("No active session state found.")
        if new_phase not in self.PHASES:
            raise ValueError(f"Invalid phase: {new_phase}")
        state["current_phase"] = new_phase
        state["current_phase_approved"] = False
        state["history"].append({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event": "phase_transition",
            "phase": new_phase,
        })
        self.save_state(state)
        return state

    def parse_plan_tasks(self) -> list[dict]:
        if not self.plan_file.exists():
            return []
        content = self.plan_file.read_text()
        tasks = []
        for line in content.splitlines():
            line_str = line.strip()
            if not line_str.startswith("- ["):
                continue

            checked = line_str.startswith("- [x]") or line_str.startswith("- [X]")
            
            # Extract Task ID
            tid = None
            m_bold = re.search(r"-\s*\[[ xX]\]\s*\*\*([^*]+)\*\*", line_str)
            if m_bold:
                tid = m_bold.group(1).strip().rstrip(":")
            else:
                m_raw = re.search(r"-\s*\[[ xX]\]\s*([^:(]+)", line_str)
                if m_raw:
                    tid = m_raw.group(1).strip()

            # Extract Target
            target = None
            m_target = re.search(r"\(Target:\s*([^)]+)\)", line_str)
            if m_target:
                target = m_target.group(1).strip()

            # Extract Agent
            agent = None
            m_agent = re.search(r"\(Agent:\s*([^)]+)\)", line_str)
            if m_agent:
                agent = m_agent.group(1).strip()

            # Extract blocked_by list
            blocked_by = []
            m_blocked = re.search(r"\(blocked_by:\s*\[(.*?)\]\)", line_str)
            if m_blocked:
                raw_deps = m_blocked.group(1).strip()
                if raw_deps:
                    blocked_by = [d.strip().strip("'\"") for d in raw_deps.split(",") if d.strip()]

            # Extract description
            desc = line_str
            m_desc = re.search(r"-\s*\[[ xX]\]\s*(.*?)(?=\s*\(Agent:|\s*\(Target:|$)", line_str)
            if m_desc:
                desc = m_desc.group(1).strip()

            tasks.append({
                "id": tid,
                "checked": checked,
                "description": desc,
                "agent": agent,
                "target": target,
                "blocked_by": blocked_by,
            })
        return tasks
```

### 2.3 Refactor & Verify
- `uv run pytest tests/test_state.py`

---

## Phase 3: Session Lock & Stale PID Recovery (`lock.py`)

### 3.1 Red (Tests First: `tests/test_lock.py`)

```python
import json
import os
from pathlib import Path
import pytest
from orchestrator_mcp.lock import SessionLockManager, LockError


def test_acquire_lock_atomic(temp_workspace: Path):
    lock_mgr = SessionLockManager(temp_workspace)
    acquired = lock_mgr.acquire_lock("2026-08-23-test-session")

    assert acquired is True
    lock_file = temp_workspace / ".orchestrator" / "session.lock"
    assert lock_file.exists()
    data = json.loads(lock_file.read_text())
    assert data["session_id"] == "2026-08-23-test-session"
    assert data["pid"] == os.getpid()


def test_prevent_concurrent_lock(temp_workspace: Path, mock_alive_pid):
    lock_mgr = SessionLockManager(temp_workspace)
    lock_mgr.acquire_lock("session-1")

    with pytest.raises(LockError, match="Active orchestration session"):
        lock_mgr.acquire_lock("session-2")


def test_stale_lock_recovery(temp_workspace: Path, mock_dead_pid):
    lock_mgr = SessionLockManager(temp_workspace)
    lock_file = temp_workspace / ".orchestrator" / "session.lock"
    lock_file.write_text(json.dumps({"session_id": "stale-session", "pid": 99999}))

    acquired = lock_mgr.acquire_lock("new-session")
    assert acquired is True
    assert json.loads(lock_file.read_text())["session_id"] == "new-session"


def test_release_lock(temp_workspace: Path):
    lock_mgr = SessionLockManager(temp_workspace)
    lock_mgr.acquire_lock("session-1")
    assert lock_mgr.release_lock() is True
    assert not (temp_workspace / ".orchestrator" / "session.lock").exists()


def test_force_archive(temp_workspace: Path):
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
```

### 3.2 Green (Implementation: `src/orchestrator_mcp/lock.py`)

```python
import json
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from .config import get_orchestrator_dir


class LockError(Exception):
    pass


class SessionLockManager:
    def __init__(self, workspace_root: Path | None = None):
        self.orch_dir = get_orchestrator_dir(workspace_root)
        self.lock_file = self.orch_dir / "session.lock"

    def is_process_alive(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            os.kill(pid, 0)
            return True
        except (OSError, ProcessLookupError):
            return False

    def acquire_lock(self, session_id: str) -> bool:
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
            except (json.JSONDecodeError, KeyError):
                self.release_lock(force=True)

        payload = {
            "session_id": session_id,
            "pid": os.getpid(),
            "created_at": datetime.now(timezone.utc).isoformat(),
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
        if not self.lock_file.exists():
            return True
        try:
            os.chmod(self.lock_file, stat.S_IWUSR | stat.S_IRUSR)
            self.lock_file.unlink()
            return True
        except Exception:
            if force and self.lock_file.exists():
                os.remove(str(self.lock_file))
                return True
            return False

    def force_archive(self, session_id: str | None = None) -> dict:
        self.release_lock(force=True)
        session_file = self.orch_dir / "session.json"
        design_file = self.orch_dir / "design.md"
        plan_file = self.orch_dir / "plan.md"

        target_sid = session_id
        if not target_sid and session_file.exists():
            try:
                data = json.loads(session_file.read_text())
                target_sid = data.get("session_id", "unnamed-session")
            except Exception:
                target_sid = "unnamed-session"

        target_sid = target_sid or datetime.now(timezone.utc).strftime("%Y-%m-%d-archived")
        archive_dir = self.orch_dir / "archive" / target_sid
        archive_dir.mkdir(parents=True, exist_ok=True)

        for src in [session_file, design_file, plan_file]:
            if src.exists():
                shutil.move(str(src), str(archive_dir / src.name))

        return {"success": True, "archived_session_id": target_sid}
```

### 3.3 Refactor & Verify
- `uv run pytest tests/test_lock.py`

---

## Phase 4: Phase Verification Engine (`verifier.py` & `prompts/`)

### 4.1 Red (Tests First: `tests/test_verifier.py`)

```python
from pathlib import Path
import pytest
from orchestrator_mcp.verifier import VerificationEngine


def test_verify_design_missing_file(temp_workspace: Path):
    valid, errors = VerificationEngine.verify_design(temp_workspace, is_approved=True)
    assert valid is False
    assert any("Missing required deliverable" in e for e in errors)


def test_verify_design_unapproved(temp_workspace: Path):
    (temp_workspace / ".orchestrator" / "design.md").write_text(
        "## Requirements\n## Architecture\n## Self-Confidence Audit\n"
    )
    valid, errors = VerificationEngine.verify_design(temp_workspace, is_approved=False)
    assert valid is False
    assert any("GATE BLOCKED" in e for e in errors)


def test_verify_design_missing_sections(temp_workspace: Path):
    (temp_workspace / ".orchestrator" / "design.md").write_text("## Requirements\n")
    valid, errors = VerificationEngine.verify_design(temp_workspace, is_approved=True)
    assert valid is False
    assert any("Missing required Design Document section" in e for e in errors)


def test_verify_design_success(temp_workspace: Path):
    (temp_workspace / ".orchestrator" / "design.md").write_text(
        "## Requirements\nDetail\n## Architecture\nDetail\n## Self-Confidence Audit\nDetail\n"
    )
    valid, errors = VerificationEngine.verify_design(temp_workspace, is_approved=True)
    assert valid is True
    assert len(errors) == 0


def test_verify_plan_invalid_reviewer_barrier(temp_workspace: Path):
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: Task 1 (Agent: coder) (Target: a.py) (blocked_by: [])\n"
        "## Detailed Task Specifications\n"
        "### T1\nDetail\n"
        "## Verification\n"
        "Test command: pytest\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=True)
    assert valid is False
    assert any("Agent: implementation-reviewer" in e for e in errors)


def test_verify_plan_success(temp_workspace: Path):
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: Code (Agent: coder) (Target: a.py) (blocked_by: [])\n"
        "- [ ] **T2**: Review (Agent: implementation-reviewer) (Target: a.py) (blocked_by: [T1])\n"
        "## Detailed Task Specifications\n"
        "### T1\nSpec 1\n"
        "### T2\nSpec 2\n"
        "## Verification\n"
        "Test command: pytest tests/\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=True)
    assert valid is True
    assert len(errors) == 0


def test_verify_execution_unchecked_tasks(temp_workspace: Path):
    plan = "## Tasks\n- [ ] **T1**: Unfinished (Agent: coder) (Target: a.py) (blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is False
    assert any("is incomplete" in e for e in errors)


def test_verify_execution_zero_byte_target_file(temp_workspace: Path):
    plan = "## Tasks\n- [x] **T1**: Done (Agent: coder) (Target: src/empty.py) (blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    target = temp_workspace / "src" / "empty.py"
    target.parent.mkdir(parents=True)
    target.touch()

    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is False
    assert any("is 0 bytes" in e for e in errors)


def test_verify_execution_success(temp_workspace: Path):
    plan = "## Tasks\n- [x] **T1**: Done (Agent: coder) (Target: src/main.py) (blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    target = temp_workspace / "src" / "main.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hello')")

    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is True


def test_verify_testing_command_failure(temp_workspace: Path):
    plan = "## Verification\nTest command: exit 1\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_testing(temp_workspace)
    assert valid is False
    assert any("Automated test runner failed" in e for e in errors)


def test_verify_testing_command_success(temp_workspace: Path):
    plan = "## Verification\nTest command: exit 0\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_testing(temp_workspace)
    assert valid is True
```

### 4.2 Green (Implementation)

#### `src/orchestrator_mcp/prompts/design.py`
```python
DESIGN_PHASE_PROMPT = """# Phase SOP: DESIGN

You are in the DESIGN phase of the orchestration lifecycle.

## Objectives
1. Understand and define user requirements, edge cases, and scope.
2. Select architecture patterns, component boundaries, and data structures.
3. Conduct a self-confidence audit (deductions for assumptions, missed edge cases).
4. Write the deliverable to `.orchestrator/design.md`.

## Mandatory Headings in `.orchestrator/design.md`
- `## Requirements`
- `## Architecture`
- `## Self-Confidence Audit`

## Next Gate
Instruct the user to review the document and run `orchestrate_approve` before calling `orchestrate_verify`.
"""
```

#### `src/orchestrator_mcp/prompts/plan.py`
```python
PLAN_PHASE_PROMPT = """# Phase SOP: PLAN

You are in the PLAN phase of the orchestration lifecycle.

## Objectives
1. Break down architecture into discrete task items.
2. Format tasks with `(Agent: <role>)`, `(Target: <file>)`, and `(blocked_by: [<deps>])`.
3. Provide detailed specifications for every task under `## Detailed Task Specifications`.
4. Ensure the final task is assigned to `Agent: implementation-reviewer` blocked by prior tasks.
5. Provide a valid executable test command under `## Verification` (`Test command: <cmd>`).
6. Write the deliverable to `.orchestrator/plan.md`.

## Next Gate
Instruct the user to run `orchestrate_approve` before calling `orchestrate_verify`.
"""
```

#### `src/orchestrator_mcp/prompts/execute.py`
```python
EXECUTE_PHASE_PROMPT = """# Phase SOP: EXECUTE

You are in the EXECUTE phase of the orchestration lifecycle.

## Objectives
1. Retrieve execution batches using `orchestrate_get_dag_batches`.
2. Delegate tasks to specialized subagents batch by batch.
3. Verify target files exist and are non-empty.
4. Mark completed tasks as `[x]` in `.orchestrator/plan.md`.
5. Run `orchestrate_verify` once all tasks are completed.
"""
```

#### `src/orchestrator_mcp/prompts/verify.py`
```python
VERIFY_PHASE_PROMPT = """# Phase SOP: VERIFY

You are in the VERIFY phase of the orchestration lifecycle.

## Objectives
1. Run `orchestrate_verify` to execute automated test runner from plan.
2. If tests fail, inspect failure logs and remediate.
3. Advance to COMPLETE upon zero exit code.
"""
```

#### `src/orchestrator_mcp/prompts/complete.py`
```python
COMPLETE_PHASE_PROMPT = """# Phase SOP: COMPLETE

Orchestration workflow completed successfully.
Run `orchestrate_archive` to release the lock and archive session files.
"""
```

#### `src/orchestrator_mcp/verifier.py`
```python
import re
import subprocess
from pathlib import Path
from .config import get_orchestrator_dir, resolve_workspace_root

TEST_COMMAND_REGEX = re.compile(
    r"^\s*(?:-\s*)?(?:\*\*)?Test command:?(?:\*\*)?:?\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


class VerificationEngine:
    @staticmethod
    def verify_design(workspace_root: Path | None = None, is_approved: bool = False) -> tuple[bool, list[str]]:
        root = workspace_root or resolve_workspace_root()
        design_file = get_orchestrator_dir(root) / "design.md"
        if not design_file.exists():
            return False, ["Missing required deliverable: .orchestrator/design.md"]

        errors = []
        if not is_approved:
            errors.append("GATE BLOCKED: Design deliverable .orchestrator/design.md is ready, but human approval is required.")

        content = design_file.read_text()
        for heading in ["## Requirements", "## Architecture", "## Self-Confidence Audit"]:
            if heading not in content:
                errors.append(f"Missing required Design Document section: '{heading}'")

        return len(errors) == 0, errors

    @staticmethod
    def verify_plan(workspace_root: Path | None = None, is_approved: bool = False) -> tuple[bool, list[str]]:
        root = workspace_root or resolve_workspace_root()
        plan_file = get_orchestrator_dir(root) / "plan.md"
        if not plan_file.exists():
            return False, ["Missing required deliverable: .orchestrator/plan.md"]

        errors = []
        if not is_approved:
            errors.append("GATE BLOCKED: Plan deliverable .orchestrator/plan.md is ready, but human approval is required.")

        content = plan_file.read_text()
        if "## Tasks" not in content or "## Verification" not in content:
            errors.append("Plan Document must contain '## Tasks' and '## Verification' sections.")
        if "## Detailed Task Specifications" not in content:
            errors.append("Plan Document must contain '## Detailed Task Specifications' section.")

        checkbox_lines = [line.strip() for line in content.splitlines() if line.strip().startswith("- [")]
        if not checkbox_lines:
            errors.append("Plan must contain at least one task item (checkbox '- [ ]').")

        for line in checkbox_lines:
            if "Agent:" not in line:
                errors.append(f"Task item missing required '(Agent: <role>)' tag: '{line}'")
            if "Target:" not in line:
                errors.append(f"Task item missing required '(Target: path/to/file)' tag: '{line}'")
            if "blocked_by:" not in line:
                errors.append(f"Task item missing required '(blocked_by: [<deps>])' tag: '{line}'")

            tid = None
            m_bold = re.search(r"-\s*\[[ xX]\]\s*\*\*([^*]+)\*\*", line)
            if m_bold:
                tid = m_bold.group(1).strip().rstrip(":")
            else:
                m_raw = re.search(r"-\s*\[[ xX]\]\s*([^:(]+)", line)
                if m_raw:
                    tid = m_raw.group(1).strip()

            if tid and not re.search(rf"###\s*{re.escape(tid)}\b", content, re.IGNORECASE):
                errors.append(f"Task '{tid}' missing detailed specification heading '### {tid}' under '## Detailed Task Specifications'.")

        last_checkbox = checkbox_lines[-1] if checkbox_lines else ""
        if "Agent: implementation-reviewer" not in last_checkbox:
            errors.append("Plan MUST end with a final task assigned to 'Agent: implementation-reviewer', blocked by all prior tasks.")
        if "blocked_by: []" in last_checkbox:
            errors.append("Final task MUST be blocked by all preceding tasks. 'blocked_by: []' is invalid.")

        match = TEST_COMMAND_REGEX.search(content)
        if not match:
            errors.append("Plan Document missing required 'Test command: <cmd>' under '## Verification'.")
        else:
            test_cmd = match.group(1).strip().strip("`").strip()
            if not test_cmd or test_cmd.lower() == "none":
                errors.append("Plan Document must specify a valid executable 'Test command: <cmd>' under '## Verification' ('None' or empty is forbidden).")

        return len(errors) == 0, errors

    @staticmethod
    def verify_execution(workspace_root: Path | None = None) -> tuple[bool, list[str]]:
        root = workspace_root or resolve_workspace_root()
        plan_file = get_orchestrator_dir(root) / "plan.md"
        if not plan_file.exists():
            return False, ["Missing plan file for execution verification."]

        content = plan_file.read_text()
        errors = []

        unchecked = re.findall(r"- \[\s\]\s*(.*)", content)
        if unchecked:
            for task_desc in unchecked:
                errors.append(f"[VERIFICATION FAILED: UNFINISHED TASK] Task '{task_desc.strip()}' is incomplete.")

        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith("- [x]") or line_str.startswith("- [X]"):
                m_target = re.search(r"\(Target:\s*([^)]+)\)", line_str)
                if m_target:
                    target_clean = m_target.group(1).strip()
                    file_path = root / target_clean
                    if not file_path.exists():
                        errors.append(f"Target file '{target_clean}' does not exist.")
                    elif file_path.stat().st_size == 0:
                        errors.append(f"Target file '{target_clean}' is 0 bytes.")

        return len(errors) == 0, errors

    @staticmethod
    def verify_testing(workspace_root: Path | None = None) -> tuple[bool, list[str]]:
        root = workspace_root or resolve_workspace_root()
        plan_file = get_orchestrator_dir(root) / "plan.md"
        if not plan_file.exists():
            return False, ["Missing plan file for verification."]

        content = plan_file.read_text()
        match = TEST_COMMAND_REGEX.search(content)
        if not match:
            return False, ["Missing required 'Test command: <cmd>' under '## Verification' in plan.md."]

        test_cmd = match.group(1).strip().strip("`").strip()
        if not test_cmd or test_cmd.lower() == "none":
            return False, ["Plan Document specifies an invalid or empty test command ('None' is forbidden)."]

        try:
            res = subprocess.run(test_cmd, shell=True, cwd=root, capture_output=True, text=True, timeout=120, check=False)
            if res.returncode != 0:
                stdout_tail = "\n".join(res.stdout.splitlines()[-50:])
                stderr_tail = "\n".join(res.stderr.splitlines()[-50:])
                return False, [f"Automated test runner failed (Exit Code {res.returncode}):\n{stdout_tail}\n{stderr_tail}"]
            return True, []
        except Exception as e:
            return False, [f"Failed to execute test command '{test_cmd}': {e!s}"]
```

### 4.3 Refactor & Verify
- `uv run pytest tests/test_verifier.py`

---

## Phase 5: Task DAG Scheduler & Collision Guard (`dag.py`)

### 5.1 Red (Tests First: `tests/test_dag.py`)

```python
from orchestrator_mcp.dag import DAGScheduler


def test_build_independent_batches():
    tasks = [
        {"id": "T1", "target": "src/a.py", "blocked_by": []},
        {"id": "T2", "target": "src/b.py", "blocked_by": []},
        {"id": "T3", "target": "src/c.py", "blocked_by": ["T1", "T2"]},
    ]
    batches = DAGScheduler.build_execution_batches(tasks)
    assert len(batches) == 2
    assert [t["id"] for t in batches[0]] == ["T1", "T2"]
    assert [t["id"] for t in batches[1]] == ["T3"]


def test_file_collision_guard():
    tasks = [
        {"id": "T1", "target": "src/auth.py", "blocked_by": []},
        {"id": "T2", "target": "src/auth.py", "blocked_by": []},
    ]
    batches = DAGScheduler.build_execution_batches(tasks)
    assert len(batches) == 2
    assert [t["id"] for t in batches[0]] == ["T1"]
    assert [t["id"] for t in batches[1]] == ["T2"]
    assert "T1" in tasks[1]["blocked_by"]


def test_circular_dependency_fallback():
    tasks = [
        {"id": "T1", "target": "a.py", "blocked_by": ["T2"]},
        {"id": "T2", "target": "b.py", "blocked_by": ["T1"]},
    ]
    batches = DAGScheduler.build_execution_batches(tasks)
    assert len(batches) >= 1
```

### 5.2 Green (Implementation: `src/orchestrator_mcp/dag.py`)

```python
class DAGScheduler:
    @staticmethod
    def build_execution_batches(tasks: list[dict]) -> list[list[dict]]:
        if not tasks:
            return []

        file_to_tasks: dict[str, list[dict]] = {}
        for t in tasks:
            target = t.get("target")
            if target:
                file_to_tasks.setdefault(target, []).append(t)

        for target, colliding_tasks in file_to_tasks.items():
            if len(colliding_tasks) > 1:
                for idx, task in enumerate(colliding_tasks):
                    if idx > 0:
                        prev_id = colliding_tasks[idx - 1].get("id")
                        if prev_id:
                            task.setdefault("blocked_by", []).append(prev_id)

        batches = []
        remaining = list(tasks)
        completed_ids = set()

        while remaining:
            current_batch = []
            next_remaining = []

            for task in remaining:
                blocked_by = task.get("blocked_by", [])
                if all(dep_id in completed_ids for dep_id in blocked_by):
                    current_batch.append(task)
                else:
                    next_remaining.append(task)

            if not current_batch:
                current_batch.append(next_remaining.pop(0))

            batches.append(current_batch)
            for task in current_batch:
                if task.get("id"):
                    completed_ids.add(task["id"])

            remaining = next_remaining

        return batches
```

### 5.3 Refactor & Verify
- `uv run pytest tests/test_dag.py`

---

## Phase 6: MCP Server & BDD Scenarios Integration (`server.py` & `test_bdd_scenarios.py`)

### 6.1 Red (Tests First: `tests/test_bdd_scenarios.py`)

```python
import json
from pathlib import Path
import pytest
from pytest_bdd import scenarios, given, when, then, parsers
from orchestrator_mcp.server import (
    orchestrate_init,
    orchestrate_status,
    orchestrate_approve,
    orchestrate_verify,
    orchestrate_archive,
    orchestrate_get_dag_batches,
)
from orchestrator_mcp.state import StateTamperError

scenarios("../docs/gherkin-scenarios.md")


@pytest.fixture
def bdd_context():
    return {}


@given("a project workspace directory initialized with Git or OpenCode configuration")
def given_workspace(temp_workspace: Path, bdd_context):
    bdd_context["workspace"] = temp_workspace


@given("no active orchestration session exists in workspace")
def given_no_active_session(temp_workspace: Path, bdd_context):
    bdd_context["workspace"] = temp_workspace


@given(parsers.parse('an active orchestration session exists with running process PID'))
def given_active_session_running_pid(temp_workspace: Path, bdd_context, mock_alive_pid):
    bdd_context["workspace"] = temp_workspace
    orchestrate_init("Active Task", workspace_root=str(temp_workspace))


@given(parsers.parse('lock file ".orchestrator/session.lock" exists with PID of a terminated process'))
def given_stale_lock(temp_workspace: Path, bdd_context, mock_dead_pid):
    bdd_context["workspace"] = temp_workspace
    lock_file = temp_workspace / ".orchestrator" / "session.lock"
    lock_file.write_text(json.dumps({"session_id": "stale-session", "pid": 99999}))


@given(parsers.parse('an active orchestration session in phase "{phase}"'))
def given_session_in_phase(temp_workspace: Path, bdd_context, phase):
    bdd_context["workspace"] = temp_workspace
    orchestrate_init("Test Task", workspace_root=str(temp_workspace))
    state_file = temp_workspace / ".orchestrator" / "session.json"
    data = json.loads(state_file.read_text())
    data["current_phase"] = phase
    from orchestrator_mcp.state import StateManager
    mgr = StateManager(temp_workspace)
    data["_hmac"] = mgr.calculate_hmac(data)
    state_file.write_text(json.dumps(data, indent=2))


@when(parsers.parse('client calls tool "orchestrate_init" with:\n{table}'))
def call_init_table(bdd_context, table):
    lines = [line.strip().split("|")[1:-1] for line in table.strip().splitlines()]
    params = {k.strip(): v.strip() for k, v in lines if k.strip() != "parameter"}
    res = orchestrate_init(task_description=params.get("task_description", "Task"), workspace_root=str(bdd_context["workspace"]))
    bdd_context["init_res"] = res


@when('client calls tool "orchestrate_status"')
def call_status(bdd_context):
    res = orchestrate_status(workspace_root=str(bdd_context["workspace"]))
    bdd_context["status_res"] = res


@when('client calls tool "orchestrate_approve"')
def call_approve(bdd_context):
    res = orchestrate_approve(workspace_root=str(bdd_context["workspace"]))
    bdd_context["approve_res"] = res


@when('client calls tool "orchestrate_verify"')
def call_verify(bdd_context):
    res = orchestrate_verify(workspace_root=str(bdd_context["workspace"]))
    bdd_context["verify_res"] = res


@when(parsers.parse('client calls tool "orchestrate_archive" with force=true'))
def call_archive(bdd_context):
    res = orchestrate_archive(force=True, workspace_root=str(bdd_context["workspace"]))
    bdd_context["archive_res"] = res


@then(parsers.parse('server advances current_phase to "{phase}"'))
def verify_advancement(bdd_context, phase):
    assert bdd_context["verify_res"].success is True
    assert bdd_context["verify_res"].phase == phase
```

### 6.2 Green (Implementation: `src/orchestrator_mcp/server.py`)

```python
from pathlib import Path
from mcp.server.mcpserver import MCPServer
from .config import resolve_workspace_root
from .dag import DAGScheduler
from .lock import LockError, SessionLockManager
from .models import (
    ApproveResult,
    ArchiveResult,
    DAGBatch,
    DAGResult,
    InitResult,
    StatusResult,
    VerifyResult,
)
from .prompts.complete import COMPLETE_PHASE_PROMPT
from .prompts.design import DESIGN_PHASE_PROMPT
from .prompts.execute import EXECUTE_PHASE_PROMPT
from .prompts.plan import PLAN_PHASE_PROMPT
from .prompts.verify import VERIFY_PHASE_PROMPT
from .state import StateManager, StateTamperError
from .verifier import VerificationEngine

mcp = MCPServer("orchestrator-mcp")


def get_phase_prompt(phase: str) -> str:
    prompts = {
        "DESIGN": DESIGN_PHASE_PROMPT,
        "PLAN": PLAN_PHASE_PROMPT,
        "EXECUTE": EXECUTE_PHASE_PROMPT,
        "VERIFY": VERIFY_PHASE_PROMPT,
        "COMPLETE": COMPLETE_PHASE_PROMPT,
    }
    return prompts.get(phase, "")


@mcp.tool()
def orchestrate_init(task_description: str, workspace_root: str | None = None) -> InitResult:
    root = resolve_workspace_root(Path(workspace_root) if workspace_root else None)
    lock_mgr = SessionLockManager(root)
    state_mgr = StateManager(root)

    try:
        state = state_mgr.init_session(task_description)
        lock_mgr.acquire_lock(state["session_id"])
        mandates_file = root / ".orchestrator" / "project-mandates.md"
        if not mandates_file.exists():
            mandates_file.write_text("# Critical Project Mandates\n\nALL agents MUST obey these rules.\n")
        return InitResult(
            success=True,
            session_id=state["session_id"],
            phase="DESIGN",
            sop_instructions=DESIGN_PHASE_PROMPT,
        )
    except LockError as e:
        return InitResult(success=False, error=str(e))
    except Exception as e:
        return InitResult(success=False, error=f"Internal Error: {e!s}")


@mcp.tool()
def orchestrate_status(workspace_root: str | None = None) -> StatusResult:
    root = resolve_workspace_root(Path(workspace_root) if workspace_root else None)
    state_mgr = StateManager(root)
    state = state_mgr.load_state()
    if not state:
        return StatusResult(active_session=False, message="No active orchestration session")
    return StatusResult(active_session=True, phase=state.get("current_phase"), message="Active session in progress")


@mcp.tool()
def orchestrate_approve(workspace_root: str | None = None) -> ApproveResult:
    root = resolve_workspace_root(Path(workspace_root) if workspace_root else None)
    state_mgr = StateManager(root)
    try:
        state = state_mgr.load_state()
        if not state:
            return ApproveResult(success=False, error="No active session state found.")
        updated = state_mgr.approve_current_phase()
        return ApproveResult(success=True, phase=updated.get("current_phase"), message=f"Phase '{updated.get('current_phase')}' approved.")
    except Exception as e:
        return ApproveResult(success=False, error=str(e))


@mcp.tool()
def orchestrate_verify(workspace_root: str | None = None) -> VerifyResult:
    root = resolve_workspace_root(Path(workspace_root) if workspace_root else None)
    state_mgr = StateManager(root)
    state = state_mgr.load_state()
    if not state:
        return VerifyResult(success=False, phase="UNKNOWN", errors=["No active session state found."])

    phase = state.get("current_phase", "DESIGN")
    is_approved = state.get("current_phase_approved", False)
    valid, errors = False, []

    if phase == "DESIGN":
        valid, errors = VerificationEngine.verify_design(root, is_approved=is_approved)
        if valid:
            state_mgr.update_phase("PLAN")
    elif phase == "PLAN":
        valid, errors = VerificationEngine.verify_plan(root, is_approved=is_approved)
        if valid:
            state_mgr.update_phase("EXECUTE")
    elif phase == "EXECUTE":
        valid, errors = VerificationEngine.verify_execution(root)
        if valid:
            state_mgr.update_phase("VERIFY")
    elif phase == "VERIFY":
        valid, errors = VerificationEngine.verify_testing(root)
        if valid:
            state_mgr.update_phase("COMPLETE")
    else:
        valid = True

    new_state = state_mgr.load_state() if valid else state
    new_phase = new_state.get("current_phase") if new_state else phase
    return VerifyResult(
        success=valid,
        phase=new_phase,
        previous_phase=phase if valid else None,
        next_sop_instructions=get_phase_prompt(new_phase) if valid else None,
        errors=errors,
    )


@mcp.tool()
def orchestrate_archive(force: bool = True, workspace_root: str | None = None) -> ArchiveResult:
    root = resolve_workspace_root(Path(workspace_root) if workspace_root else None)
    lock_mgr = SessionLockManager(root)
    res = lock_mgr.force_archive()
    return ArchiveResult(success=res.get("success", False), archived_session_id=res.get("archived_session_id"))


@mcp.tool()
def orchestrate_get_dag_batches(workspace_root: str | None = None) -> DAGResult:
    root = resolve_workspace_root(Path(workspace_root) if workspace_root else None)
    state_mgr = StateManager(root)
    tasks = state_mgr.parse_plan_tasks()
    batches = DAGScheduler.build_execution_batches(tasks)
    return DAGResult(
        success=True,
        batches=[DAGBatch(batch_number=i + 1, tasks=b) for i, b in enumerate(batches)],
        total_tasks=len(tasks),
    )


def main():
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
```

### 6.3 Refactor & Final Verification
- Run complete test suite: `uv run pytest`.
- Run linter & formatter: `uv run ruff check src/ tests/ && uv run ruff format src/ tests/`.
- Run type checker: `uv run mypy src/ tests/`.
- All 18 BDD scenarios in `docs/gherkin-scenarios.md` pass 100%.
