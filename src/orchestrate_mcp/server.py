import json

from mcp.server.mcpserver import MCPServer

from .agents import CONCRETE_AGENTS
from .config import resolve_workspace_root
from .dag import DAGScheduler
from .lock import LockError, SessionLockManager
from .models import (
    AgentListResult,
    AgentSummary,
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
from .state import StateManager
from .verifier import VerificationEngine

mcp = MCPServer("orchestrate-mcp")

DEFAULT_PROJECT_MANDATES = """# Critical Project Mandates

ALL agents MUST obey these rules. They override conflicting instructions.

## No Silent Fallbacks
- NEVER return sentinel or fabricated values (0.5, 0.0, "unknown", "N/A") when data is missing.
- NEVER use default argument fallbacks (getattr(x, "y", 0.005), x or 100) that fabricate data.
- NEVER hardcode magic strings that should come from actual pipeline config ("ewma", "yang_zhang").
- ALWAYS raise when required data is unavailable or cannot be determined truthfully.
"""


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
def orchestrate_init(task_description: str) -> InitResult:
    """Initialize a new orchestration session."""
    root = resolve_workspace_root()
    lock_mgr = SessionLockManager(root)
    state_mgr = StateManager(root)

    try:
        # Pre-check active lock before mutating state
        if lock_mgr.lock_file.exists():
            try:
                lock_data = json.loads(lock_mgr.lock_file.read_text())
                pid = lock_data.get("pid", 0)
                if lock_mgr.is_process_alive(pid):
                    return InitResult(
                        success=False,
                        error=f"Active orchestration session '{lock_data.get('session_id')}' in progress (PID {pid}). "
                        "Run orchestrate_archive to release lock.",
                    )
                # Stale lock from dead PID: auto-archive prior session
                lock_mgr.force_archive()
            except (json.JSONDecodeError, OSError):
                lock_mgr.release_lock(force=True)
        elif state_mgr.state_file.exists():
            # Stale unarchived session left on disk without lock
            lock_mgr.force_archive()

        # Generate session ID and acquire atomic lock FIRST
        session_id = state_mgr.generate_session_id(task_description)
        lock_mgr.acquire_lock(session_id)

        # State is only written after lock acquisition succeeds
        state = state_mgr.init_session(task_description, session_id=session_id)
        mandates_file = root / ".orchestrator" / "project-mandates.md"
        if not mandates_file.exists():
            mandates_file.write_text(DEFAULT_PROJECT_MANDATES, encoding="utf-8")
        return InitResult(
            success=True,
            session_id=state["session_id"],
            phase="DESIGN",
            sop_instructions=DESIGN_PHASE_PROMPT,
        )
    except LockError as e:
        return InitResult(success=False, error=str(e))
    except Exception as e:  # noqa: BLE001
        return InitResult(success=False, error=f"Internal Error: {e!s}")


@mcp.tool()
def orchestrate_status() -> StatusResult:
    """Query current session status and active phase."""
    root = resolve_workspace_root()
    state_mgr = StateManager(root)
    state = state_mgr.load_state()
    if not state:
        return StatusResult(active_session=False, message="No active orchestration session")
    return StatusResult(
        active_session=True,
        phase=state.get("current_phase"),
        message="Active session in progress",
    )


@mcp.tool()
def orchestrate_approve() -> ApproveResult:
    """Grant human approval for the current phase deliverable."""
    root = resolve_workspace_root()
    state_mgr = StateManager(root)
    state = state_mgr.load_state()
    if not state:
        return ApproveResult(success=False, error="No active session state found.")

    updated = state_mgr.approve_current_phase()
    phase = updated.get("current_phase")
    return ApproveResult(
        success=True,
        phase=phase,
        message=f"Phase '{phase}' approved by user. Machine verification is now enabled.",
    )


@mcp.tool()
def orchestrate_verify() -> VerifyResult:
    """Run machine verification on current phase deliverables and advance phase on success."""
    root = resolve_workspace_root()
    state_mgr = StateManager(root)
    state = state_mgr.load_state()
    if not state:
        return VerifyResult(
            success=False, phase="UNKNOWN", errors=["No active session state found."]
        )

    phase = state.get("current_phase", "DESIGN")
    is_approved = state.get("current_phase_approved", False)
    valid: bool = False
    errors: list[str] = []

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
    new_phase = (new_state.get("current_phase") if new_state else phase) or "UNKNOWN"
    return VerifyResult(
        success=valid,
        phase=new_phase,
        previous_phase=phase if valid else None,
        next_sop_instructions=get_phase_prompt(new_phase) if valid else None,
        errors=errors,
    )


@mcp.tool()
def orchestrate_archive(force: bool = True) -> ArchiveResult:
    """Archive current orchestration deliverables and release session lock."""
    root = resolve_workspace_root()
    lock_mgr = SessionLockManager(root)
    res = lock_mgr.force_archive()
    archived_id = res.get("archived_session_id")
    return ArchiveResult(
        success=res.get("success", False),
        archived_session_id=archived_id,
        message=f"Session '{archived_id}' archived and lock released.",
    )


@mcp.tool()
def orchestrate_get_dag_batches() -> DAGResult:
    """Compute topological execution batches from plan.md tasks."""
    root = resolve_workspace_root()
    state_mgr = StateManager(root)
    try:
        tasks = state_mgr.parse_plan_tasks()
        batches = DAGScheduler.build_execution_batches(tasks)
        return DAGResult(
            success=True,
            batches=[DAGBatch(batch_number=i + 1, tasks=b) for i, b in enumerate(batches)],
            total_tasks=len(tasks),
        )
    except Exception as e:  # noqa: BLE001
        return DAGResult(success=False, error=str(e))


@mcp.tool()
def orchestrate_get_agents() -> AgentListResult:
    """List all specialized orchestrate agent personas. Each `name` is a registered OpenCode subagent ID, spawnable by name via the `subagent` tool even if hidden from the advertised subagent catalog."""
    summaries = [
        AgentSummary(name=name, role=info["role"], description=info["description"])
        for name, info in CONCRETE_AGENTS.items()
    ]
    return AgentListResult(success=True, agents=summaries)


def main() -> None:
    """MCP Server entrypoint."""
    mcp.run(transport="stdio")


if __name__ == "__main__":
    main()
