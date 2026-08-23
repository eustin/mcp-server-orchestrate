import re
import subprocess
from pathlib import Path

from .config import get_orchestrator_dir, resolve_workspace_root

TEST_COMMAND_REGEX = re.compile(
    r"^\s*(?:-\s*)?(?:\*\*)?Test command:?(?:\*\*)?:?\s*(.+)$",
    re.MULTILINE | re.IGNORECASE,
)


class VerificationEngine:
    @staticmethod
    def verify_design(
        workspace_root: Path | None = None, is_approved: bool = False
    ) -> tuple[bool, list[str]]:
        root = workspace_root or resolve_workspace_root()
        design_file = get_orchestrator_dir(root) / "design.md"
        if not design_file.exists():
            return False, ["Missing required deliverable: .orchestrator/design.md"]

        errors = []
        if not is_approved:
            errors.append(
                "GATE BLOCKED: Design deliverable .orchestrator/design.md is ready, but human approval is required."
            )

        content = design_file.read_text()
        for heading in ["## Requirements", "## Architecture", "## Self-Confidence Audit"]:
            if heading not in content:
                errors.append(f"Missing required Design Document section: '{heading}'")

        return len(errors) == 0, errors

    @staticmethod
    def verify_plan(
        workspace_root: Path | None = None, is_approved: bool = False
    ) -> tuple[bool, list[str]]:
        root = workspace_root or resolve_workspace_root()
        plan_file = get_orchestrator_dir(root) / "plan.md"
        if not plan_file.exists():
            return False, ["Missing required deliverable: .orchestrator/plan.md"]

        errors = []
        if not is_approved:
            errors.append(
                "GATE BLOCKED: Plan deliverable .orchestrator/plan.md is ready, but human approval is required."
            )

        content = plan_file.read_text()
        if "## Tasks" not in content or "## Verification" not in content:
            errors.append("Plan Document must contain '## Tasks' and '## Verification' sections.")
        if "## Detailed Task Specifications" not in content:
            errors.append("Plan Document must contain '## Detailed Task Specifications' section.")

        checkbox_lines = [
            line.strip() for line in content.splitlines() if line.strip().startswith("- [")
        ]
        if not checkbox_lines:
            errors.append("Plan must contain at least one task item (checkbox '- [ ]').")

        for line in checkbox_lines:
            if "Agent:" not in line:
                errors.append(f"Task item missing required '(Agent: <role>)' tag: '{line}'")
            if "Target:" not in line:
                errors.append(f"Task item missing required '(Target: path/to/file)' tag: '{line}'")
            if "blocked_by:" not in line:
                errors.append(f"Task item missing required '(blocked_by: [<deps>])' tag: '{line}'")

            tid = None
            m_bold = re.search(r"-\s*\[[ xX]\]\s*\*\*([^*]+)\*\*", line)
            if m_bold:
                tid = m_bold.group(1).strip().rstrip(":")
            else:
                m_raw = re.search(r"-\s*\[[ xX]\]\s*([^:(]+)", line)
                if m_raw:
                    tid = m_raw.group(1).strip()

            if tid and not re.search(rf"###\s*{re.escape(tid)}\b", content, re.IGNORECASE):
                errors.append(
                    f"Task '{tid}' missing detailed specification heading '### {tid}' under '## Detailed Task Specifications'."
                )

        last_checkbox = checkbox_lines[-1] if checkbox_lines else ""
        if "Agent: implementation-reviewer" not in last_checkbox:
            errors.append(
                "Plan MUST end with a final task assigned to 'Agent: implementation-reviewer', blocked by all prior tasks."
            )
        if "blocked_by: []" in last_checkbox:
            errors.append(
                "Final task MUST be blocked by all preceding tasks. 'blocked_by: []' is invalid."
            )

        match = TEST_COMMAND_REGEX.search(content)
        if not match:
            errors.append(
                "Plan Document missing required 'Test command: <cmd>' under '## Verification'."
            )
        else:
            test_cmd = match.group(1).strip().strip("`").strip()
            if not test_cmd or test_cmd.lower() == "none":
                errors.append(
                    "Plan Document must specify a valid executable 'Test command: <cmd>' under '## Verification' ('None' or empty is forbidden)."
                )

        return len(errors) == 0, errors

    @staticmethod
    def verify_execution(workspace_root: Path | None = None) -> tuple[bool, list[str]]:
        root = workspace_root or resolve_workspace_root()
        plan_file = get_orchestrator_dir(root) / "plan.md"
        if not plan_file.exists():
            return False, ["Missing plan file for execution verification."]

        content = plan_file.read_text()
        errors = []

        unchecked = re.findall(r"- \[\s\]\s*(.*)", content)
        if unchecked:
            for task_desc in unchecked:
                errors.append(
                    f"[VERIFICATION FAILED: UNFINISHED TASK] Task '{task_desc.strip()}' is incomplete."
                )

        for line in content.splitlines():
            line_str = line.strip()
            if line_str.startswith(("- [x]", "- [X]")):
                m_target = re.search(r"\(Target:\s*([^)]+?)\)", line_str)
                if m_target:
                    target_clean = m_target.group(1).strip()
                    file_path = root / target_clean
                    if not file_path.exists():
                        errors.append(f"Target file '{target_clean}' does not exist.")
                    elif file_path.stat().st_size == 0:
                        errors.append(f"Target file '{target_clean}' is 0 bytes.")

        return len(errors) == 0, errors

    @staticmethod
    def verify_testing(workspace_root: Path | None = None) -> tuple[bool, list[str]]:
        root = workspace_root or resolve_workspace_root()
        plan_file = get_orchestrator_dir(root) / "plan.md"
        if not plan_file.exists():
            return False, ["Missing plan file for verification."]

        content = plan_file.read_text()
        match = TEST_COMMAND_REGEX.search(content)
        if not match:
            return False, [
                "Missing required 'Test command: <cmd>' under '## Verification' in plan.md."
            ]

        test_cmd = match.group(1).strip().strip("`").strip()
        if not test_cmd or test_cmd.lower() == "none":
            return False, [
                "Plan Document specifies an invalid or empty test command ('None' is forbidden)."
            ]

        try:
            res = subprocess.run(
                test_cmd,
                shell=True,
                cwd=root,
                capture_output=True,
                text=True,
                timeout=120,
                check=False,
            )
            if res.returncode != 0:
                stdout_tail = "\n".join(res.stdout.splitlines()[-50:])
                stderr_tail = "\n".join(res.stderr.splitlines()[-50:])
                return False, [
                    f"Automated test runner failed (Exit Code {res.returncode}):\n{stdout_tail}\n{stderr_tail}"
                ]
            return True, []
        except Exception as e:  # noqa: BLE001
            return False, [f"Failed to execute test command '{test_cmd}': {e!s}"]
