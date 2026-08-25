# Orchestrate Python MCP Server

Machine-verified 4-phase workflow MCP server for AI coding assistants. Enforces **DESIGN → PLAN → EXECUTE → VERIFY → COMPLETE** with human approval gates, state integrity checks, and DAG task scheduling.

---

## Table of Contents

- [Workflow Lifecycle](#workflow-lifecycle)
- [MCP Tools Reference](#mcp-tools-reference)
- [Deliverable Requirements per Phase](#deliverable-requirements-per-phase)
- [Example Deliverables](#example-deliverables)
  - [Example `.orchestrator/design.md`](#example-orchestratordesignmd)
  - [Example `.orchestrator/plan.md`](#example-orchestratorplanmd)
- [Quickstart](#quickstart)
  - [Installation & Run](#installation--run)
  - [OpenCode MCP Configuration](#opencode-mcp-configuration-opencodejson)

---

## Workflow Lifecycle

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

## MCP Tools Reference

| Tool Name | Parameters | Description |
|---|---|---|
| `orchestrate_init` | `task_description: str` | Initializes new session in `DESIGN` phase, acquires atomic lock, returns initial SOP prompt. |
| `orchestrate_status` | *(none)* | Returns `{ active_session: bool, phase: str, message: str }`. |
| `orchestrate_approve` | *(none)* | Human gate approval. Unlocks verification for `DESIGN` and `PLAN` phases. |
| `orchestrate_verify` | *(none)* | Validates phase deliverables. Advances to next phase on pass, returns next SOP prompt. |
| `orchestrate_get_dag_batches` | *(none)* | Parses `plan.md` tasks and returns ordered parallel batches with file collision guard. |
| `orchestrate_archive` | `force: bool = True` | Releases lock and moves session files into `.orchestrator/archive/<session_id>/`. |

---

## Deliverable Requirements per Phase

1. **DESIGN Phase**:
   - Deliverable: `.orchestrator/design.md`
   - Required Headings: `## Requirements`, `## Architecture`, `## Self-Confidence Audit`.
   - Gate: Requires `orchestrate_approve` before verification.

2. **PLAN Phase**:
   - Deliverable: `.orchestrator/plan.md`
   - Tasks Schema: `- [ ] **<id>**: <desc> (Agent: <role>, Target: <file>, blocked_by: [<deps>])`
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

## Example Deliverables

Below are minimal, realistic examples demonstrating valid syntax and required structure for phase deliverables.

### Example `.orchestrator/design.md`

````markdown
# Design — Collinear-feature handling in corrected CFI estimators

## Goal
Fix `run_cfi_corrected` crash when input feature matrix contains near-collinear or duplicate pairs (`DatasetException: |rho|=1 is effectively 1`).

## Requirements

### Functional
| # | Requirement |
|---|---|
| F1 | `corrected_mutual_information(a, b)` returns `1.0` when pair is collinear (`rho**2 >= 1 - 1e-12`). |
| F2 | `corrected_variation_of_information(a, b)` returns `0.0` when pair is collinear. |
| F3 | `BaseCorrectedCfiConfig` gains opt-in `drop_collinear_features: bool = False`. |

### Non-Functional
- **No silent fallbacks**: Constant/NaN inputs still raise `DatasetException`.
- **Zero regression**: Unaffected estimator paths remain byte-identical.

## Architecture

```python
_EFFECTIVELY_COLLINEAR_RHO2 = 1 - 1e-12

def _is_effectively_collinear(rho: float) -> bool:
    return rho**2 >= _EFFECTIVELY_COLLINEAR_RHO2
```
In `corrected_mutual_information`, short-circuit before histogram binning:
- If `np.isfinite(rho)` and `_is_effectively_collinear(rho)`: return `1.0`.

## Self-Confidence Audit
- Guessed paths: 0% (inspected `dependence.py`, `config.py`, `impl.py`)
- Unresolved assumptions: 0% (analytic limits Cover & Thomas Thm 2.4.1)
- Missed edge cases: 0% (constant inputs delegate to existing validation)
- Unchecked config: 0% (pydantic & numpy dependencies verified)
**Score: 97%** (>= 95% gate pass)
````

### Example `.orchestrator/plan.md`

````markdown
# Implementation Plan — Collinear-feature handling in corrected CFI estimators

## Overview
Implement 2-layer collinear handling: (1) estimator analytic limit guard in `dependence.py`, (2) opt-in feature dedup in `config.py` / `impl.py`.

## Tasks

- [ ] **T1**: Estimator guard in dependence.py (Agent: coder, Target: src/research/cfi/dependence.py, blocked_by: [])
- [ ] **T2**: Add drop_collinear_features config field (Agent: coder, Target: src/research/cfi/config.py, blocked_by: [])
- [ ] **T3**: Unit tests for collinear limits & config (Agent: tester, Target: tests/test_cfi.py, blocked_by: [T1, T2])
- [ ] **T4**: Final Implementation Verification Audit (Agent: implementation-reviewer, Target: .orchestrator/plan.md, blocked_by: [T1, T2, T3])

## Detailed Task Specifications

### T1: Estimator guard in dependence.py
- **Target**: `src/research/cfi/dependence.py`
- **Signatures & Contracts**:
  - Add `_EFFECTIVELY_COLLINEAR_RHO2: float = 1 - 1e-12`
  - Add `_is_effectively_collinear(rho: float) -> bool`
  - Update `corrected_mutual_information(a: ArrayLike, b: ArrayLike, n_bins: int | None = None) -> float`
- **Old → New Implementation**:
```python
# Before
    x, y = _as_paired_arrays(a, b)
    hx, hy, hxy = _binning_and_entropies(x, y, n_bins)

# After
    x, y = _as_paired_arrays(a, b)
    if n_bins is None:
        rho = float(np.corrcoef(x, y)[0, 1])
        if np.isfinite(rho) and _is_effectively_collinear(rho):
            return 1.0
    hx, hy, hxy = _binning_and_entropies(x, y, n_bins)
```
- **Acceptance Criteria**:
  - `corrected_mutual_information(2*a+1, a) == 1.0` without raising `DatasetException`.

### T2: Add drop_collinear_features config field
- **Target**: `src/research/cfi/config.py`
- **Signatures & Contracts**:
  - Extend `BaseCorrectedCfiConfig(BaseModel)` with new schema fields.
- **Old → New Implementation**:
```python
# Before
class BaseCorrectedCfiConfig(BaseModel):
    scoring: Any = log_loss
    seed: int = 42

# After
class BaseCorrectedCfiConfig(BaseModel):
    scoring: Any = log_loss
    seed: int = 42
    drop_collinear_features: bool = False
    collinear_threshold: float = Field(default=0.999, ge=0.0, lt=1.0)
```

### T3: Unit tests for collinear limits & config
- **Target Test File**: `tests/test_cfi.py`
- **Test Scenarios**: MI limit = 1.0, VI limit = 0.0, validation constraint `lt=1.0`.
- **Copy-Paste Implementation**:
```python
def test_mi_collinear_returns_one():
    a = np.arange(100.0)
    b = 2.0 * a + 1.0
    assert corrected_mutual_information(b, a) == pytest.approx(1.0)

def test_vi_collinear_returns_zero():
    a = np.arange(100.0)
    b = 2.0 * a + 1.0
    assert corrected_variation_of_information(b, a, normalize=True) == 0.0

def test_collinear_threshold_validation():
    with pytest.raises(ValidationError):
        cfi_config("onc_vi", collinear_threshold=1.5)
```

### T4: Final Implementation Verification Audit
- **Target**: `.orchestrator/plan.md`
- **Verification Specialist Duties**:
  - Inspect `git diff` against specifications in T1–T3.
  - Verify all unit tests pass with zero regressions.

## File Inventory
| File | Status | Purpose |
|---|---|---|
| `src/research/cfi/dependence.py` | Modified | Add collinear short-circuit |
| `src/research/cfi/config.py` | Modified | Add `drop_collinear_features` schema field |
| `tests/test_cfi.py` | Modified | Collinear regression test suite |

## Verification
Test command: uv run pytest tests/test_cfi.py -v

## Confidence Self-Audit
- Guessed paths: 0%
- Unresolved assumptions: 0%
- Missed edge cases: 0%
- Unchecked config: 0%
**Score: 98%** (>= 95% gate pass)
````

---

## Quickstart

### Installation & Run

```bash
# Sync environment
uv sync

# Run tests (Unit + 26 BDD Scenarios)
uv run pytest

# Start MCP server (stdio transport)
uv run python -m orchestrate_mcp.server
```

### OpenCode MCP Configuration (`opencode.json`)

```json
{
  "mcpServers": {
    "orchestrate": {
      "command": "uv",
      "args": ["run", "--directory", "/path/to/orchestrate", "python", "-m", "orchestrate_mcp.server"]
    }
  }
}
```
