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
