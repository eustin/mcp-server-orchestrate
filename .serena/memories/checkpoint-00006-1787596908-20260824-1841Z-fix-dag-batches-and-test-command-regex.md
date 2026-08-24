# Checkpoint 00006 — Fix DAG batches task parsing and test command regex

## State
- Fixed DAG batches task line parsing for canonical single-parenthetical plan format (`state.py`, `verifier.py`, `test_bdd_scenarios.py`).
- Fixed `TEST_COMMAND_REGEX` and scoped search to `## Verification` section in `verifier.py` to prevent task-spec self-verification bullets from shadowing global test runner command.
- Updated schema documentation in `README.md`, `AGENTS.md`, and `docs/mcp-server-design.md`.
- Added 10 new regression tests (119 passed, ruff clean, mypy clean).

## Changes landed this session
- `src/orchestrator_mcp/state.py`: hardened regexes for `target`, `agent`, `blocked_by` with `(?:, |\()` prefix guard.
- `src/orchestrator_mcp/verifier.py`: hardened `Target:` regex in `verify_execution`; tightened `TEST_COMMAND_REGEX` requiring mandatory colon; scoped search to `## Verification` in `verify_plan` and `verify_testing`.
- `tests/test_bdd_scenarios.py`: hardened target regex helper in fixture setup.
- `tests/test_state.py`: added canonical format and description prose regression tests.
- `tests/test_server.py`: added canonical 3-task chain and collision guard serialization tests.
- `tests/test_verifier.py`: added canonical missing/0-byte target tests, self-verification bullet isolation tests, and format variations tests.
- `README.md`, `AGENTS.md`, `docs/mcp-server-design.md`: updated task checklist schema docs to canonical single-parenthetical format.

## Next steps
- All reported bugs in `docs/bugreport-dag-batches-blocked_by-parsing.md` and `docs/bugreport-verify-test-command-regex.md` resolved and verified.
