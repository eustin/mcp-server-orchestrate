# Orchestrator Python MCP Server — Architecture & Design Document

## 1. Executive Summary

The **Orchestrator Python MCP Server** ports the 4-phase machine-verified workflow (**DESIGN → PLAN → EXECUTE → VERIFY → COMPLETE**) from the OpenCode plugin architecture to a standardized, transport-agnostic Model Context Protocol (MCP) server.

Instead of intercepting LLM chat streams via plugin hooks, the MCP server exposes deterministic tools and structured outputs that guide AI agents, enforce human approval gates, validate deliverables, schedule task DAGs, and guarantee state integrity via cryptographic signatures.

---

## 2. Architectural Overview

```
                      ┌────────────────────────────────────────────────────────┐
                      │              MCP Client (OpenCode, Claude, etc.)       │
                      └───────────────────────────┬────────────────────────────┘
                                                  │ stdio transport (JSON-RPC)
                                                  ▼
                      ┌────────────────────────────────────────────────────────┐
                      │          orchestrator_mcp.server.MCPServer             │
                      └─────┬──────────────┬──────────────┬──────────────┬─────┘
                            │              │              │              │
        ┌───────────────────┴───┐   ┌──────┴──────┐ ┌─────┴─────┐   ┌───┴─────────────────┐
        ▼                       ▼   ▼             ▼ ▼           ▼   ▼                     ▼
 orchestrate_init    orchestrate_status  orchestrate_approve  orchestrate_verify  orchestrate_archive
 orchestrate_get_dag_batches
        │                       │                 │                 │                     │
        └───────────────────────┼─────────────────┼─────────────────┼─────────────────────┘
                                ▼                 ▼                 ▼
                      ┌────────────────────────────────────────────────────────┐
                      │                  Core Engine Layer                     │
                      │  • StateManager: HMAC anti-tamper & history tracking   │
                      │  • SessionLockManager: Atomic O_CREAT lock & PID check │
                      │  • VerificationEngine: Machine verification AST/regex  │
                      │  • DAGScheduler: Topological batching & collision guard│
                      │  • SOP Prompts: Phase-specific instructions & rules    │
                      └────────────────────────────────────────────────────────┘
```

---

## 3. Package & Directory Layout

```
orchestrate/
├── pyproject.toml                     # Package metadata, uv/hatchling config, dependencies
├── README.md                          # Server documentation & setup guide
├── docs/
│   ├── gherkin-scenarios.md           # BDD behavioral specifications
│   ├── mcp-server-design.md           # This architecture & design document
│   └── tdd-implementation-plan.md     # Test-driven development plan
├── src/
│   └── orchestrator_mcp/
│       ├── __init__.py                # Package exports & version
│       ├── agents.py                  # Dynamic OpenCode agent loader & registry
│       ├── config.py                  # Workspace root resolution & .orchestrator directory
│       ├── dag.py                     # DAGScheduler (batch grouping & file collision guard)
│       ├── lock.py                    # SessionLockManager, atomic lock, stale PID cleanup
│       ├── models.py                  # Pydantic models for structured tool inputs/outputs
│       ├── prompts/                   # Phase Standard Operating Procedure (SOP) prompts
│       │   ├── __init__.py            # Prompt router helper
│       │   ├── complete.py            # COMPLETE phase summary SOP
│       │   ├── design.py              # DESIGN phase SOP
│       │   ├── execute.py             # EXECUTE phase SOP
│       │   ├── plan.py                # PLAN phase SOP
│       │   └── verify.py              # VERIFY phase SOP
│       ├── server.py                  # MCPServer instance, tool decorators & dispatch
│       ├── state.py                   # StateManager, session.json lifecycle, HMAC tamper check
│       └── verifier.py                # VerificationEngine (design, plan, execute, verify rules)
└── tests/
    ├── conftest.py                    # Fixtures: isolated temporary workspace & git repo
    ├── test_agents.py                 # Dynamic agent discovery & persona unit tests
    ├── test_bdd_scenarios.py          # pytest-bdd step definitions mapped to gherkin-scenarios.md
    ├── test_dag.py                    # DAG batching & file collision serialization
    ├── test_lock.py                   # Atomic lock, PID liveness & stale lock recovery
    ├── test_prompts.py                # Contract tests for all phase SOP invariants
    ├── test_scaffolding.py            # Scaffolding & package exports tests
    ├── test_server.py                 # MCP tool invocation unit tests
    ├── test_state.py                  # HMAC calculation, tampering detection, transitions
    └── test_verifier.py               # Machine verification unit tests per phase
```

---

## 4. MCP Tool Interface Contract

All tools are registered on the `MCPServer` instance using `@mcp.tool()`. All tool parameters accept optional `workspace_root: str | None = None` defaulting to auto-discovered workspace root.

### 4.1 `orchestrate_init`
- **Parameters**: `task_description: str`, `workspace_root: str | None = None`
- **Returns**: `InitResult`
- **Behavior**:
  1. Checks for active lock via `SessionLockManager`. If active process holds lock, returns lock error.
  2. Cleans up stale lock if PID is dead.
  3. Initializes state dictionary:
     - `session_id`: `<YYYY-MM-DD>-<slugified-task-name>`
     - `current_phase`: `"DESIGN"`
     - `current_phase_approved`: `False`
     - `task_description`: `task_description`
     - `history`: Initial creation event.
  4. Signs state with SHA256 HMAC and saves `.orchestrator/session.json`.
  5. Scaffolds default `.orchestrator/project-mandates.md` if missing.
  6. Returns session ID, phase `"DESIGN"`, and DESIGN phase SOP instructions.

### 4.2 `orchestrate_status`
- **Parameters**: `workspace_root: str | None = None`
- **Returns**: `StatusResult`
- **Behavior**:
  1. Checks if `.orchestrator/session.json` exists and verifies HMAC.
  2. If active session exists, returns `{ active_session: True, phase: "<CURRENT_PHASE>", message: "Active session in progress" }`.
  3. If no session exists, returns `{ active_session: False, phase: None, message: "No active orchestration session" }`.

### 4.3 `orchestrate_approve`
- **Parameters**: `workspace_root: str | None = None`
- **Returns**: `ApproveResult`
- **Behavior**:
  1. Loads `session.json` and verifies HMAC.
  2. Sets `current_phase_approved = True` and records `"phase_approved"` event in history.
  3. Re-signs and writes updated `session.json`.
  4. Returns confirmation that human gate for current phase is unlocked.

### 4.4 `orchestrate_verify`
- **Parameters**: `workspace_root: str | None = None`
- **Returns**: `VerifyResult`
- **Behavior**:
  1. Loads state, verifies HMAC, and dispatches to `VerificationEngine` based on `current_phase`.
  2. **DESIGN**:
     - Deliverable: `.orchestrator/design.md`.
     - Checks: File exists, human approval == True, contains `## Requirements`, `## Architecture`, `## Self-Confidence Audit`.
     - Next Phase on Pass: `PLAN`.
  3. **PLAN**:
     - Deliverable: `.orchestrator/plan.md`.
     - Checks: File exists, human approval == True, contains `## Tasks`, `## Detailed Task Specifications`, `## Verification`.
     - Task items: At least 1 checkbox, each containing `(Agent: <role>)`, `(Target: <path>)`, `(blocked_by: [<deps>])`.
     - Specification sections: Each task ID has a matching `### <task_id>` section.
     - Final barrier: Last task must be `Agent: implementation-reviewer` blocked by all preceding tasks.
     - Test command: Valid non-empty test command under `## Verification` (not "None").
     - Next Phase on Pass: `EXECUTE`.
  4. **EXECUTE**:
     - Checks: All plan tasks marked `- [x]` or `- [X]` (no unchecked `- [ ]`).
     - Target files: Every target file listed in plan must exist on disk and have size > 0 bytes.
     - Next Phase on Pass: `VERIFY`.
  5. **VERIFY**:
     - Checks: Executes test command from `plan.md` in shell subprocess (120s timeout).
     - Result: If exit code == 0, passes. If non-zero, captures last 50 lines of stdout/stderr and fails.
     - Next Phase on Pass: `COMPLETE`.
  6. Upon successful transition:
     - Updates `current_phase` to next phase.
     - Resets `current_phase_approved` to `False`.
     - Appends transition event to history, updates HMAC, saves `session.json`.
     - Returns `VerifyResult` with new phase and next-step SOP instructions.

### 4.5 `orchestrate_archive`
- **Parameters**: `force: bool = True`, `workspace_root: str | None = None`
- **Returns**: `ArchiveResult`
- **Behavior**:
  1. Releases and removes `.orchestrator/session.lock`.
  2. Creates archive folder `.orchestrator/archive/<session_id>/`.
  3. Moves `session.json`, `design.md`, and `plan.md` to the archive directory.
  4. Returns success status and archived session ID.

### 4.6 `orchestrate_get_dag_batches`
- **Parameters**: `workspace_root: str | None = None`
- **Returns**: `DAGResult`
- **Behavior**:
  1. Parses all task items from `.orchestrator/plan.md`.
  2. **File Collision Guard**: If multiple tasks target the same file path, automatically adds a sequential dependency so they run in successive batches.
  3. Computes topological execution batches where tasks in the same batch have zero unresolved dependencies.
  4. Returns ordered batches for parallel subagent execution.

### 4.7 `orchestrate_get_agents`
- **Parameters**: None
- **Returns**: `AgentListResult`
- **Behavior**:
  1. Inspects `CONCRETE_AGENTS` registry.
  2. Returns list of 12 specialized agent roles with their names, titles, and descriptions.

---

## 5. Security & Safety Model

1. **Cryptographic Anti-Tamper (HMAC-SHA256)**:
   - Secret key `b"opencode-orchestrator-anti-tamper-key"` signs all state dictionaries.
   - Any manual modification to `session.json` invalidates the hash and throws `StateTamperError`.
2. **OS-Level Atomic Locking**:
   - Uses `os.open(..., os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)` to create `session.lock`.
   - File holds session ID, creator PID, UTC timestamp, and ACTIVE status.
   - Lock acquisition inspects process table (`os.kill(pid, 0)`) to automatically reclaim abandoned/stale locks if previous process died.
3. **Mandatory Human Approval Gate**:
   - Machine verification cannot advance from DESIGN → PLAN or PLAN → EXECUTE unless `orchestrate_approve` has been explicitly invoked.

---

## 6. Implementation Dependencies

`pyproject.toml` specifications:
- **Build System**: `hatchling`
- **Python Version**: `>=3.11`
- **Core Dependencies**:
  - `mcp>=1.0.0` (Official MCP Python SDK)
  - `pydantic>=2.0.0` (Data validation & serialization)
  - `anyio>=4.0.0` (Async runtime support)
- **Development & Test Dependencies**:
  - `pytest>=8.0.0`
  - `pytest-asyncio>=0.23.0`
  - `pytest-bdd>=7.0.0` (Gherkin test execution)
  - `ruff>=0.4.0` (Linting & formatting)
  - `mypy>=1.10.0` (Type checking)
