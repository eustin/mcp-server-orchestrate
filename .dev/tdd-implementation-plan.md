# Orchestrator Python MCP Server — TDD Implementation Plan: Dynamic Agent Discovery & Comprehensive Phase Prompts

## 1. Overview & Context

This document details the Test-Driven Development (TDD) implementation plan to upgrade the **Orchestrator Python MCP Server** (`orchestrator_mcp`) with:
1. **Dynamic OpenCode Agent Discovery & Loading** (`src/orchestrator_mcp/agents.py`): Discover and load agent personas dynamically from the user's OpenCode configuration directory (`~/.config/opencode/agents/`, `$XDG_CONFIG_HOME/opencode/agents/`, `<workspace>/.opencode/agents/`, or `<workspace>/agents/`) without bundling or copying static `.md` files into the repository.
2. **Comprehensive Phase Standard Operating Procedure (SOP) Prompts** (`src/orchestrator_mcp/prompts/`): Upgrade stub prompts into full, authoritative supervisory prompts for all 5 phases (`DESIGN`, `PLAN`, `EXECUTE`, `VERIFY`, `COMPLETE`) adapted for MCP tool invocations (`orchestrate_approve`, `orchestrate_verify`, `orchestrate_get_dag_batches`, `orchestrate_archive`, `orchestrate_status`) with strict supervisory gates, copy-paste requirements, subagent role mappings, debugger retry escalation, verification specialist loops, and user satisfaction gates (free of legacy "Maestro" references).
3. **Project Mandates Scaffolding** (`src/orchestrator_mcp/server.py`): Ensure `orchestrate_init` scaffolds the full default `.orchestrator/project-mandates.md` with "No Silent Fallbacks" and anti-fabrication rules.
4. **Agent Inspection Endpoint** (`src/orchestrator_mcp/server.py`): Expose `orchestrate_get_agents` MCP tool to allow clients and agents to discover available specialized roles and dynamic descriptions.
5. **Contract & Regression Test Suites** (`tests/test_agents.py`, `tests/test_prompts.py`, `tests/test_server.py`): Test-first verification using Red-Green-Refactor methodology with full forbidden-tool contract checks, role mapping assertions, and Maestro-absence regression tests.

---

## 2. Source-of-Truth Architectural Reconciliation

| Source of Truth Component (`plugins/orchestrator`) | MCP Server Architecture (`orchestrator_mcp`) | Reconciliation Decision |
|---|---|---|
| `plugin.js` JS Hooks (`experimental.chat.system.transform`) | MCP stdio tool responses (`InitResult.sop_instructions`, `VerifyResult.next_sop_instructions`) | Prompts returned in structured tool outputs rather than runtime stream interception. |
| `plugin.js` JS `tool.call` hard guard on code editing | System prompt supervisory mandate in `EXECUTE_PHASE_PROMPT` | Hard prompt instructions + verification gates; MCP server does not intercept third-party client tool calls. |
| `sync_agents.py` & `agents.py` static sync | Dynamic multi-directory loader in `src/orchestrator_mcp/agents.py` | Reads user's OpenCode directories dynamically on demand; zero static files committed to repository. |
| `cli.py` Python CLI entrypoint | FastMCP Server (`server.py`) exposing `@mcp.tool()` stdio endpoints | All CLI commands mapped 1:1 to JSON-RPC tools (`orchestrate_*`). |
| `.orchestrator/project-mandates.md` scaffolding | `orchestrate_init` scaffolding in `server.py` | Full "No Silent Fallbacks" mandate template scaffolded on session creation. |

---

## 3. Target Directory & Module Structure

```
orchestrate/
├── docs/
│   ├── gherkin-scenarios.md
│   ├── mcp-server-design.md
│   └── tdd-implementation-plan.md
├── src/
│   └── orchestrator_mcp/
│       ├── __init__.py
│       ├── agents.py                 # Dynamic agent discovery & persona registry
│       ├── config.py                 # Workspace & OpenCode path resolvers
│       ├── dag.py
│       ├── lock.py
│       ├── models.py                 # Pydantic schemas (added AgentListResult, AgentSummary)
│       ├── prompts/
│       │   ├── __init__.py
│       │   ├── complete.py           # UPGRADED: Full completion & satisfaction check SOP
│       │   ├── design.py             # UPGRADED: Full requirements & architecture SOP
│       │   ├── execute.py            # UPGRADED: Full supervisory delegation & fix loop SOP
│       │   ├── plan.py               # UPGRADED: Full task breakdown & copy-paste specs SOP
│       │   └── verify.py             # UPGRADED: Full verification & audit SOP
│       ├── server.py                 # UPGRADED: Full project-mandates + orchestrate_get_agents
│       ├── state.py
│       └── verifier.py
└── tests/
    ├── conftest.py
    ├── test_agents.py                # Unit tests for dynamic OpenCode agent discovery
    ├── test_bdd_scenarios.py
    ├── test_dag.py
    ├── test_lock.py
    ├── test_prompts.py               # Contract tests for all phase SOP invariants
    ├── test_scaffolding.py           # Scaffolding & package exports tests
    ├── test_server.py                # Tool invocation & mandates scaffolding tests
    ├── test_state.py
    └── test_verifier.py
```

---

## 4. Phased TDD Implementation

---

### Phase A: Dynamic OpenCode Agent Discovery & Registry (`src/orchestrator_mcp/agents.py`)

#### A.1 Architectural Specifications
- `resolve_opencode_agents_dirs(workspace_root: Path | None = None) -> list[Path]`:
  Returns prioritized search directories for OpenCode agents:
  1. `<workspace_root>/.opencode/agents/`
  2. `<workspace_root>/agents/`
  3. `$XDG_CONFIG_HOME/opencode/agents/` (if `XDG_CONFIG_HOME` set) or `Path.home() / ".config" / "opencode" / "agents"`
  4. `Path.home() / ".opencode" / "agents"`
- `load_agent_prompt(name: str, workspace_root: Path | None = None) -> str`:
  Iterates search paths. If `<path>/<name>.md` exists, reads and returns raw content (preserving YAML frontmatter as consumed by OpenCode subagent harness). If not found, returns fallback persona string `# Agent Persona: {name.title()}\nRole: Specialist for {name}.`.
- `CONCRETE_AGENTS`: Registry dictionary mapping the 12 standard agent roles:
  1. `architect`: System design, tech stack selection, component boundaries.
  2. `product-manager`: Requirements, PRDs, user stories, scope prioritization.
  3. `ux-designer`: User flows, wireframes, interaction patterns.
  4. `cavecrew-investigator`: Read-only code locator, file:line indexing.
  5. `coder`: Implementation specialist, clean pattern adherence.
  6. `debugger`: Root cause analysis, stack trace diagnosis, targeted minimal fixes.
  7. `performance-engineer`: Latency optimization, profiling, memory bottlenecks.
  8. `tester`: Test suite creation, edge cases, assertions.
  9. `implementation-reviewer`: Plan conformance verification, deliverable inventory audit.
  10. `code-reviewer`: Code quality, SOLID principles, security check.
  11. `security-engineer`: Vulnerability scanning, threat modeling, OWASP Top 10.
  12. `technical-writer`: Documentation, READMEs, API specifications.

#### A.2 Red: Test Suite First (`tests/test_agents.py`)

```python
"""Tests for dynamic OpenCode agent discovery and persona loading."""
from pathlib import Path
from unittest.mock import patch

from orchestrator_mcp.agents import (
    CONCRETE_AGENTS,
    get_agent_info,
    load_agent_prompt,
    resolve_opencode_agents_dirs,
)


def test_concrete_agents_registry_has_all_12_roles():
    expected_roles = [
        "architect",
        "product-manager",
        "ux-designer",
        "cavecrew-investigator",
        "coder",
        "debugger",
        "performance-engineer",
        "tester",
        "implementation-reviewer",
        "code-reviewer",
        "security-engineer",
        "technical-writer",
    ]
    for role in expected_roles:
        assert role in CONCRETE_AGENTS, f"Missing role in CONCRETE_AGENTS: {role}"
        info = CONCRETE_AGENTS[role]
        assert "role" in info
        assert "description" in info
        assert callable(info["prompt_fn"])


def test_resolve_opencode_agents_dirs_order_default_env(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    ws_opencode_agents = ws / ".opencode" / "agents"
    ws_agents = ws / "agents"
    home = tmp_path / "home"
    home_config_agents = home / ".config" / "opencode" / "agents"
    home_opencode_agents = home / ".opencode" / "agents"

    with patch("pathlib.Path.home", return_value=home), patch.dict(
        "os.environ", {}, clear=True
    ):
        dirs = resolve_opencode_agents_dirs(ws)
        assert dirs == [
            ws_opencode_agents,
            ws_agents,
            home_config_agents,
            home_opencode_agents,
        ]


def test_resolve_opencode_agents_dirs_with_xdg_env(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    custom_xdg = tmp_path / "custom_config"
    home = tmp_path / "home"

    with patch("pathlib.Path.home", return_value=home), patch.dict(
        "os.environ", {"XDG_CONFIG_HOME": str(custom_xdg)}, clear=True
    ):
        dirs = resolve_opencode_agents_dirs(ws)
        assert dirs[2] == custom_xdg / "opencode" / "agents"


def test_load_agent_prompt_from_workspace(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws_agents = ws / "agents"
    ws_agents.mkdir(parents=True)
    custom_coder = ws_agents / "coder.md"
    custom_coder.write_text("# Workspace Custom Coder Persona", encoding="utf-8")

    prompt = load_agent_prompt("coder", workspace_root=ws)
    assert prompt == "# Workspace Custom Coder Persona"


def test_load_agent_prompt_from_home_config(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    home = tmp_path / "home"
    config_agents = home / ".config" / "opencode" / "agents"
    config_agents.mkdir(parents=True)
    (config_agents / "tester.md").write_text("# Global Tester Persona", encoding="utf-8")

    with patch("pathlib.Path.home", return_value=home), patch.dict(
        "os.environ", {}, clear=True
    ):
        prompt = load_agent_prompt("tester", workspace_root=ws)
        assert prompt == "# Global Tester Persona"


def test_load_agent_prompt_preserves_frontmatter(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws_agents = ws / "agents"
    ws_agents.mkdir(parents=True)
    agent_file = ws_agents / "architect.md"
    raw_content = "---\nmode: subagent\nhidden: true\n---\n# Agent Persona: Architect"
    agent_file.write_text(raw_content, encoding="utf-8")

    prompt = load_agent_prompt("architect", workspace_root=ws)
    assert prompt == raw_content


def test_load_agent_prompt_fallback_when_file_not_found(tmp_path: Path):
    ws = tmp_path / "workspace"
    ws.mkdir()
    with patch("pathlib.Path.home", return_value=tmp_path / "empty_home"), patch.dict(
        "os.environ", {}, clear=True
    ):
        prompt = load_agent_prompt("nonexistent-role", workspace_root=ws)
        assert "Agent Persona: Nonexistent-Role" in prompt
        assert "Specialist for nonexistent-role" in prompt


def test_get_agent_info_helper():
    info = get_agent_info("architect")
    assert info is not None
    assert info["role"] == "System Architect"
```

#### A.3 Green: Implementation (`src/orchestrator_mcp/agents.py`)

```python
"""Concrete Agent Personas and Dynamic OpenCode Agent Discovery."""
from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

from .config import resolve_workspace_root


class AgentInfo(TypedDict):
    role: str
    description: str
    prompt_fn: Callable[[], str]


def resolve_opencode_agents_dirs(workspace_root: Path | None = None) -> list[Path]:
    """Return prioritized search directories for OpenCode agent definition files."""
    root = workspace_root or resolve_workspace_root()
    home = Path.home()
    xdg_env = os.environ.get("XDG_CONFIG_HOME")
    xdg_config = Path(xdg_env) if xdg_env else home / ".config"

    return [
        root / ".opencode" / "agents",
        root / "agents",
        xdg_config / "opencode" / "agents",
        home / ".opencode" / "agents",
    ]


def load_agent_prompt(name: str, workspace_root: Path | None = None) -> str:
    """Dynamically load agent system prompt from user's OpenCode environment."""
    search_dirs = resolve_opencode_agents_dirs(workspace_root)
    for agent_dir in search_dirs:
        agent_file = agent_dir / f"{name}.md"
        if agent_file.is_file():
            try:
                return agent_file.read_text(encoding="utf-8")
            except OSError:
                continue

    return f"# Agent Persona: {name.title()}\nRole: Specialist for {name}."


CONCRETE_AGENTS: dict[str, AgentInfo] = {
    "architect": {
        "role": "System Architect",
        "description": "System design specialist for architecture decisions, technology selection, and component boundaries.",
        "prompt_fn": lambda: load_agent_prompt("architect"),
    },
    "product-manager": {
        "role": "Product Manager",
        "description": "Product management specialist for requirements gathering, PRDs, user stories, feature prioritization, and competitive analysis.",
        "prompt_fn": lambda: load_agent_prompt("product-manager"),
    },
    "ux-designer": {
        "role": "UX Designer",
        "description": "UX designer for user flow design, interaction patterns, wireframe descriptions, and usability evaluation.",
        "prompt_fn": lambda: load_agent_prompt("ux-designer"),
    },
    "cavecrew-investigator": {
        "role": "Cavecrew Investigator",
        "description": "Read-only code locator. Returns file:line table for where symbols, functions, or configs are defined.",
        "prompt_fn": lambda: load_agent_prompt("cavecrew-investigator"),
    },
    "coder": {
        "role": "Coder",
        "description": "Implementation specialist for writing clean, well-structured code following established patterns and SOLID principles.",
        "prompt_fn": lambda: load_agent_prompt("coder"),
    },
    "debugger": {
        "role": "Debugger",
        "description": "Debugging specialist for root cause analysis, investigating defects, and tracing execution flow.",
        "prompt_fn": lambda: load_agent_prompt("debugger"),
    },
    "performance-engineer": {
        "role": "Performance Engineer",
        "description": "Performance engineering specialist for systematic performance analysis, profiling, benchmarking, and latency optimization.",
        "prompt_fn": lambda: load_agent_prompt("performance-engineer"),
    },
    "tester": {
        "role": "Tester",
        "description": "Testing specialist for unit, integration, and E2E test implementation, edge case discovery, and test coverage.",
        "prompt_fn": lambda: load_agent_prompt("tester"),
    },
    "implementation-reviewer": {
        "role": "Implementation Reviewer",
        "description": "Implementation reviewer specializing in plan conformance verification. Verifies deliverable inventory against approved implementation plan.",
        "prompt_fn": lambda: load_agent_prompt("implementation-reviewer"),
    },
    "code-reviewer": {
        "role": "Code Reviewer",
        "description": "Code reviewer specializing in verified code quality assessment, SOLID principles, security, and logic correctness.",
        "prompt_fn": lambda: load_agent_prompt("code-reviewer"),
    },
    "security-engineer": {
        "role": "Security Engineer",
        "description": "Security engineer specializing in application security assessment, vulnerability scanning, threat modeling, and OWASP Top 10 audits.",
        "prompt_fn": lambda: load_agent_prompt("security-engineer"),
    },
    "technical-writer": {
        "role": "Technical Writer",
        "description": "Technical writer specializing in clear, accurate developer documentation, API contracts, READMEs, and architecture docs.",
        "prompt_fn": lambda: load_agent_prompt("technical-writer"),
    },
}


def get_agent_info(name: str) -> AgentInfo | None:
    """Retrieve metadata and prompt resolver for given agent role."""
    return CONCRETE_AGENTS.get(name)
```

---

### Phase B: Upgraded Phase SOP Prompts (`src/orchestrator_mcp/prompts/`)

#### B.1 Prompts Specification (Adapted for MCP Tool Execution)

1. **`src/orchestrator_mcp/prompts/design.py`**:
   - Includes `SELF-IDENTIFICATION GATE` with `Worker Scope Boundary` check.
   - Declares Active Roles: `Product Manager`, `Architect`, `UX Designer`, `Cavecrew Investigator`.
   - Workflow steps: Requirement discovery, Turn-1 flow, writing `.orchestrator/design.md` with sections:
     `## Goal`, `## Requirements`, `## Architecture`, `## Self-Confidence Audit`.
   - Self-Confidence Audit Gate (`>= 95%`).
   - Human Approval instructions instructing user to invoke `orchestrate_approve` before `orchestrate_verify`.
   - Mandatory unbypassable refusal constraints.

2. **`src/orchestrator_mcp/prompts/plan.py`**:
   - Includes `SELF-IDENTIFICATION GATE`.
   - Declares Active Roles: `Architect`, `Cavecrew Investigator`.
   - Granularity rules: 1–3 files per task.
   - Tasks list formatting: `- [ ] **T<N>**: Task Description (Agent: <role>, Target: <path>, blocked_by: [<deps>])`.
   - Mandatory final task: `Agent: implementation-reviewer` blocked by all preceding tasks.
   - High-granularity task specifications (`## Detailed Task Specifications`):
     - Tester: Embed complete source code in code block (copy-paste ready).
     - Coder: Embed exact old→new code blocks.
   - Verification command: Non-empty `Test command: <cmd>`.
   - Self-Confidence Audit Gate (`>= 95%`).
   - Approval Gate: Instruct user to invoke `orchestrate_approve` then `orchestrate_verify`.

3. **`src/orchestrator_mcp/prompts/execute.py`**:
   - Includes `SELF-IDENTIFICATION GATE`.
   - Supervisory Lead mandate: NEVER edit or write source code directly.
   - Forbidden code-edit tools blacklist (`edit`, `write`, `serena_replace_content`, `serena_create_text_file`, `serena_replace_symbol_body`, `serena_insert_after_symbol`, `serena_insert_before_symbol`, `serena_replace_in_files`, `serena_rename_symbol`, `serena_safe_delete_symbol`).
   - Allowed tools list (`task`, `orchestrate_get_dag_batches`, `orchestrate_status`, `orchestrate_verify`, checkbox edits to `.orchestrator/plan.md`, `read`, `glob`, `grep`, `serena_read_file`, `serena_find_file`, `serena_find_symbol`).
   - Batch delegation protocol via `orchestrate_get_dag_batches` and subagent task tools.
   - Checkbox lifecycle: Only check `[x]` after subagent reports verified success.
   - 3-retry debugger escalation protocol.
   - `implementation-reviewer` Verification Specialist Protocol: Fix Delegation Loop & Re-Verification Loop.
   - Phase completion via `orchestrate_verify`.

4. **`src/orchestrator_mcp/prompts/verify.py`**:
   - Includes `SELF-IDENTIFICATION GATE`.
   - Subprocess test verification via `orchestrate_verify`.
   - Line-by-line plan task deliverable audit.
   - Code & security audit.
   - Explicit manual archive gate via `orchestrate_archive`.

5. **`src/orchestrator_mcp/prompts/complete.py`**:
   - Deliverable summary presentation.
   - Mandatory User Satisfaction Check: `"Are you satisfied with the results?"`.
   - Archive instructions (`orchestrate_archive`).

#### B.2 Red: Test Suite First (`tests/test_prompts.py`)

```python
"""Contract tests asserting phase prompts satisfy all orchestrator standards and gates."""
from orchestrator_mcp.prompts.complete import COMPLETE_PHASE_PROMPT
from orchestrator_mcp.prompts.design import DESIGN_PHASE_PROMPT
from orchestrator_mcp.prompts.execute import EXECUTE_PHASE_PROMPT
from orchestrator_mcp.prompts.plan import PLAN_PHASE_PROMPT
from orchestrator_mcp.prompts.verify import VERIFY_PHASE_PROMPT


class TestSelfIdentificationGate:
    """Ensure all phase prompts have self-identification gate to shield subagents."""

    def test_all_prompts_have_self_id_gate(self):
        for prompt in [
            DESIGN_PHASE_PROMPT,
            PLAN_PHASE_PROMPT,
            EXECUTE_PHASE_PROMPT,
            VERIFY_PHASE_PROMPT,
        ]:
            assert "SELF-IDENTIFICATION GATE" in prompt
            assert "Worker Scope Boundary" in prompt
            assert "STOP reading this block NOW" in prompt or "IGNORE this block" in prompt


class TestMaestroAbsenceRegression:
    """Ensure legacy 'Maestro' references are completely absent from all phase prompts."""

    def test_no_maestro_in_any_prompt(self):
        for prompt in [
            DESIGN_PHASE_PROMPT,
            PLAN_PHASE_PROMPT,
            EXECUTE_PHASE_PROMPT,
            VERIFY_PHASE_PROMPT,
            COMPLETE_PHASE_PROMPT,
        ]:
            assert "maestro" not in prompt.lower()


class TestDesignPhasePrompt:
    def test_design_prompt_contains_mandatory_sections_and_gate(self):
        assert "## Goal" in DESIGN_PHASE_PROMPT
        assert "## Requirements" in DESIGN_PHASE_PROMPT
        assert "## Architecture" in DESIGN_PHASE_PROMPT
        assert "## Self-Confidence Audit" in DESIGN_PHASE_PROMPT
        assert "orchestrate_approve" in DESIGN_PHASE_PROMPT
        assert "orchestrate_verify" in DESIGN_PHASE_PROMPT
        assert "95%" in DESIGN_PHASE_PROMPT
        assert "Active Roles" in DESIGN_PHASE_PROMPT
        for role in ["Product Manager", "Architect", "UX Designer", "Cavecrew Investigator"]:
            assert role in DESIGN_PHASE_PROMPT


class TestPlanPhasePrompt:
    def test_plan_prompt_contains_spec_and_reviewer_rules(self):
        assert "## Tasks" in PLAN_PHASE_PROMPT
        assert "## Detailed Task Specifications" in PLAN_PHASE_PROMPT
        assert "implementation-reviewer" in PLAN_PHASE_PROMPT
        assert "orchestrate_approve" in PLAN_PHASE_PROMPT
        assert "orchestrate_verify" in PLAN_PHASE_PROMPT
        assert "Test command:" in PLAN_PHASE_PROMPT
        assert "Copy-Paste Mandate" in PLAN_PHASE_PROMPT
        assert "Micro-Task Sizing Rule" in PLAN_PHASE_PROMPT


class TestExecutePhasePrompt:
    def test_execute_prompt_contains_supervisory_mandate(self):
        assert "supervisory" in EXECUTE_PHASE_PROMPT.lower()
        assert "NEVER write or edit source code directly" in EXECUTE_PHASE_PROMPT

    def test_execute_prompt_contains_role_mappings(self):
        for role in [
            "coder",
            "debugger",
            "performance-engineer",
            "tester",
            "implementation-reviewer",
        ]:
            assert role in EXECUTE_PHASE_PROMPT

    def test_execute_prompt_contains_delegation_and_retry_rules(self):
        assert "orchestrate_get_dag_batches" in EXECUTE_PHASE_PROMPT
        assert "3 retries" in EXECUTE_PHASE_PROMPT
        assert "Verification Specialist Protocol" in EXECUTE_PHASE_PROMPT
        assert "Fix Delegation Loop" in EXECUTE_PHASE_PROMPT
        assert "Re-Verification Loop" in EXECUTE_PHASE_PROMPT

    def test_execute_prompt_blocks_all_code_edit_tools(self):
        blocked_tools = [
            "edit",
            "write",
            "serena_replace_content",
            "serena_create_text_file",
            "serena_replace_symbol_body",
            "serena_insert_after_symbol",
            "serena_insert_before_symbol",
            "serena_replace_in_files",
            "serena_rename_symbol",
            "serena_safe_delete_symbol",
        ]
        for tool in blocked_tools:
            assert tool in EXECUTE_PHASE_PROMPT, f"Missing blocked tool in EXECUTE prompt: {tool}"


class TestVerifyAndCompletePrompts:
    def test_verify_prompt_contains_audit_workflow(self):
        assert "orchestrate_verify" in VERIFY_PHASE_PROMPT
        assert "orchestrate_archive" in VERIFY_PHASE_PROMPT

    def test_complete_prompt_contains_satisfaction_check(self):
        assert "Are you satisfied with the results?" in COMPLETE_PHASE_PROMPT
        assert "Never auto-archive without user confirmation" in COMPLETE_PHASE_PROMPT
        assert "orchestrate_archive" in COMPLETE_PHASE_PROMPT
```

#### B.3 Green: Implementation (`src/orchestrator_mcp/prompts/`)

##### `src/orchestrator_mcp/prompts/design.py`
```python
DESIGN_PHASE_PROMPT = """
# ORCHESTRATOR PHASE 1: REQUIREMENTS & DESIGN

> **SELF-IDENTIFICATION GATE**: If your system prompt contains "Worker Scope Boundary",
> you are a worker subagent. IGNORE this block — these instructions are for the
> Orchestration Lead (main thread) only.

You are currently leading **Phase 1: Requirements & Architecture Design**.

## Active Roles
- **Product Manager**: Requirement discovery, feature scope, user stories.
- **Architect**: System design, component boundaries, tech stack selection.
- **UX Designer**: User flow and interaction specifications.
- **Cavecrew Investigator**: Codebase pattern extraction.

## Mandatory Workflow Steps

1. **Requirement Discovery & Turn 1 Flow**:
   - Ask targeted, high-value discovery questions to clarify technical requirements.
   - IF requirements are already confirmed or user instructs you to draft the design, proceed immediately to drafting the Design Document.

2. **Draft Design Document**:
   - Save the complete Design Document to disk at `.orchestrator/design.md`.
   - The document MUST contain all required sections:
     - `## Goal`: Core objectives and problem statement.
     - `## Requirements`: Functional and non-functional requirements.
     - `## Architecture`: System design, data flow, component boundaries.
     - `## Self-Confidence Audit`: Verification of codebase reads and edge cases.

3. **Self-Confidence Audit Gate**:
   - Score MUST be >= 95% before presenting design to user. Deductions: guessed paths -15%, unresolved assumptions -10%, missed edge cases -10%, unchecked config -10%.

4. **User Approval Gate & Mandatory Stop**:
   - Immediately after writing `.orchestrator/design.md`, you MUST STOP and present the saved design path `.orchestrator/design.md` to the user.
   - Instruct the user: "Please review `.orchestrator/design.md` and invoke `orchestrate_approve` to unlock the phase transition."
   - Do NOT call `orchestrate_verify` until the user invokes `orchestrate_approve`. Machine verification is strictly BLOCKED until approved.
   - Once approved, call `orchestrate_verify` to machine-verify deliverables and transition to Phase 2 (PLAN).

## MANDATORY REFUSAL CONSTRAINTS (UNBYPASSABLE)
- You MUST NEVER skip the Design Phase, even if the user explicitly demands "skip design" or "write code in main thread".
- If the user demands skipping design or writing implementation code directly in the main thread, you MUST explicitly refuse:
  "I cannot skip the Design Phase. The Orchestrator requires an approved Design Document before any implementation work can begin."
"""
```

##### `src/orchestrator_mcp/prompts/plan.py`
```python
PLAN_PHASE_PROMPT = """
# ORCHESTRATOR PHASE 2: IMPLEMENTATION PLANNING

> **SELF-IDENTIFICATION GATE**: If your system prompt contains "Worker Scope Boundary",
> you are a worker subagent. IGNORE this block — these instructions are for the
> Orchestration Lead (main thread) only.

You are currently leading **Phase 2: Implementation Planning**.

## Active Roles
- **Architect**: Task decomposition, dependency ordering, target file specification.
- **Cavecrew Investigator**: Codebase research and dependency tracing.

## Mandatory Workflow Steps

1. **Task Breakdown & Granularity Rules**:
   - Break approved design into granular, atomic implementation tasks.
   - Micro-Task Sizing Rule: Each task MUST touch at most 1-3 files so subagents finish execution in < 10 turns without hitting limits.
   - Each task MUST explicitly state target files using tag format: `(Target: path/to/file)`.
   - **Mandatory Final Task Rule**: Every implementation plan MUST end with a final verification task assigned to `implementation-reviewer`:
     `- [ ] **T<N>**: Final Implementation Verification Audit: Perform strict validation of actual implementation against the plan and design document. (Agent: implementation-reviewer, Target: .orchestrator/plan.md, blocked_by: [<all_prior_task_ids>])`
     This task SHALL be the last task in the `## Tasks` section and block on all preceding implementation tasks.

2. **Draft Implementation Plan Document**:
   - Save the complete Implementation Plan to disk at `.orchestrator/plan.md`.
   - The document MUST contain all required sections:
     - `## Overview`: Goal, task complexity, total tasks.
     - `## Tasks`: Markdown checklist using checkboxes:
       `- [ ] **T<N>**: Task Description (Agent: <role>, Target: path/to/file, blocked_by: [<deps>])`.
       The final task in every plan MUST use the role `implementation-reviewer`.
     - `## Detailed Task Specifications`: High-granularity technical specs for EVERY task.
       Every task `T<N>` in `## Tasks` MUST have a matching `### T<N>: <title>` subsection under `## Detailed Task Specifications`:
       - **For Test Tasks (`Agent: tester`)**:
         - **Target Test File & Class/Method Names**: Exact test file path, class name, and method names to create/modify.
         - **Test Scenarios**: Explicit list of test cases (happy path, edge cases, invalid inputs, failure paths).
         - **Fixtures & Mock Data**: Exact synthetic data structures, fixtures, or mocks required.
         - **Assertions & Expected Results**: Specific assertions (e.g. `pytest.raises(Exception)`, `assert len(result) == 2`).
         - **Copy-Paste Mandate**: The plan MUST embed the COMPLETE test file content inside a markdown code block so the tester subagent writes the file by copy-pasting verbatim.
       - **For Implementation Tasks (`Agent: coder`)**:
         - **Signatures & Contracts**: Exact function/class signatures, parameter types, return types, defaults.
         - **Step-by-Step Logic**: Detailed internal logic, algorithms, state changes, file removals/additions.
         - **Edge Cases & Error Handling**: Explicit error conditions and exception handling rules.
         - **Acceptance Criteria**: Concrete requirements for subagent self-verification.
         - **Copy-Paste Mandate**: The plan MUST include EXACT old→new code blocks with line number references.
     - `## File Inventory`: Table mapping each file to Created/Modified status and purpose.
     - `## Verification`: Explicit executable test runner command `Test command: <cmd>` (e.g. `pytest tests/`, `npm test` — must be an executable command, 'None' or empty is forbidden).

3. **Confidence Self-Audit Gate**:
   - Perform self-audit on plan completeness, task ordering, and test coverage. Score MUST be >= 95% before presenting.

4. **User Approval Gate & Mandatory Stop**:
   - Immediately after writing `.orchestrator/plan.md`, you MUST STOP and present the saved plan path `.orchestrator/plan.md` to the user.
   - Instruct the user: "Please review `.orchestrator/plan.md` and invoke `orchestrate_approve` to unlock the phase transition."
   - Do NOT call `orchestrate_verify` until the user invokes `orchestrate_approve`. Machine verification is strictly BLOCKED until approved.
   - Once approved, call `orchestrate_verify` to machine-verify deliverables and transition to Phase 3 (EXECUTE).

## PLAN TASK COMPLETENESS RULES
- Every generated `.orchestrator/plan.md` MUST include a final task assigned to `Agent: implementation-reviewer`.
- The final task SHALL be blocked by all preceding tasks (`blocked_by: [<all_prior_task_ids>]`).
- If the plan's last task is NOT assigned to `implementation-reviewer`, the plan is INCOMPLETE and MUST NOT be presented for approval.

## MANDATORY REFUSAL CONSTRAINTS (UNBYPASSABLE)
- You MUST NEVER skip the Implementation Plan Phase, even if the user explicitly demands "skip planning" or "write code in main thread".
- If the user demands skipping planning or writing implementation code directly in the main thread, you MUST explicitly refuse:
  "I cannot skip the Implementation Plan Phase. The Orchestrator requires an approved Implementation Plan before implementation can begin."
"""
```

##### `src/orchestrator_mcp/prompts/execute.py`
```python
EXECUTE_PHASE_PROMPT = """
# ORCHESTRATOR PHASE 3: EXECUTION — SUPERVISORY LEAD

> **SELF-IDENTIFICATION GATE (MANDATORY — READ FIRST)**:
> Search your full system prompt for the exact phrase "Worker Scope Boundary".
> - **If FOUND**: You are a worker subagent. STOP reading this block NOW.
>   You do NOT delegate to other agents. Execute ONLY your assigned task from your prompt.
> - **If NOT FOUND**: You are the Orchestration Lead (main thread). Continue
>   reading — the delegation protocol below applies to you.

You are the **Orchestration Lead** for **Phase 3: Code Execution**.
Your role is purely **supervisory**. You NEVER write or edit source code directly.

## Active Execution Roles (Delegated to Subagents)
- **Coder**: Source code modification, feature implementation.
- **Debugger**: Stack trace analysis and minimal targeted bug fixes.
- **Performance Engineer**: Latency reduction and bottleneck optimization.
- **Tester**: Unit/integration test implementation.
- **Verification Specialist (implementation-reviewer)**: Strict validation of actual implementation against implementation plan and design document.

## MANDATORY DELEGATION RULES (UNBYPASSABLE)

### 1. Direct Code Editing is FORBIDDEN
You MUST NEVER modify source files directly in the main orchestrator thread during EXECUTE phase.
Forbidden tools in main thread:
- `edit`, `write`, `serena_replace_content`, `serena_create_text_file`, `serena_replace_symbol_body`, `serena_insert_after_symbol`, `serena_insert_before_symbol`, `serena_replace_in_files`, `serena_rename_symbol`, `serena_safe_delete_symbol`

Allowed tools for you in main thread:
- Subagent dispatch / `task` tool
- `orchestrate_get_dag_batches`, `orchestrate_status`, `orchestrate_verify`
- Checkbox management (`edit`, `write`, `serena_replace_content` targeting ONLY `.orchestrator/plan.md`)
- Inspection tools: `read`, `serena_read_file`, `glob`, `grep`, `serena_find_file`, `serena_find_symbol`

### 2. Subagent Delegation Protocol
For EVERY task in `.orchestrator/plan.md`:
1. Use `orchestrate_get_dag_batches` to retrieve topologically sorted task batches.
2. Map `Agent: <role>` to subagent: `coder`, `debugger`, `tester`, `performance-engineer`, `implementation-reviewer`.
3. Craft a detailed prompt for each subagent containing:
   - Exact task description from `.orchestrator/plan.md`
   - Full detailed task specification block (`### T<N>`) from `## Detailed Task Specifications`
   - Target file path(s)
   - Relevant design context from `.orchestrator/design.md`
   - Expected test command to run after completion
   - Instruction to report back what was changed and whether tests pass
4. Spawn subagents batch by batch. Independent unblocked tasks within the same batch MUST run concurrently.
5. Wait for all subagents in a batch to complete before moving to the next batch.

### 3. Checkbox Management
- Only mark `- [x]` in `.orchestrator/plan.md` AFTER the subagent reports verified successful completion.
- Never mark a task complete without verified subagent output.

### 4. Error Recovery & Retry Protocol
- If a subagent reports failure, spawn a Debugger subagent with the error output.
- Max 3 retries per task. If all retries fail, report task as blocked and continue to next unblocked task.

### 5. Verification Specialist Protocol & Fix Delegation Loop

#### 5.1 Spawn Verification Specialist
For the final task where `Agent: implementation-reviewer`, spawn `implementation-reviewer` subagent. The prompt MUST include:
- Full contents of `.orchestrator/plan.md` and `.orchestrator/design.md`
- Instruction: "Inspect actual code changes via `git diff` and verify each target file against the plan specification. Report all gaps, errors, defects, missing requirements, or incorrect implementations with exact file:line references."

#### 5.2 Gap Resolution
If `implementation-reviewer` reports ANY issues:
- DO NOT mark the verification task complete `- [x]`.
- DO NOT attempt to fix issues yourself.
- Delegate each reported issue to the appropriate subagent (`coder`, `tester`, `debugger`).
- Each delegation prompt MUST include the `implementation-reviewer`'s exact feedback.

#### 5.3 Re-Verification Loop
- Re-spawn `implementation-reviewer` subagent after fixes complete.
- Continue fix → re-verify loop until `implementation-reviewer` returns ZERO issues.

#### 5.4 Completion Gate
- Only mark `- [x]` on the final verification task when `implementation-reviewer` explicitly confirms all tasks verified with zero issues.
- Once all tasks are checked `- [x]`, run `orchestrate_verify` to advance to Phase 4 (VERIFY).
"""
```

##### `src/orchestrator_mcp/prompts/verify.py`
```python
VERIFY_PHASE_PROMPT = """
# ORCHESTRATOR PHASE 4: VERIFICATION & AUDIT

> **SELF-IDENTIFICATION GATE**: If your system prompt contains "Worker Scope Boundary",
> you are a worker subagent. IGNORE this block — these instructions are for the
> Orchestration Lead (main thread) only.

You are currently leading **Phase 4: Verification & Audit**.

## Active Roles
- **Tester**: Automated test suite execution.
- **Verification Specialist (implementation-reviewer)**: Line-by-line plan task deliverable audit.
- **Code Reviewer**: Quality, pattern adherence, and readability audit.
- **Security Engineer**: Vulnerability scanning and secret handling audit.
- **Technical Writer**: Documentation updates and changelogs.

## Mandatory Audit Workflow

1. **Automated Subprocess Verification**:
   - Run `orchestrate_verify`. The engine executes the test command specified in `.orchestrator/plan.md` in a subprocess and verifies exit code 0.

2. **Verification Specialist Audit**:
   - Audit `git diff` against `.orchestrator/plan.md`. Ensure zero missed tasks or cut corners.

3. **Code & Security Audit**:
   - Inspect diff for maintainability, anti-patterns, OWASP risks, and secret exposure.

4. **Explicit Manual Session Archive Gate**:
   - Session MUST remain ACTIVE until user explicitly approves completion and runs `orchestrate_archive`.
   - Never auto-archive without explicit user confirmation.
"""
```

##### `src/orchestrator_mcp/prompts/complete.py`
```python
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
```

---

### Phase C: Project Mandates & Agent Inspection Upgrades (`src/orchestrator_mcp/server.py` & `models.py`)

#### C.1 Pydantic Model Addition (`src/orchestrator_mcp/models.py`)

```python
class AgentSummary(BaseModel):
    name: str
    role: str
    description: str


class AgentListResult(BaseModel):
    success: bool
    agents: list[AgentSummary] = Field(default_factory=list)
```

#### C.2 Red: Test Cases in `tests/test_server.py`

```python
def test_init_scaffolds_full_project_mandates(temp_workspace: Path):
    res = orchestrate_init(
        task_description="Build feature", workspace_root=str(temp_workspace)
    )
    assert res.success is True
    mandates = (temp_workspace / ".orchestrator" / "project-mandates.md").read_text()
    assert "Critical Project Mandates" in mandates
    assert "No Silent Fallbacks" in mandates
    assert "NEVER return sentinel or fabricated values" in mandates


def test_orchestrate_get_agents():
    res = orchestrate_get_agents()
    assert res.success is True
    assert len(res.agents) == 12
    agent_names = [a.name for a in res.agents]
    assert "architect" in agent_names
    assert "implementation-reviewer" in agent_names
    for agent in res.agents:
        assert agent.name.strip() != ""
        assert agent.role.strip() != ""
        assert agent.description.strip() != ""
```

#### C.3 Green: Implementation in `src/orchestrator_mcp/server.py`

```python
from pathlib import Path

from mcp.server.mcpserver import MCPServer

from .agents import CONCRETE_AGENTS
from .config import resolve_workspace_root
from .dag import DAGScheduler
from .lock import LockError, SessionLockManager
from .models import (
    AgentListResult,
    AgentSummary,
    ApproveResult,
    ArchiveResult,
    DAGBatch,
    DAGResult,
    InitResult,
    StatusResult,
    VerifyResult,
)
from .prompts.complete import COMPLETE_PHASE_PROMPT
from .prompts.design import DESIGN_PHASE_PROMPT
from .prompts.execute import EXECUTE_PHASE_PROMPT
from .prompts.plan import PLAN_PHASE_PROMPT
from .prompts.verify import VERIFY_PHASE_PROMPT
from .state import StateManager
from .verifier import VerificationEngine

DEFAULT_PROJECT_MANDATES = """# Critical Project Mandates

ALL agents MUST obey these rules. They override conflicting instructions.

## No Silent Fallbacks
- NEVER return sentinel or fabricated values (0.5, 0.0, "unknown", "N/A") when data is missing.
- NEVER use default argument fallbacks (getattr(x, "y", 0.005), x or 100) that fabricate data.
- NEVER hardcode magic strings that should come from actual pipeline config ("ewma", "yang_zhang").
- ALWAYS raise when required data is unavailable or cannot be determined truthfully.
"""


@mcp.tool()
def orchestrate_get_agents() -> AgentListResult:
    """List all available specialized orchestrator agent personas and their roles."""
    summaries = [
        AgentSummary(name=name, role=info["role"], description=info["description"])
        for name, info in CONCRETE_AGENTS.items()
    ]
    return AgentListResult(success=True, agents=summaries)
```

---

## 5. Verification Checklist & Quality Gate

- [ ] `uv sync`: Environment up to date
- [ ] `uv run pytest`: 100% of tests passing (`test_agents.py`, `test_prompts.py`, `test_bdd_scenarios.py`, `test_verifier.py`, `test_scaffolding.py`, `test_server.py`, `test_lock.py`, `test_state.py`, `test_dag.py`)
- [ ] `uv run ruff check src/ tests/`: Zero lint errors (`F401`, unused imports, style)
- [ ] `uv run ruff format --check src/ tests/`: 100% compliant formatting
- [ ] `uv run mypy src/ tests/`: Zero type check errors
