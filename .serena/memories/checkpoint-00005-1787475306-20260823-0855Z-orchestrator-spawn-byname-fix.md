# Checkpoint 00005 — Orchestrator spawn-by-name fix

## State
- Orchestrator session 2026-08-23-develop-a-python-script-that-p (hello.py test task) archived mid-EXECUTE.
- T1 done: hello.py created at repo root (print("hello")), verified exit 0, ruff clean. T2 (implementation-reviewer final audit) never ran.

## Changes landed this session (MCP server, /home/eusti/dev/orchestrate)
- src/orchestrator_mcp/prompts/execute.py: added Spawn-by-Name: Role IDs are Authoritative block — plan role IDs (coder, debugger, tester, performance-engineer, implementation-reviewer) are registered OpenCode subagents spawnable by exact ID; subagent tool Available subagents list is a filtered projection (excludes hidden/primary/denied); never substitute general/explore unless spawn fails with Unknown agent.
- src/orchestrator_mcp/server.py (~line 214): orchestrate_get_agents docstring now states each name is a spawnable OpenCode subagent ID even if hidden from catalog.
- Verified: uv run ruff check src/ tests/ clean; uv run pytest 109 passed.

## Root cause found
- ~/dev/opencode/packages/core/src/tool/plugin/subagent.ts:307-332 — subagent catalog is a runtime-filtered projection (mode != primary, !hidden, permission != deny). All 12 orchestrator persona markdown files in ~/.config/opencode/agents/*.md carry hidden: true, so only explore/general advertised, but name-based spawn (agents.resolve, subagent.ts:163) ignores hidden. Hidden-by-design; fix = SOP authority, not un-hiding.

## Next steps
- If resuming: re-run orchestrate_init for hello.py task or new task; complete T2 implementation-reviewer audit per new SOP.
- Consider same spawn-by-name note for DESIGN/PLAN prompts if they ever reference spawnable agents.