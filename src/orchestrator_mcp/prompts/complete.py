"""Phase 5 (COMPLETE) standard operating procedure prompt."""

COMPLETE_PHASE_PROMPT = """
# ORCHESTRATOR PHASE 5: COMPLETE — HANDOFF & ARCHIVE

All phases are complete. All implementation tasks verified. All tests pass.

## Mandatory Handoff Protocol

1. **Present Final Summary**:
   - List all files modified/created.
   - Show test pass count.
   - Summarize what was accomplished.

2. **User Satisfaction Check (MANDATORY)**:
   - You MUST explicitly ask the user: "Are you satisfied with the results?"
   - Do NOT auto-archive without explicit user confirmation.
   - Do NOT assume satisfaction. Wait for user response.

3. **Archive Gate**:
   - If the user confirms satisfaction, instruct them to invoke `orchestrate_archive` to close the session and release the lock.
   - If the user requests changes, delegate fixes using subagents before completing.

## MANDATORY DO-NOT
- Never auto-archive without user confirmation.
- Never end the session or stop responding until user explicitly confirms done.
"""
