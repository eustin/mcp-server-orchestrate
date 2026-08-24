from pathlib import Path

from orchestrator_mcp.verifier import VerificationEngine


def test_verify_design_missing_file(temp_workspace: Path) -> None:
    valid, errors = VerificationEngine.verify_design(temp_workspace, is_approved=True)
    assert valid is False
    assert any("Missing required deliverable" in e for e in errors)


def test_verify_design_unapproved(temp_workspace: Path) -> None:
    (temp_workspace / ".orchestrator" / "design.md").write_text(
        "## Requirements\n## Architecture\n## Self-Confidence Audit\n"
    )
    valid, errors = VerificationEngine.verify_design(temp_workspace, is_approved=False)
    assert valid is False
    assert any("GATE BLOCKED" in e for e in errors)


def test_verify_design_missing_sections(temp_workspace: Path) -> None:
    (temp_workspace / ".orchestrator" / "design.md").write_text("## Requirements\n")
    valid, errors = VerificationEngine.verify_design(temp_workspace, is_approved=True)
    assert valid is False
    assert any("Missing required Design Document section" in e for e in errors)


def test_verify_design_success(temp_workspace: Path) -> None:
    (temp_workspace / ".orchestrator" / "design.md").write_text(
        "## Requirements\nDetail\n## Architecture\nDetail\n## Self-Confidence Audit\nDetail\n"
    )
    valid, errors = VerificationEngine.verify_design(temp_workspace, is_approved=True)
    assert valid is True
    assert len(errors) == 0


def test_verify_plan_missing_file(temp_workspace: Path) -> None:
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=True)
    assert valid is False
    assert any("Missing required deliverable" in e for e in errors)


def test_verify_plan_unapproved(temp_workspace: Path) -> None:
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: Code (Agent: coder) (Target: a.py) (blocked_by: [])\n"
        "- [ ] **T2**: Review (Agent: implementation-reviewer) (Target: a.py) (blocked_by: [T1])\n"
        "## Detailed Task Specifications\n"
        "### T1\nSpec 1\n"
        "### T2\nSpec 2\n"
        "## Verification\n"
        "Test command: pytest tests/\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=False)
    assert valid is False
    assert any("GATE BLOCKED" in e for e in errors)


def test_verify_plan_invalid_tags(temp_workspace: Path) -> None:
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: Code missing target and blocked_by (Agent: coder)\n"
        "- [ ] **T2**: Review (Agent: implementation-reviewer) (Target: a.py) (blocked_by: [T1])\n"
        "## Detailed Task Specifications\n"
        "### T1\nSpec 1\n"
        "### T2\nSpec 2\n"
        "## Verification\n"
        "Test command: pytest tests/\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=True)
    assert valid is False
    assert any("missing required" in e for e in errors)


def test_verify_plan_missing_detailed_spec(temp_workspace: Path) -> None:
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: Code (Agent: coder) (Target: a.py) (blocked_by: [])\n"
        "- [ ] **T2**: Review (Agent: implementation-reviewer) (Target: a.py) (blocked_by: [T1])\n"
        "## Detailed Task Specifications\n"
        "### T1\nSpec 1\n"
        "## Verification\n"
        "Test command: pytest tests/\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=True)
    assert valid is False
    assert any("missing detailed specification heading" in e for e in errors)


def test_verify_plan_invalid_reviewer_barrier(temp_workspace: Path) -> None:
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: Task 1 (Agent: coder) (Target: a.py) (blocked_by: [])\n"
        "## Detailed Task Specifications\n"
        "### T1\nDetail\n"
        "## Verification\n"
        "Test command: pytest\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=True)
    assert valid is False
    assert any("Agent: implementation-reviewer" in e for e in errors)


def test_verify_plan_invalid_test_command(temp_workspace: Path) -> None:
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: Code (Agent: coder) (Target: a.py) (blocked_by: [])\n"
        "- [ ] **T2**: Review (Agent: implementation-reviewer) (Target: a.py) (blocked_by: [T1])\n"
        "## Detailed Task Specifications\n"
        "### T1\nSpec 1\n"
        "### T2\nSpec 2\n"
        "## Verification\n"
        "Test command: None\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=True)
    assert valid is False
    assert any("None" in e or "invalid" in e.lower() for e in errors)


def test_verify_plan_success(temp_workspace: Path) -> None:
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: Code (Agent: coder) (Target: a.py) (blocked_by: [])\n"
        "- [ ] **T2**: Review (Agent: implementation-reviewer) (Target: a.py) (blocked_by: [T1])\n"
        "## Detailed Task Specifications\n"
        "### T1\nSpec 1\n"
        "### T2\nSpec 2\n"
        "## Verification\n"
        "Test command: pytest tests/\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=True)
    assert valid is True
    assert len(errors) == 0


def test_verify_execution_unchecked_tasks(temp_workspace: Path) -> None:
    plan = "## Tasks\n- [ ] **T1**: Unfinished (Agent: coder) (Target: a.py) (blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is False
    assert any("is incomplete" in e for e in errors)


def test_verify_execution_missing_target_file(temp_workspace: Path) -> None:
    plan = "## Tasks\n- [x] **T1**: Done (Agent: coder) (Target: src/missing.py) (blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is False
    assert any("does not exist" in e for e in errors)


def test_verify_execution_zero_byte_target_file(temp_workspace: Path) -> None:
    plan = "## Tasks\n- [x] **T1**: Done (Agent: coder) (Target: src/empty.py) (blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    target = temp_workspace / "src" / "empty.py"
    target.parent.mkdir(parents=True)
    target.touch()

    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is False
    assert any("is 0 bytes" in e for e in errors)


def test_verify_execution_success(temp_workspace: Path) -> None:
    plan = "## Tasks\n- [x] **T1**: Done (Agent: coder) (Target: src/main.py) (blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    target = temp_workspace / "src" / "main.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hello')")

    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is True
    assert len(errors) == 0


def test_verify_execution_canonical_missing_target_file(temp_workspace: Path) -> None:
    plan = "## Tasks\n- [x] **T1**: Done (Agent: coder, Target: src/missing.py, blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is False
    assert any("does not exist" in e for e in errors)


def test_verify_execution_canonical_zero_byte_target_file(temp_workspace: Path) -> None:
    plan = "## Tasks\n- [x] **T1**: Done (Agent: coder, Target: src/empty.py, blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    target = temp_workspace / "src" / "empty.py"
    target.parent.mkdir(parents=True)
    target.touch()

    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is False
    assert any("is 0 bytes" in e for e in errors)


def test_verify_execution_canonical_success(temp_workspace: Path) -> None:
    plan = "## Tasks\n- [x] **T1**: Done (Agent: coder, Target: src/main.py, blocked_by: [])\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    target = temp_workspace / "src" / "main.py"
    target.parent.mkdir(parents=True)
    target.write_text("print('hello')")

    valid, errors = VerificationEngine.verify_execution(temp_workspace)
    assert valid is True
    assert len(errors) == 0


def test_verify_testing_command_failure(temp_workspace: Path) -> None:
    plan = "## Verification\nTest command: exit 1\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_testing(temp_workspace)
    assert valid is False
    assert any("Automated test runner failed" in e for e in errors)


def test_verify_testing_command_success(temp_workspace: Path) -> None:
    plan = "## Verification\nTest command: exit 0\n"
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_testing(temp_workspace)
    assert valid is True
    assert len(errors) == 0


def test_verify_testing_ignores_task_spec_self_verification_bullet(temp_workspace: Path) -> None:
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: task 1 (Agent: coder, Target: a.py, blocked_by: [])\n"
        "## Detailed Task Specifications\n"
        "### T1\n"
        "- **Test command for self-verification**: `exit 2`\n"
        "- **Test command for T1**: `exit 2`\n"
        "## Verification\n"
        "Test command: exit 0\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_testing(temp_workspace)
    assert valid is True
    assert len(errors) == 0


def test_verify_testing_various_markdown_formats(temp_workspace: Path) -> None:
    formats = [
        "## Verification\n**Test command**: exit 0\n",
        "## Verification\n**Test command:** exit 0\n",
        "## Verification\n- **Test command**: `exit 0`\n",
        "## Verification\n- **Test command:** `exit 0`\n",
        "## Verification\nTest command: `exit 0`\n",
    ]
    for p in formats:
        (temp_workspace / ".orchestrator" / "plan.md").write_text(p)
        valid, errors = VerificationEngine.verify_testing(temp_workspace)
        assert valid is True, f"Failed for format: {p}"
        assert len(errors) == 0


def test_verify_plan_rejects_task_spec_bullet_without_verification_command(temp_workspace: Path) -> None:
    plan = (
        "## Tasks\n"
        "- [ ] **T1**: Code (Agent: coder, Target: a.py, blocked_by: [])\n"
        "- [ ] **T2**: Review (Agent: implementation-reviewer, Target: a.py, blocked_by: [T1])\n"
        "## Detailed Task Specifications\n"
        "### T1\n"
        "- **Test command for self-verification**: `pytest tests/`\n"
        "### T2\n"
        "Review spec\n"
        "## Verification\n"
    )
    (temp_workspace / ".orchestrator" / "plan.md").write_text(plan)
    valid, errors = VerificationEngine.verify_plan(temp_workspace, is_approved=True)
    assert valid is False
    assert any("missing required 'Test command: <cmd>'" in e for e in errors)
