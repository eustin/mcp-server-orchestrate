PLAN_PHASE_PROMPT = """# Phase SOP: PLAN

You are in the PLAN phase of the orchestration lifecycle.

## Objectives
1. Break down architecture into discrete task items.
2. Format tasks with `(Agent: <role>)`, `(Target: <file>)`, and `(blocked_by: [<deps>])`.
3. Provide detailed specifications for every task under `## Detailed Task Specifications`.
4. Ensure the final task is assigned to `Agent: implementation-reviewer` blocked by prior tasks.
5. Provide a valid executable test command under `## Verification` (`Test command: <cmd>`).
6. Write the deliverable to `.orchestrator/plan.md`.

## Next Gate
Instruct the user to run `orchestrate_approve` before calling `orchestrate_verify`.
"""
