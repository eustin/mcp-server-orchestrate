"""Concrete Agent Personas and Bundled Persona Loading."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import TypedDict

BUNDLED_AGENTS_DIR: Path = Path(__file__).resolve().parent / "agents"


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
    "technical-writer": {
        "role": "Technical Writer",
        "description": "Technical writer specializing in clear, accurate developer documentation, API contracts, READMEs, and architecture docs.",
        "prompt_fn": lambda: load_agent_prompt("technical-writer"),
    },
}


class AgentInfo(TypedDict):
    role: str
    description: str
    prompt_fn: Callable[[], str]


def load_agent_prompt(name: str) -> str:
    """Load the bundled persona prompt for the given agent role."""
    agent_file = BUNDLED_AGENTS_DIR / f"{name}.md"
    try:
        return agent_file.read_text(encoding="utf-8")
    except OSError:
        return f"# Agent Persona: {name.title()}\nRole: Specialist for {name}."


def get_agent_info(name: str) -> AgentInfo | None:
    """Retrieve metadata and prompt resolver for given agent role."""
    return CONCRETE_AGENTS.get(name)
