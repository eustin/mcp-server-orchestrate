# AGENTS.md — Orchestrator MCP Server

## Architecture & Project Overview
Python MCP server port of the OpenCode Orchestrator 4-phase machine-verified workflow (**DESIGN → PLAN → EXECUTE → VERIFY → COMPLETE**). Exposes deterministic MCP tools over stdio to enforce human approval gates, state integrity, AST/regex deliverable verification, and DAG task scheduling.

- **Behavioral Source of Truth**: `tests/features/orchestrator.feature` (18 BDD scenarios)
- **Package Root**: `src/orchestrator_mcp/`
- **Package Root**: `src/orchestrator_mcp/`

## Commands & Toolchain
Uses `uv` for Python package and environment management (Python >= 3.11).

```bash
# Install dependencies
uv sync

# Run test suite (BDD + Unit)
uv run pytest
uv run pytest tests/test_bdd_scenarios.py               # Run Gherkin BDD scenarios
uv run pytest tests/test_verifier.py -k test_plan_gate # Single test

# Linting & Formatting
uv run ruff check src/ tests/
uv run ruff format src/ tests/

# Type Checking
uv run mypy src/ tests/

# Run MCP server locally (stdio)
uv run python -m orchestrator_mcp.server
```

## Critical Invariants & Rules

1. **State File Integrity**:
   - Internal state file is `.orchestrator/session.json`.
   - Corrupted or unparseable state file raises `StateCorruptError`.

2. **Atomic Session Locking**:
   - Lock file is `.orchestrator/session.lock`.
   - MUST be acquired atomically with `os.open(..., os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o444)`.
   - Automatically clean up stale locks if creator PID is no longer alive (`os.kill(pid, 0)`).

3. **Human Approval Gates**:
   - `orchestrate_approve` MUST set `current_phase_approved = true`.
   - `DESIGN` and `PLAN` phase verifications MUST fail if `current_phase_approved` is false.
   - Advancing phase via `orchestrate_verify` MUST reset `current_phase_approved` to `false`.

4. **Phase Deliverables & Verification**:
   - **DESIGN**: `.orchestrator/design.md` with `## Requirements`, `## Architecture`, `## Self-Confidence Audit`.
   - **PLAN**: `.orchestrator/plan.md` with `## Tasks`, `## Detailed Task Specifications`, `## Verification`. Tasks require `(Agent: <role>, Target: <path>, blocked_by: [<deps>])`. Final barrier task MUST be `Agent: implementation-reviewer`. `Test command: <cmd>` cannot be "None" or empty.
   - **EXECUTE**: All plan tasks must be marked `- [x]`. Target files must exist and be > 0 bytes.
   - **VERIFY**: Subprocess test runner executes test command (120s timeout, exit code 0).

5. **DAG Scheduling & Collision Guard**:
   - If multiple tasks share identical target file paths, `DAGScheduler` MUST serialize them sequentially across distinct batches to prevent merge collisions.
