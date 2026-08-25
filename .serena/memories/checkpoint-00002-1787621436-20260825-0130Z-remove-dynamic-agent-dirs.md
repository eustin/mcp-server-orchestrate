# Checkpoint 00002 — Remove dynamic OpenCode agent dir resolution

## State
- `resolve_opencode_agents_dirs` REMOVED from `src/orchestrate_mcp/agents.py`. Personas are bundled in the package, so dynamic multi-dir search (ws/.opencode, ws/agents, global config) was dead weight + OpenCode coupling.
- `load_agent_prompt(name: str) -> str` simplified: reads `BUNDLED_AGENTS_DIR / f"{name}.md"` only, stub fallback `# Agent Persona: {name.title()}\nRole: Specialist for {name}.` for unknown names.
- Dropped now-unused imports in agents.py: `import os`, `from .config import resolve_workspace_root`.
- `__init__.py` exports: now `BUNDLED_AGENTS_DIR`, `CONCRETE_AGENTS`, `get_agent_info`, `load_agent_prompt` (removed resolve_opencode_agents_dirs).
- `agents.py` order: docstring, imports, `BUNDLED_AGENTS_DIR`, `CONCRETE_AGENTS`, `class AgentInfo`, `load_agent_prompt`, `get_agent_info`.

## Verification
- `uv run pytest`: 113 passed (was 118; 5 obsolete tests removed).
- `uv run ruff check src/ tests/`: clean.
- `uv run mypy src/ tests/`: clean (25 files).

## Tests rewritten (tests/test_agents.py)
Removed: resolve_opencode_agents_dirs order/xdg tests, workspace-load, home-config-load, user-override-beats-bundled, old frontmatter test.
Kept/rewritten: registry 8 roles, bundled covers all roles, bundled = source of truth, frontmatter preserved (startswith "---", contains "mode: subagent"), stub fallback unknown name, get_agent_info.

## Next steps
- Scrub remaining OpenCode-specific leaks (user asked; pending decision):
  1. `config.py:8` — `.opencode` workspace-root marker (harmless, `.git` primary)
  2. `server.py:214` — docstring references `subagent` tool / hidden catalog
  3. `execute.py:50-53` — prompt teaches `subagent` tool + `general`/`explore` fallback
- Update README + `.dev/*` docs: agent count 12 -> 8 (still says 12).
- Pre-existing EXECUTE prompt contradiction: `edit`/`write`/`serena_replace_content` in both forbidden + allowed (checkbox) lists.
