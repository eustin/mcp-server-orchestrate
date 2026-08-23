# Orchestrator Python MCP Server

Machine-verified 4-phase workflow MCP server for AI coding assistants. Enforces **DESIGN → PLAN → EXECUTE → VERIFY → COMPLETE** with human approval gates, state integrity checks, and DAG task scheduling.

---

## 🚀 Workflow Lifecycle

```
[Start] ──> orchestrate_init(task="...")
                │
                ▼ (DESIGN Phase)
        Write `.orchestrator/design.md`
                │
                ▼
        orchestrate_approve()  ──>  orchestrate_verify()
                                        │
                ┌───────────────────────┘
                ▼ (PLAN Phase)
        Write `.orchestrator/plan.md`
                │
                ▼
        orchestrate_approve()  ──>  orchestrate_verify()
                                        │
                ┌───────────────────────┘
                ▼ (EXECUTE Phase)
        orchestrate_get_dag_batches()
        Subagents implement tasks & mark [x]
                │
                ▼
        orchestrate_verify()
                │
                ▼ (VERIFY Phase)
        orchestrate_verify() (runs automated test command)
                │
                ▼ (COMPLETE Phase)
        orchestrate_archive() ──> [Done]
```

---

## 🛠️ MCP Tools Reference

| Tool Name | Parameters | Description |
|---|---|---|
| `orchestrate_init` | `task_description: str` | Initializes new session in `DESIGN` phase, acquires atomic lock, returns initial SOP prompt. |
| `orchestrate_status` | *(none)* | Returns `{ active_session: bool, phase: str, message: str }`. |
| `orchestrate_approve` | *(none)* | Human gate approval. Unlocks verification for `DESIGN` and `PLAN` phases. |
| `orchestrate_verify` | *(none)* | Validates phase deliverables. Advances to next phase on pass, returns next SOP prompt. |
| `orchestrate_get_dag_batches` | *(none)* | Parses `plan.md` tasks and returns ordered parallel batches with file collision guard. |
| `orchestrate_archive` | `force: bool = True` | Releases lock and moves session files into `.orchestrator/archive/<session_id>/`. |

---

## 📋 Deliverable Requirements per Phase

1. **DESIGN Phase**:
   - Deliverable: `.orchestrator/design.md`
   - Required Headings: `## Requirements`, `## Architecture`, `## Self-Confidence Audit`.
   - Gate: Requires `orchestrate_approve` before verification.

2. **PLAN Phase**:
   - Deliverable: `.orchestrator/plan.md`
   - Tasks Schema: `- [ ] **<id>**: <desc> (Agent: <role>) (Target: <file>) (blocked_by: [<deps>])`
   - Detailed Specs: `### <id>` section for every task.
   - Final Barrier: Final task MUST be assigned to `Agent: implementation-reviewer` blocked by all prior tasks.
   - Test Command: Valid executable `Test command: <cmd>` under `## Verification`.
   - Gate: Requires `orchestrate_approve` before verification.

3. **EXECUTE Phase**:
   - Rule: All tasks in `.orchestrator/plan.md` marked checked `- [x]`.
   - Rule: Target files must exist on disk and have size > 0 bytes.

4. **VERIFY Phase**:
   - Rule: Runs plan's test command via shell subprocess (120s timeout). Passes if exit code is 0.

---

## ⚡ Quickstart

### Installation & Run

```bash
# Sync environment
uv sync

# Run tests (Unit + 18 BDD Scenarios)
uv run pytest

# Start MCP server (stdio transport)
uv run python -m orchestrator_mcp.server
```

### OpenCode MCP Configuration (`opencode.json`)

```json
{
  "mcpServers": {
    "orchestrator": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/orchestrate", "python", "-m", "orchestrator_mcp.server"]
    }
  }
}
```
