from orchestrator_mcp.dag import DAGScheduler


def test_build_independent_batches() -> None:
    tasks = [
        {"id": "T1", "target": "src/a.py", "blocked_by": []},
        {"id": "T2", "target": "src/b.py", "blocked_by": []},
        {"id": "T3", "target": "src/c.py", "blocked_by": ["T1", "T2"]},
    ]
    batches = DAGScheduler.build_execution_batches(tasks)
    assert len(batches) == 2
    assert [t["id"] for t in batches[0]] == ["T1", "T2"]
    assert [t["id"] for t in batches[1]] == ["T3"]


def test_file_collision_guard() -> None:
    tasks = [
        {"id": "T1", "target": "src/auth.py", "blocked_by": []},
        {"id": "T2", "target": "src/auth.py", "blocked_by": []},
    ]
    batches = DAGScheduler.build_execution_batches(tasks)
    assert len(batches) == 2
    assert [t["id"] for t in batches[0]] == ["T1"]
    assert [t["id"] for t in batches[1]] == ["T2"]
    assert "T1" in tasks[1]["blocked_by"]


def test_circular_dependency_fallback() -> None:
    tasks = [
        {"id": "T1", "target": "a.py", "blocked_by": ["T2"]},
        {"id": "T2", "target": "b.py", "blocked_by": ["T1"]},
    ]
    batches = DAGScheduler.build_execution_batches(tasks)
    assert len(batches) >= 1


def test_empty_tasks() -> None:
    batches = DAGScheduler.build_execution_batches([])
    assert batches == []


def test_multiple_file_collisions() -> None:
    tasks = [
        {"id": "T1", "target": "src/auth.py", "blocked_by": []},
        {"id": "T2", "target": "src/auth.py", "blocked_by": []},
        {"id": "T3", "target": "src/auth.py", "blocked_by": []},
    ]
    batches = DAGScheduler.build_execution_batches(tasks)
    assert len(batches) == 3
    assert [t["id"] for t in batches[0]] == ["T1"]
    assert [t["id"] for t in batches[1]] == ["T2"]
    assert [t["id"] for t in batches[2]] == ["T3"]
