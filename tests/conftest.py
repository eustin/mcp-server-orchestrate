import subprocess
from collections.abc import Generator
from pathlib import Path
from unittest.mock import patch

import pytest


@pytest.fixture
def temp_workspace(tmp_path: Path) -> Path:
    """Create an isolated temporary workspace initialized with git."""
    ws = tmp_path / "workspace"
    ws.mkdir()
    subprocess.run(["git", "init"], cwd=ws, check=True, capture_output=True)
    orch_dir = ws / ".orchestrator"
    orch_dir.mkdir()
    return ws


@pytest.fixture
def mock_alive_pid() -> Generator[None, None, None]:
    """Mock os.kill to simulate a running process."""
    with patch("os.kill", return_value=None):
        yield


@pytest.fixture
def mock_dead_pid() -> Generator[None, None, None]:
    """Mock os.kill to simulate a dead process."""
    with patch("os.kill", side_effect=ProcessLookupError):
        yield
