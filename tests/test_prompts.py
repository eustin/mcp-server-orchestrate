"""Contract tests asserting phase prompts satisfy all orchestrator standards and gates."""

from orchestrator_mcp.prompts.complete import COMPLETE_PHASE_PROMPT
from orchestrator_mcp.prompts.design import DESIGN_PHASE_PROMPT
from orchestrator_mcp.prompts.execute import EXECUTE_PHASE_PROMPT
from orchestrator_mcp.prompts.plan import PLAN_PHASE_PROMPT
from orchestrator_mcp.prompts.verify import VERIFY_PHASE_PROMPT


class TestSelfIdentificationGate:
    """Ensure all phase prompts have self-identification gate to shield subagents."""

    def test_all_prompts_have_self_id_gate(self) -> None:
        for prompt in [
            DESIGN_PHASE_PROMPT,
            PLAN_PHASE_PROMPT,
            EXECUTE_PHASE_PROMPT,
            VERIFY_PHASE_PROMPT,
        ]:
            assert "SELF-IDENTIFICATION GATE" in prompt
            assert "Worker Scope Boundary" in prompt
            assert "STOP reading this block NOW" in prompt or "IGNORE this block" in prompt


class TestMaestroAbsenceRegression:
    """Ensure legacy 'Maestro' references are completely absent from all phase prompts."""

    def test_no_maestro_in_any_prompt(self) -> None:
        for prompt in [
            DESIGN_PHASE_PROMPT,
            PLAN_PHASE_PROMPT,
            EXECUTE_PHASE_PROMPT,
            VERIFY_PHASE_PROMPT,
            COMPLETE_PHASE_PROMPT,
        ]:
            assert "maestro" not in prompt.lower()


class TestDesignPhasePrompt:
    def test_design_prompt_contains_mandatory_sections_and_gate(self) -> None:
        assert "## Goal" in DESIGN_PHASE_PROMPT
        assert "## Requirements" in DESIGN_PHASE_PROMPT
        assert "## Architecture" in DESIGN_PHASE_PROMPT
        assert "## Self-Confidence Audit" in DESIGN_PHASE_PROMPT
        assert "orchestrate_approve" in DESIGN_PHASE_PROMPT
        assert "orchestrate_verify" in DESIGN_PHASE_PROMPT
        assert "95%" in DESIGN_PHASE_PROMPT
        assert "Active Roles" in DESIGN_PHASE_PROMPT
        for role in ["Product Manager", "Architect", "UX Designer", "Cavecrew Investigator"]:
            assert role in DESIGN_PHASE_PROMPT


class TestPlanPhasePrompt:
    def test_plan_prompt_contains_spec_and_reviewer_rules(self) -> None:
        assert "## Tasks" in PLAN_PHASE_PROMPT
        assert "## Detailed Task Specifications" in PLAN_PHASE_PROMPT
        assert "implementation-reviewer" in PLAN_PHASE_PROMPT
        assert "orchestrate_approve" in PLAN_PHASE_PROMPT
        assert "orchestrate_verify" in PLAN_PHASE_PROMPT
        assert "Test command:" in PLAN_PHASE_PROMPT
        assert "Copy-Paste Mandate" in PLAN_PHASE_PROMPT
        assert "Micro-Task Sizing Rule" in PLAN_PHASE_PROMPT


class TestExecutePhasePrompt:
    def test_execute_prompt_contains_supervisory_mandate(self) -> None:
        assert "supervisory" in EXECUTE_PHASE_PROMPT.lower()
        assert "NEVER write or edit source code directly" in EXECUTE_PHASE_PROMPT

    def test_execute_prompt_contains_role_mappings(self) -> None:
        for role in [
            "coder",
            "debugger",
            "performance-engineer",
            "tester",
            "implementation-reviewer",
        ]:
            assert role in EXECUTE_PHASE_PROMPT

    def test_execute_prompt_contains_delegation_and_retry_rules(self) -> None:
        assert "orchestrate_get_dag_batches" in EXECUTE_PHASE_PROMPT
        assert "3 retries" in EXECUTE_PHASE_PROMPT
        assert "Verification Specialist Protocol" in EXECUTE_PHASE_PROMPT
        assert "Fix Delegation Loop" in EXECUTE_PHASE_PROMPT
        assert "Re-Verification Loop" in EXECUTE_PHASE_PROMPT

    def test_execute_prompt_blocks_all_code_edit_tools(self) -> None:
        blocked_tools = [
            "edit",
            "write",
            "serena_replace_content",
            "serena_create_text_file",
            "serena_replace_symbol_body",
            "serena_insert_after_symbol",
            "serena_insert_before_symbol",
            "serena_replace_in_files",
            "serena_rename_symbol",
            "serena_safe_delete_symbol",
        ]
        for tool in blocked_tools:
            assert tool in EXECUTE_PHASE_PROMPT, f"Missing blocked tool in EXECUTE prompt: {tool}"


class TestVerifyAndCompletePrompts:
    def test_verify_prompt_contains_audit_workflow(self) -> None:
        assert "orchestrate_verify" in VERIFY_PHASE_PROMPT
        assert "orchestrate_archive" in VERIFY_PHASE_PROMPT

    def test_complete_prompt_contains_satisfaction_check(self) -> None:
        assert "Are you satisfied with the results?" in COMPLETE_PHASE_PROMPT
        assert "Never auto-archive without user confirmation" in COMPLETE_PHASE_PROMPT
        assert "orchestrate_archive" in COMPLETE_PHASE_PROMPT
