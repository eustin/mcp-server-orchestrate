"""Tests for bundled agent personas and persona loading."""

from orchestrate_mcp.agents import (
    BUNDLED_AGENTS_DIR,
    CONCRETE_AGENTS,
    get_agent_info,
    load_agent_prompt,
)


def test_concrete_agents_registry_has_all_8_roles() -> None:
    expected_roles = [
        "architect",
        "product-manager",
        "coder",
        "debugger",
        "tester",
        "implementation-reviewer",
        "code-reviewer",
        "technical-writer",
    ]
    for role in expected_roles:
        assert role in CONCRETE_AGENTS, f"Missing role in CONCRETE_AGENTS: {role}"
        info = CONCRETE_AGENTS[role]
        assert "role" in info
        assert "description" in info
        assert callable(info["prompt_fn"])


def test_bundled_agents_dir_covers_all_registered_roles() -> None:
    assert BUNDLED_AGENTS_DIR.is_dir()
    for role in CONCRETE_AGENTS:
        assert (BUNDLED_AGENTS_DIR / f"{role}.md").is_file(), (
            f"Missing bundled persona file for role: {role}"
        )


def test_load_agent_prompt_returns_bundled_source_of_truth() -> None:
    prompt = load_agent_prompt("coder")
    expected = (BUNDLED_AGENTS_DIR / "coder.md").read_text(encoding="utf-8")
    assert prompt == expected


def test_load_agent_prompt_preserves_frontmatter() -> None:
    prompt = load_agent_prompt("architect")
    assert prompt.startswith("---")
    assert "mode: subagent" in prompt


def test_load_agent_prompt_fallback_when_file_not_found() -> None:
    prompt = load_agent_prompt("nonexistent-role")
    assert "Agent Persona: Nonexistent-Role" in prompt
    assert "Specialist for nonexistent-role" in prompt


def test_get_agent_info_helper() -> None:
    info = get_agent_info("architect")
    assert info is not None
    assert info["role"] == "System Architect"
