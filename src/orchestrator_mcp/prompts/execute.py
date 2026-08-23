EXECUTE_PHASE_PROMPT = """# Phase SOP: EXECUTE

You are in the EXECUTE phase of the orchestration lifecycle.

## Objectives
1. Retrieve execution batches using `orchestrate_get_dag_batches`.
2. Delegate tasks to specialized subagents batch by batch.
3. Verify target files exist and are non-empty.
4. Mark completed tasks as `[x]` in `.orchestrator/plan.md`.
5. Run `orchestrate_verify` once all tasks are completed.
"""
