import json
from pathlib import Path

import pytest

from orchestrator_mcp.state import StateManager, StateTamperError


def test_init_session(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    state = mgr.init_session("Add JWT Authentication")

    assert state["current_phase"] == "DESIGN"
    assert state["current_phase_approved"] is False
    assert state["task_description"] == "Add JWT Authentication"
    assert "session_id" in state
    assert "_hmac" in state
    assert (temp_workspace / ".orchestrator" / "session.json").exists()


def test_hmac_calculation_and_verification(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    state = mgr.init_session("Test Task")
    loaded = mgr.load_state()

    assert loaded is not None
    assert loaded["session_id"] == state["session_id"]
    assert loaded["_hmac"] == mgr.calculate_hmac(loaded)


def test_state_tampering_detection(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    mgr.init_session("Tamper Test")

    state_file = temp_workspace / ".orchestrator" / "session.json"
    data = json.loads(state_file.read_text())
    data["current_phase"] = "PLAN"  # Direct manual tampering without HMAC update
    state_file.write_text(json.dumps(data))

    with pytest.raises(StateTamperError, match="TAMPERING DETECTED"):
        mgr.load_state()


def test_approve_current_phase(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    mgr.init_session("Approval Test")

    updated = mgr.approve_current_phase()
    assert updated["current_phase_approved"] is True
    assert updated["history"][-1]["event"] == "phase_approved"


def test_update_phase(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    mgr.init_session("Phase Transition Test")
    mgr.approve_current_phase()

    updated = mgr.update_phase("PLAN")
    assert updated["current_phase"] == "PLAN"
    assert updated["current_phase_approved"] is False  # Resets on transition
    assert updated["history"][-1]["event"] == "phase_transition"


def test_parse_plan_tasks(temp_workspace: Path) -> None:
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
    assert tasks[0]["agent"] == "coder"
    assert tasks[0]["target"] == "src/models.py"
    assert tasks[0]["blocked_by"] == []
    assert tasks[1]["id"] == "T2"
    assert tasks[1]["checked"] is True
    assert tasks[1]["agent"] == "coder"
    assert tasks[1]["target"] == "src/auth.py"
    assert tasks[1]["blocked_by"] == ["T1"]


def test_parse_plan_tasks_canonical_format(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.write_text(
        "## Tasks\n"
        "- [ ] **T1**: do A (Agent: coder, Target: src/a.py, blocked_by: [])\n"
        "- [ ] **T2**: do B (Agent: coder, Target: src/b.py, blocked_by: [T1, T2])\n"
        "- [x] **T3**: do C (Agent: implementation-reviewer, Target: src/c.py, blocked_by: [T1, T2])\n"
    )

    tasks = mgr.parse_plan_tasks()
    assert len(tasks) == 3
    assert tasks[0]["id"] == "T1"
    assert tasks[0]["agent"] == "coder"
    assert tasks[0]["target"] == "src/a.py"
    assert tasks[0]["blocked_by"] == []

    assert tasks[1]["id"] == "T2"
    assert tasks[1]["agent"] == "coder"
    assert tasks[1]["target"] == "src/b.py"
    assert tasks[1]["blocked_by"] == ["T1", "T2"]

    assert tasks[2]["id"] == "T3"
    assert tasks[2]["checked"] is True
    assert tasks[2]["agent"] == "implementation-reviewer"
    assert tasks[2]["target"] == "src/c.py"
    assert tasks[2]["blocked_by"] == ["T1", "T2"]


def test_parse_plan_tasks_prose_no_false_positive(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.write_text(
        "## Tasks\n"
        "- [ ] **T5**: don't use blocked_by: [X] here (Agent: coder, Target: src/e.py, blocked_by: [T1])\n"
    )

    tasks = mgr.parse_plan_tasks()
    assert len(tasks) == 1
    assert tasks[0]["id"] == "T5"
    assert tasks[0]["agent"] == "coder"
    assert tasks[0]["target"] == "src/e.py"
    assert tasks[0]["blocked_by"] == ["T1"]
