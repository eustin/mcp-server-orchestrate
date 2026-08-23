DESIGN_PHASE_PROMPT = """# Phase SOP: DESIGN

You are in the DESIGN phase of the orchestration lifecycle.

## Objectives
1. Understand and define user requirements, edge cases, and scope.
2. Select architecture patterns, component boundaries, and data structures.
3. Conduct a self-confidence audit (deductions for assumptions, missed edge cases).
4. Write the deliverable to `.orchestrator/design.md`.

## Mandatory Headings in `.orchestrator/design.md`
- `## Requirements`
- `## Architecture`
- `## Self-Confidence Audit`

## Next Gate
Instruct the user to review the document and run `orchestrate_approve` before calling `orchestrate_verify`.
"""
