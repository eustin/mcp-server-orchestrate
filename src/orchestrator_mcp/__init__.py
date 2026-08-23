"""Orchestrator MCP Server package."""

from .agents import CONCRETE_AGENTS, get_agent_info, load_agent_prompt, resolve_opencode_agents_dirs

__all__ = [
    "CONCRETE_AGENTS",
    "get_agent_info",
    "load_agent_prompt",
    "resolve_opencode_agents_dirs",
]

__version__ = "0.1.0"
