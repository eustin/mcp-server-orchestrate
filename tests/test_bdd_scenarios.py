import json
import re
import subprocess
from pathlib import Path
from typing import Any

import pytest
from pytest_bdd import given, parsers, scenarios, then, when

from orchestrator_mcp.models import (
    ApproveResult,
    ArchiveResult,
    DAGResult,
    InitResult,
    StatusResult,
    VerifyResult,
)
from orchestrator_mcp.prompts.complete import COMPLETE_PHASE_PROMPT
from orchestrator_mcp.prompts.design import DESIGN_PHASE_PROMPT
from orchestrator_mcp.prompts.execute import EXECUTE_PHASE_PROMPT
from orchestrator_mcp.prompts.plan import PLAN_PHASE_PROMPT
from orchestrator_mcp.prompts.verify import VERIFY_PHASE_PROMPT
from orchestrator_mcp.server import (
    orchestrate_approve,
    orchestrate_archive,
    orchestrate_get_dag_batches,
    orchestrate_init,
    orchestrate_status,
    orchestrate_verify,
)
from orchestrator_mcp.state import StateManager

# Register all scenarios from features/orchestrator.feature
scenarios("features/orchestrator.feature")


@pytest.fixture
def context() -> dict[str, Any]:
    """Shared context across BDD step executions."""
    return {"last_result": None, "last_error": None}


# ==============================================================================
# BACKGROUND & COMMON GIVEN STEPS
# ==============================================================================


@given("a project workspace directory initialized with Git or OpenCode configuration")
def init_project_workspace(temp_workspace: Path) -> Path:
    return temp_workspace


@given("no active orchestration session exists in workspace")
@given("no active orchestration session exists")
def ensure_no_active_session(temp_workspace: Path) -> None:
    session_json = temp_workspace / ".orchestrator" / "session.json"
    if session_json.exists():
        session_json.unlink()
    session_lock = temp_workspace / ".orchestrator" / "session.lock"
    if session_lock.exists():
        session_lock.unlink()


@given("an active orchestration session")
def ensure_active_session(temp_workspace: Path) -> None:
    orchestrate_init("Active Session", workspace_root=str(temp_workspace))


@given("an active orchestration session exists with running process PID")
def active_session_with_running_pid(temp_workspace: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    orchestrate_init("Active Session PID", workspace_root=str(temp_workspace))
    monkeypatch.setattr("os.kill", lambda pid, sig: None)


@given(parsers.parse('lock file "{lock_path}" exists with PID of a terminated process'))
def stale_lock_terminated_process(
    temp_workspace: Path, lock_path: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    lock_file = temp_workspace / lock_path
    lock_file.parent.mkdir(parents=True, exist_ok=True)
    lock_file.write_text(json.dumps({"session_id": "old-stale-session", "pid": 99999}))

    def raise_lookup(pid: int, sig: int) -> None:
        raise ProcessLookupError

    monkeypatch.setattr("os.kill", raise_lookup)


@given(parsers.parse('an active orchestration session in phase "{phase}"'))
def active_session_in_phase(temp_workspace: Path, phase: str) -> None:
    orchestrate_init(f"Session in {phase}", workspace_root=str(temp_workspace))
    mgr = StateManager(temp_workspace)
    mgr.update_phase(phase)


@given(parsers.parse('an active orchestration session with ID "{session_id}"'))
def active_session_with_id(temp_workspace: Path, session_id: str) -> None:
    mgr = StateManager(temp_workspace)
    state = {
        "session_id": session_id,
        "task_description": "JWT Authentication",
        "current_phase": "DESIGN",
        "current_phase_approved": False,
        "history": [],
    }
    mgr.save_state(state)
    lock_file = temp_workspace / ".orchestrator" / "session.lock"
    lock_file.write_text(json.dumps({"session_id": session_id, "pid": 12345}))


@given('existing files in ".orchestrator/":')
def existing_files_in_orchestrator(temp_workspace: Path, datatable: list[list[str]]) -> None:
    orch_dir = temp_workspace / ".orchestrator"
    orch_dir.mkdir(parents=True, exist_ok=True)
    for row in datatable[1:]:
        filename = row[0]
        file_path = orch_dir / filename
        if not file_path.exists():
            file_path.write_text(f"# Content of {filename}\n")


# ==============================================================================
# TOOL CALLING WHEN STEPS
# ==============================================================================


@when(parsers.parse('client calls tool "orchestrate_init" with:'))
def client_calls_orchestrate_init(
    temp_workspace: Path, context: dict[str, Any], datatable: list[list[str]]
) -> None:
    params: dict[str, str] = {row[0]: row[1] for row in datatable[1:]}
    task_description = params.get("task_description", "Default Task")
    res = orchestrate_init(task_description=task_description, workspace_root=str(temp_workspace))
    context["last_result"] = res


@when('client calls tool "orchestrate_status"')
def client_calls_orchestrate_status(temp_workspace: Path, context: dict[str, Any]) -> None:
    res = orchestrate_status(workspace_root=str(temp_workspace))
    context["last_result"] = res


@when(parsers.parse('client calls tool "orchestrate_archive" with force={force}'))
def client_calls_orchestrate_archive(
    temp_workspace: Path, context: dict[str, Any], force: str
) -> None:
    force_val = force.strip().lower() == "true"
    res = orchestrate_archive(force=force_val, workspace_root=str(temp_workspace))
    context["last_result"] = res


@when('client calls tool "orchestrate_approve"')
def client_calls_orchestrate_approve(temp_workspace: Path, context: dict[str, Any]) -> None:
    res = orchestrate_approve(workspace_root=str(temp_workspace))
    context["last_result"] = res


@when('client calls tool "orchestrate_verify"')
def client_calls_orchestrate_verify(temp_workspace: Path, context: dict[str, Any]) -> None:
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    context["last_result"] = res


@when('client calls tool "orchestrate_get_dag_batches"')
def client_calls_orchestrate_get_dag_batches(temp_workspace: Path, context: dict[str, Any]) -> None:
    res = orchestrate_get_dag_batches(workspace_root=str(temp_workspace))
    context["last_result"] = res


# ==============================================================================
# LIFECYCLE & LOCK THEN STEPS
# ==============================================================================


@then(parsers.parse('server creates atomic lock file "{lock_path}"'))
def verify_lock_file_created(temp_workspace: Path, lock_path: str) -> None:
    assert (temp_workspace / lock_path).exists()


@then(parsers.parse('server creates state file "{state_path}" containing:'))
def verify_state_file_contents(
    temp_workspace: Path, state_path: str, datatable: list[list[str]]
) -> None:
    state_file = temp_workspace / state_path
    assert state_file.exists()
    data = json.loads(state_file.read_text())
    for row in datatable[1:]:
        field, expected = row[0], row[1]
        if expected.lower() == "false":
            assert data.get(field) is False
        elif expected.lower() == "true":
            assert data.get(field) is True
        else:
            assert data.get(field) == expected


@then(parsers.parse('server creates default "{mandates_path}" if not present'))
def verify_mandates_file_created(temp_workspace: Path, mandates_path: str) -> None:
    assert (temp_workspace / mandates_path).exists()


@then('tool output returns session ID, phase "DESIGN", and DESIGN phase SOP instructions')
def verify_init_output_design(context: dict[str, Any]) -> None:
    res: InitResult = context["last_result"]
    assert res.success is True
    assert res.session_id is not None
    assert res.phase == "DESIGN"
    assert res.sop_instructions == DESIGN_PHASE_PROMPT


@then("tool returns lock error with active session ID and PID")
def verify_lock_error_returned(context: dict[str, Any]) -> None:
    res: InitResult = context["last_result"]
    assert res.success is False
    assert res.error is not None
    assert "Active orchestration session" in res.error


@then("instructs user to archive current session before starting a new one")
def verify_archive_instruction(context: dict[str, Any]) -> None:
    res: InitResult = context["last_result"]
    assert res.error is not None
    assert "archive" in res.error.lower()


@then("server automatically cleans up stale lock")
def verify_stale_lock_cleaned(context: dict[str, Any]) -> None:
    # Verified by the new session initialization succeeding
    pass


@then(parsers.parse('initializes new session in "{phase}" phase'))
def verify_new_session_phase(context: dict[str, Any], phase: str) -> None:
    res: InitResult = context["last_result"]
    assert res.success is True
    assert res.phase == phase


@then("server returns high-level status:")
def verify_high_level_status(context: dict[str, Any], datatable: list[list[str]]) -> None:
    res: StatusResult = context["last_result"]
    for row in datatable[1:]:
        field, expected = row[0], row[1]
        if field == "active_session":
            assert res.active_session == (expected.lower() == "true")
        elif field == "phase":
            assert res.phase == expected


@then(parsers.parse('server returns active_session true and phase "{phase}"'))
def verify_active_session_phase(context: dict[str, Any], phase: str) -> None:
    res: StatusResult = context["last_result"]
    assert res.active_session is True
    assert res.phase == phase


@then(parsers.parse('server returns active_session false and message "{message}"'))
def verify_inactive_status_message(context: dict[str, Any], message: str) -> None:
    res: StatusResult = context["last_result"]
    assert res.active_session is False
    assert res.message is not None
    assert message in res.message


@then(parsers.parse('server releases and removes "{lock_path}"'))
def verify_lock_removed(temp_workspace: Path, lock_path: str) -> None:
    assert not (temp_workspace / lock_path).exists()


@then(parsers.parse('moves all session files to "{archive_dest}"'))
def verify_session_files_archived(temp_workspace: Path, archive_dest: str) -> None:
    dest = temp_workspace / archive_dest
    assert dest.exists()
    assert (dest / "session.json").exists()


@then("tool output confirms session archived and lock released")
def verify_archive_confirmation(context: dict[str, Any]) -> None:
    res: ArchiveResult = context["last_result"]
    assert res.success is True
    assert res.message is not None
    assert "archived and lock released" in res.message


# ==============================================================================
# HUMAN APPROVAL GATES GIVEN / THEN STEPS
# ==============================================================================


@given('an active session in phase "DESIGN" with current_phase_approved false')
def active_session_design_unapproved(temp_workspace: Path) -> None:
    orchestrate_init("Design Task", workspace_root=str(temp_workspace))


@then('server sets current_phase_approved to true in ".orchestrator/session.json"')
def verify_phase_approved_flag(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    state = mgr.load_state()
    assert state is not None
    assert state.get("current_phase_approved") is True


@then('appends "phase_approved" event to state history')
def verify_phase_approved_in_history(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    state = mgr.load_state()
    assert state is not None
    history = state.get("history", [])
    assert any(item.get("event") == "phase_approved" for item in history)


@then(parsers.parse('tool output confirms "{expected_message}"'))
def verify_tool_confirms_message(context: dict[str, Any], expected_message: str) -> None:
    res = context["last_result"]
    message = getattr(res, "message", None) or getattr(res, "error", None)
    assert message is not None
    assert expected_message in message


@then('tool returns error "No active session state found."')
def verify_tool_returns_no_session_error(context: dict[str, Any]) -> None:
    res = context["last_result"]
    if isinstance(res, ApproveResult):
        assert res.success is False
        assert res.error == "No active session state found."
    elif isinstance(res, VerifyResult):
        assert res.success is False
        assert "No active session state found." in res.errors


# ==============================================================================
# PHASE VERIFICATION GIVEN / WHEN / THEN STEPS
# ==============================================================================


@given(parsers.parse('an active session in phase "{phase}"'))
def active_session_in_specific_phase(temp_workspace: Path, phase: str) -> None:
    orchestrate_init(f"Task in {phase}", workspace_root=str(temp_workspace))
    mgr = StateManager(temp_workspace)
    mgr.update_phase(phase)


@given('file ".orchestrator/design.md" does not exist')
def ensure_design_md_missing(temp_workspace: Path) -> None:
    design_file = temp_workspace / ".orchestrator" / "design.md"
    if design_file.exists():
        design_file.unlink()


@given('file ".orchestrator/design.md" exists with all required sections')
def ensure_valid_design_md_exists(temp_workspace: Path) -> None:
    design_file = temp_workspace / ".orchestrator" / "design.md"
    design_file.parent.mkdir(parents=True, exist_ok=True)
    design_file.write_text(
        "# Design Document\n\n"
        "## Requirements\n- Requirement 1\n\n"
        "## Architecture\n- Architecture specs\n\n"
        "## Self-Confidence Audit\n- 100% confidence score\n"
    )


@given("current_phase_approved is false")
def ensure_current_phase_unapproved(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    state = mgr.load_state()
    if state:
        state["current_phase_approved"] = False
        mgr.save_state(state)


@given('an active session in phase "DESIGN" with current_phase_approved true')
def active_session_design_approved(temp_workspace: Path) -> None:
    orchestrate_init("Design Task", workspace_root=str(temp_workspace))
    orchestrate_approve(workspace_root=str(temp_workspace))


@given('file ".orchestrator/design.md" lacks "## Self-Confidence Audit"')
def ensure_design_md_lacks_audit(temp_workspace: Path) -> None:
    design_file = temp_workspace / ".orchestrator" / "design.md"
    design_file.parent.mkdir(parents=True, exist_ok=True)
    design_file.write_text(
        "# Design Document\n\n## Requirements\n- Req 1\n\n## Architecture\n- Arch 1\n"
    )


@given('file ".orchestrator/design.md" contains sections:')
def ensure_design_md_contains_sections(temp_workspace: Path, datatable: list[list[str]]) -> None:
    design_file = temp_workspace / ".orchestrator" / "design.md"
    design_file.parent.mkdir(parents=True, exist_ok=True)
    sections = [f"{row[0]}\nSection content here.\n" for row in datatable[1:]]
    design_file.write_text("# Design Document\n\n" + "\n".join(sections))


@then("verification fails with error:")
def verify_verification_fails_with_docstring(context: dict[str, Any], docstring: str) -> None:
    res: VerifyResult = context["last_result"]
    assert res.success is False
    expected = docstring.strip()
    assert any(expected in err or err in expected for err in res.errors)


@then(parsers.parse('session phase remains "{phase}"'))
def verify_session_phase_remains(context: dict[str, Any], phase: str) -> None:
    res: VerifyResult = context["last_result"]
    assert res.phase == phase


@then("verification succeeds")
def verify_verification_succeeds(context: dict[str, Any]) -> None:
    res: VerifyResult = context["last_result"]
    assert res.success is True


@then(parsers.parse('server advances current_phase to "{phase}"'))
def verify_phase_advancement(context: dict[str, Any], phase: str) -> None:
    res: VerifyResult = context["last_result"]
    assert res.phase == phase


@then("resets current_phase_approved to false")
def verify_approval_reset(temp_workspace: Path) -> None:
    mgr = StateManager(temp_workspace)
    state = mgr.load_state()
    assert state is not None
    assert state.get("current_phase_approved") is False


@then("tool output returns PLAN phase SOP instructions")
def verify_plan_phase_sop_returned(context: dict[str, Any]) -> None:
    res: VerifyResult = context["last_result"]
    assert res.next_sop_instructions == PLAN_PHASE_PROMPT


@given('file ".orchestrator/plan.md" does not exist')
def ensure_plan_md_missing(temp_workspace: Path) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    if plan_file.exists():
        plan_file.unlink()


@then(parsers.parse('verification fails with error "{error_msg}"'))
def verify_verification_fails_with_error_string(context: dict[str, Any], error_msg: str) -> None:
    res: VerifyResult = context["last_result"]
    assert res.success is False
    assert any(error_msg in err for err in res.errors)


@given('file ".orchestrator/plan.md" exists and has valid structure')
def ensure_valid_plan_md_exists(temp_workspace: Path) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        "## Tasks\n"
        "- [ ] **task-1**: Step 1 (Agent: backend-specialist) (Target: src/t1.py) (blocked_by: [])\n"
        "- [ ] **task-2**: Final Review (Agent: implementation-reviewer) (Target: src/t1.py) (blocked_by: [task-1])\n\n"
        "## Detailed Task Specifications\n"
        "### task-1\nStep 1 spec.\n"
        "### task-2\nReview spec.\n\n"
        "## Verification\n"
        "Test command: pytest\n"
    )


@given('an active session in phase "PLAN" with current_phase_approved true')
def active_session_plan_approved(temp_workspace: Path) -> None:
    orchestrate_init("Plan Task", workspace_root=str(temp_workspace))
    mgr = StateManager(temp_workspace)
    mgr.update_phase("PLAN")
    orchestrate_approve(workspace_root=str(temp_workspace))


@when(
    'file ".orchestrator/plan.md" has task checkbox missing "(Agent: <role>)" or "(Target: <path>)" or "(blocked_by: <deps>)"'
)
def plan_md_has_invalid_task_tags(temp_workspace: Path, context: dict[str, Any]) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        "## Tasks\n"
        "- [ ] **task-1**: Invalid Task Without Tags\n\n"
        "## Detailed Task Specifications\n"
        "### task-1\n\n"
        "## Verification\n"
        "Test command: pytest\n"
    )
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    context["last_result"] = res


@then("verification fails listing specific task format violations")
def verify_format_violations(context: dict[str, Any]) -> None:
    res: VerifyResult = context["last_result"]
    assert res.success is False
    assert any("missing required" in err.lower() for err in res.errors)


@when('last task in ".orchestrator/plan.md" is not assigned to "Agent: implementation-reviewer"')
def plan_md_missing_barrier_task(temp_workspace: Path, context: dict[str, Any]) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        "## Tasks\n"
        "- [ ] **task-1**: Step 1 (Agent: backend-specialist) (Target: src/t1.py) (blocked_by: [])\n\n"
        "## Detailed Task Specifications\n"
        "### task-1\n\n"
        "## Verification\n"
        "Test command: pytest\n"
    )
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    context["last_result"] = res


@when('".orchestrator/plan.md" has "Test command: None" or missing test command')
def plan_md_has_none_test_command(temp_workspace: Path, context: dict[str, Any]) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        "## Tasks\n"
        "- [ ] **task-1**: Step 1 (Agent: backend-specialist) (Target: src/t1.py) (blocked_by: [])\n"
        "- [ ] **task-2**: Final Review (Agent: implementation-reviewer) (Target: src/t1.py) (blocked_by: [task-1])\n\n"
        "## Detailed Task Specifications\n"
        "### task-1\n"
        "### task-2\n\n"
        "## Verification\n"
        "Test command: None\n"
    )
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    context["last_result"] = res


@given('file ".orchestrator/plan.md" satisfies all schema, barrier, and test command rules')
def ensure_plan_md_fully_valid(temp_workspace: Path) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        "## Tasks\n"
        "- [ ] **task-1**: Implement feature (Agent: coder) (Target: src/auth/jwt.py) (blocked_by: [])\n"
        "- [ ] **task-2**: Final Review (Agent: implementation-reviewer) (Target: src/auth/jwt.py) (blocked_by: [task-1])\n\n"
        "## Detailed Task Specifications\n"
        "### task-1\nImplement.\n"
        "### task-2\nReview.\n\n"
        "## Verification\n"
        "Test command: pytest tests/test_auth.py\n"
    )


@then("tool output returns EXECUTE phase delegation rules")
def verify_execute_phase_sop_returned(context: dict[str, Any]) -> None:
    res: VerifyResult = context["last_result"]
    assert res.next_sop_instructions == EXECUTE_PHASE_PROMPT


@given(parsers.parse('file ".orchestrator/plan.md" contains unchecked item "{unchecked_item}"'))
def plan_md_with_unchecked_item(temp_workspace: Path, unchecked_item: str) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        f"## Tasks\n"
        f"{unchecked_item} (Agent: coder) (Target: src/auth/jwt.py) (blocked_by: [])\n"
        f"- [ ] **task-2**: Review (Agent: implementation-reviewer) (Target: src/auth/jwt.py) (blocked_by: [task-1])\n\n"
        f"## Detailed Task Specifications\n"
        f"### task-1\n\n"
        f"## Verification\n"
        f"Test command: pytest\n"
    )


@then("verification fails with error indicating unfinished tasks")
def verify_unfinished_tasks_error(context: dict[str, Any]) -> None:
    res: VerifyResult = context["last_result"]
    assert res.success is False
    assert any("UNFINISHED TASK" in err for err in res.errors)


@given('all tasks in ".orchestrator/plan.md" are marked checked "- [x]"')
def all_tasks_marked_checked(temp_workspace: Path) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    if plan_file.exists():
        content = plan_file.read_text().replace("- [ ]", "- [x]")
    else:
        content = (
            "## Tasks\n"
            "- [x] **task-1**: Step 1 (Agent: coder) (Target: src/auth/jwt.py) (blocked_by: [])\n"
            "- [x] **task-2**: Review (Agent: implementation-reviewer) (Target: src/auth/jwt.py) (blocked_by: [task-1])\n\n"
            "## Detailed Task Specifications\n"
            "### task-1\n"
            "### task-2\n\n"
            "## Verification\n"
            "Test command: pytest tests/test_auth.py\n"
        )
    plan_file.write_text(content)


@given(parsers.parse('target file "{target_path}" does not exist or has 0 bytes'))
def target_file_missing_or_empty(temp_workspace: Path, target_path: str) -> None:
    target = temp_workspace / target_path
    if target.exists():
        target.unlink()


@then("verification fails with error identifying missing or 0-byte target file")
def verify_target_missing_error(context: dict[str, Any]) -> None:
    res: VerifyResult = context["last_result"]
    assert res.success is False
    assert any(
        "does not exist" in err.lower() or "0 bytes" in err.lower() or "empty" in err.lower()
        for err in res.errors
    )


@given("all target files exist and are non-empty")
def all_target_files_exist(temp_workspace: Path) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    if plan_file.exists():
        content = plan_file.read_text()
        matches = re.findall(r"(?:, |\()Target:\s*([^,)]+)", content)
        for target in matches:
            tpath = temp_workspace / target.strip()
            tpath.parent.mkdir(parents=True, exist_ok=True)
            tpath.write_text(f"# Implementation for {target}\n")


@then("tool output returns VERIFY phase instructions")
def verify_verify_phase_sop_returned(context: dict[str, Any]) -> None:
    res: VerifyResult = context["last_result"]
    assert res.next_sop_instructions == VERIFY_PHASE_PROMPT


@given(parsers.parse('plan specifies test command "{cmd}"'))
def plan_specifies_test_command(temp_workspace: Path, cmd: str) -> None:
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)
    plan_file.write_text(
        f"## Tasks\n"
        f"- [x] **task-1**: Step 1 (Agent: coder) (Target: src/auth/jwt.py) (blocked_by: [])\n"
        f"- [x] **task-2**: Review (Agent: implementation-reviewer) (Target: src/auth/jwt.py) (blocked_by: [task-1])\n\n"
        f"## Detailed Task Specifications\n"
        f"### task-1\n"
        f"### task-2\n\n"
        f"## Verification\n"
        f"Test command: {cmd}\n"
    )
    # Ensure target files exist
    target = temp_workspace / "src" / "auth" / "jwt.py"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("# jwt auth\n")


@when("test command execution exits with non-zero exit code")
def test_execution_exits_nonzero(
    temp_workspace: Path, context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def mock_subprocess_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=1,
            stdout="FAILED tests/test_auth.py\n",
            stderr="AssertionError: Auth failed\n",
        )

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    context["last_result"] = res


@then("verification fails returning test runner stdout and stderr tail")
def verify_test_failure_output(context: dict[str, Any]) -> None:
    res: VerifyResult = context["last_result"]
    assert res.success is False
    assert any("test runner failed" in err.lower() or "failed" in err.lower() for err in res.errors)


@when("test command execution exits with exit code 0")
def test_execution_exits_zero(
    temp_workspace: Path, context: dict[str, Any], monkeypatch: pytest.MonkeyPatch
) -> None:
    def mock_subprocess_run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            args=args[0],
            returncode=0,
            stdout="1 passed in 0.01s\n",
            stderr="",
        )

    monkeypatch.setattr("subprocess.run", mock_subprocess_run)
    res = orchestrate_verify(workspace_root=str(temp_workspace))
    context["last_result"] = res


@then("tool output returns COMPLETE phase summary and archive prompt")
def verify_complete_phase_sop_returned(context: dict[str, Any]) -> None:
    res: VerifyResult = context["last_result"]
    assert res.next_sop_instructions == COMPLETE_PHASE_PROMPT


# ==============================================================================
# DAG SCHEDULING GIVEN / THEN STEPS
# ==============================================================================


@given(parsers.parse('".orchestrator/plan.md" defines tasks:'))
def plan_md_defines_dag_tasks(temp_workspace: Path, datatable: list[list[str]]) -> None:
    orchestrate_init("DAG Session", workspace_root=str(temp_workspace))
    plan_file = temp_workspace / ".orchestrator" / "plan.md"
    plan_file.parent.mkdir(parents=True, exist_ok=True)

    task_lines = []
    spec_lines = []
    for row in datatable[1:]:
        task_id, target, blocked_by = row[0], row[1], row[2]
        task_lines.append(
            f"- [ ] **{task_id}**: Task {task_id} (Agent: dev) (Target: {target}) (blocked_by: {blocked_by})"
        )
        spec_lines.append(f"### {task_id}\nSpecification for {task_id}.")

    content = (
        "## Tasks\n"
        + "\n".join(task_lines)
        + "\n\n## Detailed Task Specifications\n"
        + "\n".join(spec_lines)
        + "\n\n## Verification\nTest command: pytest\n"
    )
    plan_file.write_text(content)


@then(parsers.parse("server returns {count:d} execution batches:"))
def verify_dag_batches(context: dict[str, Any], count: int, datatable: list[list[str]]) -> None:
    res: DAGResult = context["last_result"]
    assert res.success is True
    assert len(res.batches) == count

    for row in datatable[1:]:
        batch_idx = int(row[0]) - 1
        raw_ids = row[1]
        # Parse [T1, T2] into list of strings
        expected_ids = [item.strip() for item in raw_ids.strip("[]").split(",") if item.strip()]
        actual_ids = [t["id"] for t in res.batches[batch_idx].tasks]
        assert sorted(actual_ids) == sorted(expected_ids)


@then("server applies file collision guard")
def verify_collision_guard_applied(context: dict[str, Any]) -> None:
    res: DAGResult = context["last_result"]
    assert res.success is True


@then("serializes T2 behind T1 across distinct batches:")
def verify_serialized_batches(context: dict[str, Any], datatable: list[list[str]]) -> None:
    res: DAGResult = context["last_result"]
    assert res.success is True
    for row in datatable[1:]:
        batch_idx = int(row[0]) - 1
        raw_ids = row[1]
        expected_ids = [item.strip() for item in raw_ids.strip("[]").split(",") if item.strip()]
        actual_ids = [t["id"] for t in res.batches[batch_idx].tasks]
        assert actual_ids == expected_ids
