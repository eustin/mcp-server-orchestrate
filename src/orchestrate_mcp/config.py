from pathlib import Path


def resolve_workspace_root(start_path: Path | None = None) -> Path:
    """Find the workspace root by looking upward for .git or .opencode."""
    curr = (start_path or Path.cwd()).resolve()
    for parent in [curr] + list(curr.parents):
        if (parent / ".git").exists() or (parent / ".opencode").exists():
            return parent
    return curr


def get_orchestrator_dir(workspace_root: Path | None = None) -> Path:
    """Return the .orchestrator directory path, ensuring it exists."""
    root = workspace_root or resolve_workspace_root()
    orch_dir = root / ".orchestrator"
    orch_dir.mkdir(parents=True, exist_ok=True)
    return orch_dir
