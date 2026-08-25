import json
from pathlib import Path
from unittest.mock import patch

import pytest

from orchestrate_mcp.models import (
    AgentListResult,
    AgentSummary,
    ApproveResult,
    ArchiveResult,
    DAGResult,
    InitResult,
    StatusResult,
    VerifyResult,
)
from orchestrate_mcp.prompts.complete import COMPLETE_PHASE_PROMPT
from orchestrate_mcp.prompts.design import DESIGN_PHASE_PROMPT
from orchestrate_mcp.prompts.execute import EXECUTE_PHASE_PROMPT
from orchestrate_mcp.prompts.plan import PLAN_PHASE_PROMPT
from orchestrate_mcp.prompts.verify import VERIFY_PHASE_PROMPT
from orchestrate_mcp.server import (
    get_phase_prompt,
    main,
    orchestrate_approve,
    orchestrate_archive,
    orchestrate_get_agents,
    orchestrate_get_dag_batches,
    orchestrate_init,
    orchestrate_status,
    orchestrate_verify,
)
from orchestrate_mcp.state import StateCorruptError, StateManager


def test_get_phase_prompt() -> None:
    assert get_phase_prompt("DESIGN") == DESIGN_PHASE_PROMPT
    assert get_phase_prompt("PLAN") == PLAN_PHASE_PROMPT
    assert get_phase_prompt("EXECUTE") == EXECUTE_PHASE_PROMPT
    assert get_phase_prompt("VERIFY") == VERIFY_PHASE_PROMPT
    assert get_phase_prompt("COMPLETE") == COMPLETE_PHASE_PROMPT
    assert get_phase_prompt("UNKNOWN") == ""


def test_orchestrate_init_success(temp_workspace: Path) -> None:
    res = orchestrate_init("Add JWT Authentication", workspace_root=str(temp_workspace))
    assert isinstance(res, InitResult)
    assert res.success is True
    assert res.phase == "DESIGN"
    assert res.session_id is not None
    assert "jwt-authentication" in res.session_id
    assert res.sop_instructions == DESIGN_PHASE_PROMPT

    lock_file = temp_workspace / ".orchestrator" / "session.lock"
    assert lock_file.exists()

    state_file = temp_workspace / ".orchestrator" / "session.json"
    assert state_file.exists()

    mandates_file = temp_workspace / ".orchestrator" / "project-mandates.md"
    assert mandates_file.exists()
    mandates_content = mandates_file.read_text()
    assert "Critical Project Mandates" in mandates_content
    assert "No Silent Fallbacks" in mandates_content
    assert "NEVER return sentinel or fabricated values" in mandates_content


def test_orchestrate_get_agents() -> None:
    res = orchestrate_get_agents()
    assert isinstance(res, AgentListResult)
    assert res.success is True
    assert len(res.agents) == 12
    agent_names = [a.name for a in res.agents]
    assert "architect" in agent_names
    assert "implementation-reviewer" in agent_names
    for agent in res.agents:
        assert isinstance(agent, AgentSummary)
        assert agent.name.strip() != ""
        assert agent.role.strip() != ""
        assert agent.description.strip() != ""


def test_orchestrate_init_concurrent_lock_failure(
    temp_workspace: Path, mock_alive_pid: None
) -> None:
    res1 = orchestrate_init("Task 1", workspace_root=str(temp_workspace))
    assert res1.success is True

    res2 = orchestrate_init("Task 2", workspace_root=str(temp_workspace))
    assert res2.success is False
    assert res2.error is not None
    assert "Active orchestration session" in res2.error


def test_orchestrate_init_does_not_corrupt_state_on_live_lock_failure(
    temp_workspace: Path, mock_alive_pid: None
) -> None:
    res1 = orchestrate_init("Task 1", workspace_root=str(temp_workspace))
    assert res1.success is True
    original_session_id = res1.session_id

    res2 = orchestrate_init("Task 2", workspace_root=str(temp_workspace))
    assert res2.success is False
    assert res2.error is not None
    assert "Active orchestration session" in res2.error

    state_file = temp_workspace / ".orchestrator" / "session.json"
    state_data = json.loads(state_file.read_text())
    assert state_data["session_id"] == original_session_id
    assert state_data["task_description"] == "Task 1"


def test_orchestrate_init_reclaims_stale_lock(temp_workspace: Path, mock_dead_pid: None) -> None:
    lock_file = temp_workspace / ".orchestrator" / "session.lock"
    lock_file.write_text(json.dumps({"session_id": "old-session", "pid": 99999}))

    res = orchestrate_init("Resume Work", workspace_root=str(temp_workspace))
    assert res.success is True
    assert res.phase == "DESIGN"


def test_orchestrate_init_archives_stale_session_on_dead_pid(
    temp_workspace: Path, mock_dead_pid: None
) -> None:
    state_mgr = StateManager(temp_workspace)
    old_state = state_mgr.init_session("Old Dead Task")
    old_session_id = old_state["session_id"]

    lock_file = temp_workspace / ".orchestrator" / "session.lock"
    lock_file.write_text(json.dumps({"session_id": old_session_id, "pid": 88888}))

    design_file = temp_workspace / ".orchestrator" / "design.md"
    design_file.write_text("# Old Design Doc\n")

    res = orchestrate_init("Fresh New Task", workspace_root=str(temp_workspace))
    assert res.success is True
    assert res.session_id != old_session_id

    archive_dir = temp_workspace / ".orchestrator" / "archive" / old_session_id
    assert (archive_dir / "session.json").exists()
    assert (archive_dir / "design.md").exists()

    new_state = state_mgr.load_state()
    assert new_state is not None
    assert new_state["session_id"] == res.session_id
    assert new_state["task_description"] == "Fresh New Task"


def test_orchestrate_status_no_session(temp_workspace: Path) -> None:
    res = orchestrate_status(workspace_root=str(temp_workspace))
    assert isinstance(res, StatusResult)
    assert res.active_session is False
    assert res.phase is None
    assert "No active orchestration session" in res.message


def test_orchestrate_status_active_session(temp_workspace: Path) -> None:
    orchestrate_init("Status Test", workspace_root=str(temp_workspace))
    res = orchestrate_status(workspace_root=str(temp_workspace))
    assert res.active_session is True
    assert res.phase == "DESIGN"


def test_orchestrate_status_corrupt_state_surfaces_error(temp_workspace: Path) -> None:
    orchestrate_init("Corrupt Test", workspace_root=str(temp_workspace))
    state_file = temp_workspace / ".orchestrator" / "session.json"
    state_file.write_text("{ not valid json ")

    with pytest.raises(StateCorruptError):
        orchestrate_status(workspace_root=str(temp_workspace))


def test_orchestrate_approve_no_session(temp_workspace: Path) -> None:
    res = orchestrate_approve(workspace_root=str(temp_workspace))
    assert isinstance(res, ApproveResult)
    assert res.success is False
    assert res.error == "No active session state found."


def test_orchestrate_approve_success(temp_workspace: Path) -> None:
    orchestrate_init("Approve Test", workspace_root=str(temp_workspace))
    res = orchestrate_approve(workspace_root=str(temp_workspace))
    assert res.success is True
    assert res.phase == "DESIGN"
    assert res.message == "Phase 'DESIGN' approved by user. Machine verification is now enabled."

    mgr = StateManager(temp_workspace)
    state = mgr.load_state()
    assert state is not None
    assert state["current_phase_approved"] is True
    assert state["history"][-1]["event"] == "phase_approved"


def test_orchestrate_verify_no_session(temp_workspace: Path) -> None:
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert isinstance(res, VerifyResult)
    assert res.success is False
    assert res.phase == "UNKNOWN"
    assert "No active session state found." in res.errors


def test_orchestrate_verify_design_lifecycle(temp_workspace: Path) -> None:
    orchestrate_init("Design Lifecycle", workspace_root=str(temp_workspace))

    # Without design.md and approval
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is False
    assert res.phase == "DESIGN"
    assert any("Missing required deliverable" in e for e in res.errors)

    # Create design.md without approval
    design_file = temp_workspace / ".orchestrator" / "design.md"
    design_file.write_text(
        "# Design Doc\n\n## Requirements\nReqs\n\n## Architecture\nArch\n\n## Self-Confidence Audit\nAudit\n"
    )
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is False
    assert any("GATE BLOCKED" in e for e in res.errors)

    # Approve and verify again
    orchestrate_approve(workspace_root=str(temp_workspace))
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is True
    assert res.phase == "PLAN"
    assert res.previous_phase == "DESIGN"
    assert res.next_sop_instructions == PLAN_PHASE_PROMPT


def test_orchestrate_verify_plan_and_execute_and_testing_lifecycle(
    temp_workspace: Path,
) -> None:
    orchestrate_init("Full Lifecycle", workspace_root=str(temp_workspace))

    # Setup design and approve
    (temp_workspace / ".orchestrator" / "design.md").write_text(
        "## Requirements\n## Architecture\n## Self-Confidence Audit\n"
    )
    orchestrate_approve(workspace_root=str(temp_workspace))
    orchestrate_verify(workspace_root=str(temp_workspace))

    # In PLAN phase
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_content = """## Tasks
- [ ] **task-1**: Setup db (Agent: db-specialist) (Target: src/db.py) (blocked_by: [])
- [ ] **task-2**: Final Review (Agent: implementation-reviewer) (Target: src/db.py) (blocked_by: [task-1])

## Detailed Task Specifications
### task-1
Setup db.
### task-2
Final review.

## Verification
Test command: true
"""
    plan_file.write_text(plan_content)

    # Verify PLAN without approval
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is False
    assert any("GATE BLOCKED" in e for e in res.errors)

    # Approve and verify PLAN
    orchestrate_approve(workspace_root=str(temp_workspace))
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is True
    assert res.phase == "EXECUTE"
    assert res.next_sop_instructions == EXECUTE_PHASE_PROMPT

    # In EXECUTE phase: tasks incomplete
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is False
    assert any("UNFINISHED TASK" in e for e in res.errors)

    # Mark tasks checked but target missing
    completed_plan = plan_content.replace("- [ ]", "- [x]")
    plan_file.write_text(completed_plan)
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is False
    assert any("does not exist" in e for e in res.errors)

    # Create target file
    (temp_workspace / "src").mkdir(parents=True, exist_ok=True)
    (temp_workspace / "src" / "db.py").write_text("print('db ready')\n")

    # Verify EXECUTE phase succeeds -> advances to VERIFY
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is True
    assert res.phase == "VERIFY"
    assert res.next_sop_instructions == VERIFY_PHASE_PROMPT

    # In VERIFY phase: test command runs 'true' -> exit code 0 -> advances to COMPLETE
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is True
    assert res.phase == "COMPLETE"
    assert res.next_sop_instructions == COMPLETE_PHASE_PROMPT

    # In COMPLETE phase: verify returns success
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    assert res.success is True
    assert res.phase == "COMPLETE"


def test_orchestrate_archive(temp_workspace: Path) -> None:
    orchestrate_init("Archive Test", workspace_root=str(temp_workspace))
    (temp_workspace / ".orchestrator" / "design.md").write_text("design")
    (temp_workspace / ".orchestrator" / "plan.md").write_text("plan")

    res = orchestrate_archive(force=True, workspace_root=str(temp_workspace))
    assert isinstance(res, ArchiveResult)
    assert res.success is True
    assert res.archived_session_id is not None
    assert "archive-test" in res.archived_session_id
    assert res.message is not None
    assert "archived and lock released" in res.message

    assert not (temp_workspace / ".orchestrator" / "session.lock").exists()
    assert not (temp_workspace / ".orchestrator" / "session.json").exists()
    assert (
        temp_workspace / ".orchestrator" / "archive" / res.archived_session_id / "session.json"
    ).exists()


def test_orchestrate_get_dag_batches(temp_workspace: Path) -> None:
    orchestrate_init("DAG Test", workspace_root=str(temp_workspace))
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.write_text("""## Tasks
- [ ] **task-1**: Step 1 (Agent: a1) (Target: f1.py) (blocked_by: [])
- [ ] **task-2**: Step 2 (Agent: a2) (Target: f2.py) (blocked_by: [])
- [ ] **task-3**: Review (Agent: implementation-reviewer) (Target: f3.py) (blocked_by: [task-1, task-2])

## Detailed Task Specifications
### task-1
### task-2
### task-3

## Verification
Test command: true
""")

    res = orchestrate_get_dag_batches(workspace_root=str(temp_workspace))
    assert isinstance(res, DAGResult)
    assert res.success is True
    assert res.total_tasks == 3
    assert len(res.batches) == 2
    assert len(res.batches[0].tasks) == 2
    assert len(res.batches[1].tasks) == 1
    assert res.batches[0].tasks[0]["id"] == "task-1"
    assert res.batches[0].tasks[1]["id"] == "task-2"
    assert res.batches[1].tasks[0]["id"] == "task-3"


def test_orchestrate_get_dag_batches_canonical_format(temp_workspace: Path) -> None:
    orchestrate_init("Canonical DAG Test", workspace_root=str(temp_workspace))
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.write_text("""## Tasks
- [ ] **T1**: do A (Agent: coder, Target: src/a.py, blocked_by: [])
- [ ] **T2**: do B (Agent: coder, Target: src/b.py, blocked_by: [T1])
- [ ] **T3**: do C (Agent: implementation-reviewer, Target: src/c.py, blocked_by: [T1, T2])

## Detailed Task Specifications
### T1
### T2
### T3

## Verification
Test command: true
""")

    res = orchestrate_get_dag_batches(workspace_root=str(temp_workspace))
    assert isinstance(res, DAGResult)
    assert res.success is True
    assert res.total_tasks == 3
    assert len(res.batches) == 3
    assert len(res.batches[0].tasks) == 1
    assert res.batches[0].tasks[0]["id"] == "T1"
    assert res.batches[0].tasks[0]["target"] == "src/a.py"
    assert res.batches[0].tasks[0]["agent"] == "coder"
    assert res.batches[0].tasks[0]["blocked_by"] == []

    assert len(res.batches[1].tasks) == 1
    assert res.batches[1].tasks[0]["id"] == "T2"
    assert res.batches[1].tasks[0]["target"] == "src/b.py"
    assert res.batches[1].tasks[0]["agent"] == "coder"
    assert res.batches[1].tasks[0]["blocked_by"] == ["T1"]

    assert len(res.batches[2].tasks) == 1
    assert res.batches[2].tasks[0]["id"] == "T3"
    assert res.batches[2].tasks[0]["target"] == "src/c.py"
    assert res.batches[2].tasks[0]["agent"] == "implementation-reviewer"
    assert res.batches[2].tasks[0]["blocked_by"] == ["T1", "T2"]


def test_orchestrate_get_dag_batches_canonical_collision_guard(temp_workspace: Path) -> None:
    orchestrate_init("Collision Guard Test", workspace_root=str(temp_workspace))
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.write_text("""## Tasks
- [ ] **T1**: Step 1 (Agent: coder, Target: src/auth.py, blocked_by: [])
- [ ] **T2**: Step 2 (Agent: coder, Target: src/auth.py, blocked_by: [])

## Detailed Task Specifications
### T1
### T2

## Verification
Test command: true
""")

    res = orchestrate_get_dag_batches(workspace_root=str(temp_workspace))
    assert isinstance(res, DAGResult)
    assert res.success is True
    assert res.total_tasks == 2
    assert len(res.batches) == 2
    assert [t["id"] for t in res.batches[0].tasks] == ["T1"]
    assert [t["id"] for t in res.batches[1].tasks] == ["T2"]


def test_main_invokes_mcp_run() -> None:
    with patch("orchestrate_mcp.server.mcp.run") as mock_run:
        main()
        mock_run.assert_called_once_with(transport="stdio")
