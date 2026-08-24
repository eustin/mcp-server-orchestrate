# Bug Report — `orchestrate_get_dag_batches` collapses dependency graph (all tasks in one batch)

**Reported:** 2026-08-24
**Affected tool:** `orchestrate_get_dag_batches`
**Severity:** High (execution-phase scheduling)
**Component:** `src/orchestrator_mcp/state.py` (task-line parser) + `src/orchestrator_mcp/dag.py` (batching)
**Status:** Open

---

## Summary

`orchestrate_get_dag_batches` ignores the `blocked_by` dependencies declared in
`.orchestrator/plan.md`. Every task is returned with `blocked_by: []` (and
`target: null`, `agent` mangled), so the DAG collapses into **a single batch
containing all tasks** instead of the topologically ordered parallel batches the
tool is documented to produce (`README.md` → "returns ordered parallel batches").

This forces the Orchestration Lead to ignore the tool's batching and fall back
to the plan's declared `blocked_by` to sequence work — violating the documented
"spawn by topologically sorted batch" supervision protocol. In plans with
parallel branches it would allow dependent tasks to run before their
prerequisites complete.

Observed in two independent sessions against two different plans (a linear
3-task chain and a 6-task graph with real dependencies): identical failure.

---

## Root cause

The three per-field regexes in `src/orchestrator_mcp/state.py` all anchor the
field name directly to an opening parenthesis `(`:

```python
# ~line 137 — Target
m_target = re.search(r"\(Target:\s*([^)]+)\)", line_str)
# ~line 143 — Agent
m_agent   = re.search(r"\(Agent:\s*([^)]+)\)", line_str)
# ~line 149 — blocked_by
m_blocked = re.search(r"\(blocked_by:\s*\[(.*?)\]\)", line_str)
```

But the plan template the server itself enforces (`src/orchestrator_mcp/prompts/plan.py:31`)
writes **all three fields inside a single parenthetical**:

```
- [ ] **T<N>**: Task Description (Agent: <role>, Target: path/to/file, blocked_by: [<deps>])
```

In that format only `Agent:` is preceded by `(`; `Target:` and `blocked_by:` are
preceded by `", "`. So:

- `\(Agent:\s*([^)]+)\)` matches `(Agent: ... [T1])` and, because `[^)]+` is
  greedy, captures **the whole parenthetical** → `agent` =
  `"coder, Target: src/..., blocked_by: [T1]"` (mangled).
- `\(Target:` never matches (no `(Target:` in the line) → `target = None`.
- `\(blocked_by:` never matches (no `(blocked_by:` in the line) → `blocked_by = []`.

Note the **description** regex (state.py ~line 160) already handles the
single-parenthetical format correctly:

```python
m_desc = re.search(r"^-\s*\[[ xX]\]\s*(.*?)(?=\s*\((?:Agent|Target|blocked_by):|$)", line_str)
```

so `description` parses fine — only `agent` / `target` / `blocked_by` are broken.

`dag.py` then builds batches from the (empty) `blocked_by` arrays, so every task
becomes "unblocked" → one flat batch.

---

## Reproduction

Plan task lines (verbatim format produced by the server's own PLAN prompt):

```
- [ ] **T1**: do A (Agent: coder, Target: src/a.py, blocked_by: [])
- [ ] **T2**: do B (Agent: coder, Target: src/b.py, blocked_by: [T1])
- [ ] **T3**: do C (Agent: coder, Target: src/c.py, blocked_by: [T1, T2])
```

Call `orchestrate_get_dag_batches`.

**Expected:**

```json
{ "batches": [
    { "batch_number": 1, "tasks": [ { "id": "T1", "blocked_by": [] } ] },
    { "batch_number": 2, "tasks": [ { "id": "T2", "blocked_by": ["T1"] } ] },
    { "batch_number": 3, "tasks": [ { "id": "T3", "blocked_by": ["T1", "T2"] } ] }
] }
```

**Actual (observed, both sessions):**

```json
{ "batches": [ { "batch_number": 1, "tasks": [
    { "id": "T1", "blocked_by": [], "target": null,
      "agent": "coder, Target: src/a.py, blocked_by: []" },
    { "id": "T2", "blocked_by": [], "target": null,
      "agent": "coder, Target: src/b.py, blocked_by: [T1]" },
    { "id": "T3", "blocked_by": [], "target": null,
      "agent": "coder, Target: src/c.py, blocked_by: [T1, T2]" }
] } ] }
```

Real observed input/output (session `2026-08-24-audit-all-cfi-clustering-metho`):

```
- [ ] **T1**: Write + run read-only CFI audit probes ... (Agent: tester, Target: scratch/audit/cfi_audit_probes.py, blocked_by: [])
- [ ] **T2**: Write Findings Register ... (Agent: technical-writer, Target: .orchestrator/audit_cfi_methods.md, blocked_by: [T1])
- [ ] **T3**: Final Implementation Verification Audit ... (Agent: implementation-reviewer, Target: .orchestrator/audit_cfi_methods.md, blocked_by: [T1, T2])
```
→ returned ONE batch with all three tasks, every `blocked_by: []`, `target: null`,
`agent` = full parenthetical string. Same behavior in the prior 6-task session.

---

## Impact

1. **DAG scheduling is flat** — no topological batches; parallel-branch plans
   cannot be executed by the tool as designed.
2. **`target` is always `null`** — downstream "Target: path" enforcement /
   file-collision guard (README: "with file collision guard") has no file to
   work with.
3. **`agent` is corrupted** — the plan role is not extractable (`"coder, Target:
   ..., blocked_by: []"`), so role→subagent mapping must be re-derived manually.
4. **Supervision protocol drift** — the Orchestration Lead must re-derive
   dependencies from the plan text, which the tool was built to provide.

---

## Suggested fix

Drop the `\(` anchor for `Target:` and `blocked_by:` (and stop `Agent` at the
first `,` or `)`), e.g. in `state.py`:

```python
# Agent: first field inside the parenthetical
m_agent   = re.search(r"\(Agent:\s*([^),]+)", line_str)
# Target: field may be 2nd/3rd inside the parenthetical
m_target  = re.search(r"Target:\s*([^,)]+)", line_str)
# blocked_by: field may be 2nd/3rd inside the parenthetical
m_blocked = re.search(r"blocked_by:\s*\[([^\]]*)\]", line_str)
```

Add a unit test asserting: for the template line
`- [ ] **T2**: desc (Agent: coder, Target: src/b.py, blocked_by: [T1, T2])`,
`get_dag_batches` yields `blocked_by == ["T1", "T2"]`, `target == "src/b.py"`,
`agent == "coder"`, and the correct multi-batch ordering.

---

## Workaround (until fixed)

Orchestration Lead: ignore the returned batch structure; sequence tasks
according to the `blocked_by` declared in `.orchestrator/plan.md` (the parser
bug is in the field extraction only — the plan text itself is correct).
