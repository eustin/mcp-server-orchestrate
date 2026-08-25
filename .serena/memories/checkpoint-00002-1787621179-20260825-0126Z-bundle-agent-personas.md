# Checkpoint 00002 — Bundle agent personas into package

## State
- `src/orchestrate_mcp/agents/` now holds 8 bundled OpenCode persona `.md` files (architect, product-manager, coder, debugger, tester, implementation-reviewer, code-reviewer, technical-writer).
- Wheel verified to ship them as package data (hatchling auto-includes files under package dir) — uvx/pip users get real personas.
- `BUNDLED_AGENTS_DIR` = `Path(__file__).parent/"agents"`, appended LAST in `resolve_opencode_agents_dirs` search list → user override dirs win, bundled is fallback, stub only for unknown names.
- Removed 4 roles entirely: `ux-designer`, `cavecrew-investigator`, `performance-engineer`, `security-engineer` (registry, prompts, tests).
- Prompts edited: design.py dropped UX Designer/Cavecrew Investigator, plan.py dropped Cavecrew Investigator, execute.py dropped Performance Engineer (active roles + delegation map), verify.py dropped Security Engineer.
- Constants at module top in `agents.py` (BUNDLED_AGENTS_DIR + CONCRETE_AGENTS before class AgentInfo). `__all__` stays at bottom in prompts/__init__.py (convention).
- Toolchain: ruff (lint+format), mypy, pytest. No black.

## Progress / Verification
- `uv run pytest`: 118 passed.
- `uv run ruff check src/ tests/`: clean.
- `uv run mypy src/ tests/`: clean (25 files).
- `uv build`: wheel contains `orchestrate_mcp/agents/*.md`.

## Tests updated (tests/)
- test_agents.py: registry 12->8 roles; `resolve_opencode_agents_dirs` expected list + bundled entry; +3 tests (bundled fallback == source of truth, user override beats bundled, bundled covers all registered roles).
- test_server.py: `orchestrate_get_agents` len 12->8.
- test_prompts.py: design role list -> [Product Manager, Architect]; execute role mappings dropped performance-engineer.

## Next steps
- Update README + `.dev/*` docs: agent count 12 -> 8 (still says 12).
- Pre-existing EXECUTE prompt contradiction (Defect 2): `edit`/`write`/`serena_replace_content` appear in BOTH forbidden and allowed (checkbox) lists — fix or document.
- Loader gap: 8 bundled personas found when user dirs empty; already covered by test_bundled_covers_all_registered_roles.
