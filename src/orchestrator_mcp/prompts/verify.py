VERIFY_PHASE_PROMPT = """# Phase SOP: VERIFY

You are in the VERIFY phase of the orchestration lifecycle.

## Objectives
1. Run `orchestrate_verify` to execute automated test runner from plan.
2. If tests fail, inspect failure logs and remediate.
3. Advance to COMPLETE upon zero exit code.
"""
