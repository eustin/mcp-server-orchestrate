from pathlib import Path


def resolve_workspace_root(start_path: Path | None = None) -> Path:
    """Return the directory the agent session runs in (the MCP server's cwd)."""
    return (start_path or Path.cwd()).resolve()


def get_orchestrator_dir(workspace_root: Path | None = None) -> Path:
    """Return the .orchestrator directory path, ensuring it exists."""
    root = workspace_root or resolve_workspace_root()
    orch_dir = root / ".orchestrator"
    orch_dir.mkdir(parents=True, exist_ok=True)
    return orch_dir
