import os
from pathlib import Path

import pytest

from orchestrate_mcp.config import get_orchestrator_dir, resolve_workspace_root
from orchestrate_mcp.models import (
    ApproveResult,
    ArchiveResult,
    DAGBatch,
    DAGResult,
    InitResult,
    StatusResult,
    VerifyResult,
)


def test_temp_workspace_fixture(temp_workspace: Path) -> None:
    assert temp_workspace.exists()
    assert (temp_workspace / ".git").exists()
    assert (temp_workspace / ".orchestrator").exists()


def test_mock_alive_pid(mock_alive_pid: None) -> None:
    # Should not raise
    os.kill(99999, 0)


def test_mock_dead_pid(mock_dead_pid: None) -> None:
    with pytest.raises(ProcessLookupError):
        os.kill(99999, 0)


def test_config_resolution(temp_workspace: Path) -> None:
    sub_dir = temp_workspace / "sub" / "dir"
    sub_dir.mkdir(parents=True)
    root = resolve_workspace_root(sub_dir)
    assert root == temp_workspace
    orch = get_orchestrator_dir(root)
    assert orch == temp_workspace / ".orchestrator"
    assert orch.exists()


def test_models_instantiation() -> None:
    init_res = InitResult(success=True, session_id="test-id", phase="DESIGN")
    assert init_res.success is True

    status_res = StatusResult(active_session=True, phase="PLAN", message="ok")
    assert status_res.phase == "PLAN"

    approve_res = ApproveResult(success=True, phase="DESIGN")
    assert approve_res.success is True

    verify_res = VerifyResult(success=True, phase="PLAN", previous_phase="DESIGN")
    assert verify_res.phase == "PLAN"

    archive_res = ArchiveResult(success=True, archived_session_id="arch-1")
    assert archive_res.archived_session_id == "arch-1"

    dag_batch = DAGBatch(batch_number=1, tasks=[{"id": "T1"}])
    dag_res = DAGResult(success=True, batches=[dag_batch], total_tasks=1)
    assert dag_res.total_tasks == 1
