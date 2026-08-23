"""Tests for dynamic OpenCode agent discovery and persona loading."""

from pathlib import Path
from unittest.mock import patch

from orchestrator_mcp.agents import (
    CONCRETE_AGENTS,
    get_agent_info,
    load_agent_prompt,
    resolve_opencode_agents_dirs,
)


def test_concrete_agents_registry_has_all_12_roles() -> None:
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


def test_resolve_opencode_agents_dirs_order_default_env(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    ws_opencode_agents = ws / ".opencode" / "agents"
    ws_agents = ws / "agents"
    home = tmp_path / "home"
    home_config_agents = home / ".config" / "opencode" / "agents"
    home_opencode_agents = home / ".opencode" / "agents"

    with patch("pathlib.Path.home", return_value=home), patch.dict("os.environ", {}, clear=True):
        dirs = resolve_opencode_agents_dirs(ws)
        assert dirs == [
            ws_opencode_agents,
            ws_agents,
            home_config_agents,
            home_opencode_agents,
        ]


def test_resolve_opencode_agents_dirs_with_xdg_env(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    custom_xdg = tmp_path / "custom_config"
    home = tmp_path / "home"

    with (
        patch("pathlib.Path.home", return_value=home),
        patch.dict("os.environ", {"XDG_CONFIG_HOME": str(custom_xdg)}, clear=True),
    ):
        dirs = resolve_opencode_agents_dirs(ws)
        assert dirs[2] == custom_xdg / "opencode" / "agents"


def test_load_agent_prompt_from_workspace(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws_agents = ws / "agents"
    ws_agents.mkdir(parents=True)
    custom_coder = ws_agents / "coder.md"
    custom_coder.write_text("# Workspace Custom Coder Persona", encoding="utf-8")

    prompt = load_agent_prompt("coder", workspace_root=ws)
    assert prompt == "# Workspace Custom Coder Persona"


def test_load_agent_prompt_from_home_config(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    home = tmp_path / "home"
    config_agents = home / ".config" / "opencode" / "agents"
    config_agents.mkdir(parents=True)
    (config_agents / "tester.md").write_text("# Global Tester Persona", encoding="utf-8")

    with patch("pathlib.Path.home", return_value=home), patch.dict("os.environ", {}, clear=True):
        prompt = load_agent_prompt("tester", workspace_root=ws)
        assert prompt == "# Global Tester Persona"


def test_load_agent_prompt_preserves_frontmatter(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws_agents = ws / "agents"
    ws_agents.mkdir(parents=True)
    agent_file = ws_agents / "architect.md"
    raw_content = "---\nmode: subagent\nhidden: true\n---\n# Agent Persona: Architect"
    agent_file.write_text(raw_content, encoding="utf-8")

    prompt = load_agent_prompt("architect", workspace_root=ws)
    assert prompt == raw_content


def test_load_agent_prompt_fallback_when_file_not_found(tmp_path: Path) -> None:
    ws = tmp_path / "workspace"
    ws.mkdir()
    with (
        patch("pathlib.Path.home", return_value=tmp_path / "empty_home"),
        patch.dict("os.environ", {}, clear=True),
    ):
        prompt = load_agent_prompt("nonexistent-role", workspace_root=ws)
        assert "Agent Persona: Nonexistent-Role" in prompt
        assert "Specialist for nonexistent-role" in prompt


def test_get_agent_info_helper() -> None:
    info = get_agent_info("architect")
    assert info is not None
    assert info["role"] == "System Architect"
