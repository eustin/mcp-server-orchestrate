# Checkpoint 00002 — Remove remaining OpenCode references

## State
- Repo now clean of opencode coupling. `rg -in "opencode"` (excluding orchestrate*): single hit = README client-config example (intentional, docs for connecting a client).
- BDD leftovers removed: `tests/features/orchestrate.feature:7` and `tests/test_bdd_scenarios.py:48` — "Given a project workspace directory" (was "...initialized with Git or OpenCode configuration", referenced deleted `.opencode` marker logic).
- README.md: heading "OpenCode MCP Configuration" -> "MCP Client Configuration"; schema corrected to real opencode format (`mcp` + `type: local` + `command` array, `--project` flag, no `cwd`). TOC updated.

## Verification
- `uv run pytest`: 114 passed.
- `uv run ruff check src/ tests/`: clean.
- `uv run mypy src/ tests/`: clean (25 files).

## Session context (prior commits this session)
- 2efc9d7: bundle 8 personas, trim registry to 8 (removed ux-designer, cavecrew-investigator, performance-engineer, security-engineer)
- 49183a9: drop dynamic dir resolution (resolve_opencode_agents_dirs removed)
- 05023d5: resolve workspace to session cwd, remove workspace_root from all tools

## Next steps
- Update `.dev/*` gitignored docs: agent count 12 -> 8, workspace_root removal, dynamic loader removal.
- Pre-existing EXECUTE prompt contradiction: `edit`/`write`/`serena_replace_content` appear in BOTH forbidden list AND allowed (checkbox management) list in execute.py prompt — fix or document.
- server.py:214 docstring still says "registered OpenCode subagent ID ... `subagent` tool" — decide whether to generalize (it's prompt/docs text, not runtime coupling).
