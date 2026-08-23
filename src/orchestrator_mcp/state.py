import hashlib
import hmac
import json
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, ClassVar

from .config import get_orchestrator_dir

SECRET_KEY = b"opencode-orchestrator-anti-tamper-key"


class StateTamperError(Exception):
    """Raised when internal session state tampering is detected."""


class StateManager:
    PHASES: ClassVar[list[str]] = ["DESIGN", "PLAN", "EXECUTE", "VERIFY", "COMPLETE"]

    def __init__(self, workspace_root: Path | None = None) -> None:
        self.orch_dir = get_orchestrator_dir(workspace_root)
        self.state_file = self.orch_dir / "session.json"
        self.plan_file = self.orch_dir / "plan.md"
        self.design_file = self.orch_dir / "design.md"

    def calculate_hmac(self, data_dict: dict[str, Any]) -> str:
        """Calculate HMAC-SHA256 signature for state dictionary, excluding existing _hmac."""
        clean = {k: v for k, v in data_dict.items() if k != "_hmac"}
        serialized = json.dumps(clean, sort_keys=True)
        return hmac.new(SECRET_KEY, serialized.encode("utf-8"), hashlib.sha256).hexdigest()

    def generate_session_id(self, task_description: str) -> str:
        """Generate a deterministic slugified session ID."""
        slug = re.sub(r"[^a-z0-9]+", "-", task_description.lower()).strip("-")[:30]
        return f"{datetime.now(UTC).strftime('%Y-%m-%d')}-{slug}"

    def init_session(self, task_description: str, session_id: str | None = None) -> dict[str, Any]:
        """Initialize a new orchestration session with HMAC anti-tamper signature."""
        sid = session_id or self.generate_session_id(task_description)
        state: dict[str, Any] = {
            "session_id": sid,
            "current_phase": "DESIGN",
            "current_phase_approved": False,
            "task_description": task_description,
            "retry_counts": {},
            "history": [
                {
                    "timestamp": datetime.now(UTC).isoformat(),
                    "event": "session_created",
                    "phase": "DESIGN",
                }
            ],
        }
        state["_hmac"] = self.calculate_hmac(state)
        self.state_file.write_text(json.dumps(state, indent=2))
        return state

    def load_state(self) -> dict[str, Any] | None:
        """Load session state and verify HMAC signature. Raises StateTamperError if tampered."""
        if not self.state_file.exists():
            return None
        try:
            data: dict[str, Any] = json.loads(self.state_file.read_text())
            if data.get("_hmac") != self.calculate_hmac(data):
                raise StateTamperError(
                    "TAMPERING DETECTED: Internal state file session.json was manually modified."
                )
            return data
        except json.JSONDecodeError as err:
            raise StateTamperError("Corrupted state file session.json.") from err

    def save_state(self, state: dict[str, Any]) -> None:
        """Sign and save state dictionary to session.json."""
        state["_hmac"] = self.calculate_hmac(state)
        self.state_file.write_text(json.dumps(state, indent=2))

    def approve_current_phase(self) -> dict[str, Any]:
        """Mark the current phase as human-approved and record the event."""
        state = self.load_state()
        if not state:
            raise ValueError("No active session state found.")
        state["current_phase_approved"] = True
        state["history"].append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "event": "phase_approved",
                "phase": state.get("current_phase"),
            }
        )
        self.save_state(state)
        return state

    def update_phase(self, new_phase: str) -> dict[str, Any]:
        """Transition session to a new phase and reset approval."""
        state = self.load_state()
        if not state:
            raise ValueError("No active session state found.")
        if new_phase not in self.PHASES:
            raise ValueError(f"Invalid phase: {new_phase}")
        state["current_phase"] = new_phase
        state["current_phase_approved"] = False
        state["history"].append(
            {
                "timestamp": datetime.now(UTC).isoformat(),
                "event": "phase_transition",
                "phase": new_phase,
            }
        )
        self.save_state(state)
        return state

    def parse_plan_tasks(self) -> list[dict[str, Any]]:
        """Parse tasks from plan.md with robust non-greedy metadata extraction."""
        if not self.plan_file.exists():
            return []
        content = self.plan_file.read_text()
        tasks: list[dict[str, Any]] = []
        for line in content.splitlines():
            line_str = line.strip()
            if not line_str.startswith("- ["):
                continue

            checked = line_str.startswith(("- [x]", "- [X]"))

            # Extract Task ID
            tid = None
            m_bold = re.search(r"^-\s*\[[ xX]\]\s*\*\*([^*]+)\*\*", line_str)
            if m_bold:
                tid = m_bold.group(1).strip().rstrip(":")
            else:
                m_raw = re.search(r"^-\s*\[[ xX]\]\s*([^:(]+)", line_str)
                if m_raw:
                    tid = m_raw.group(1).strip()

            # Extract Target
            target = None
            m_target = re.search(r"\(Target:\s*([^)]+)\)", line_str)
            if m_target:
                target = m_target.group(1).strip()

            # Extract Agent
            agent = None
            m_agent = re.search(r"\(Agent:\s*([^)]+)\)", line_str)
            if m_agent:
                agent = m_agent.group(1).strip()

            # Extract blocked_by list
            blocked_by: list[str] = []
            m_blocked = re.search(r"\(blocked_by:\s*\[(.*?)\]\)", line_str)
            if m_blocked:
                raw_deps = m_blocked.group(1).strip()
                if raw_deps:
                    blocked_by = [d.strip().strip("'\"") for d in raw_deps.split(",") if d.strip()]

            # Extract description
            desc = line_str
            m_desc = re.search(
                r"^-\s*\[[ xX]\]\s*(.*?)(?=\s*\((?:Agent|Target|blocked_by):|$)", line_str
            )
            if m_desc:
                desc = m_desc.group(1).strip()

            tasks.append(
                {
                    "id": tid,
                    "checked": checked,
                    "description": desc,
                    "agent": agent,
                    "target": target,
                    "blocked_by": blocked_by,
                }
            )
        return tasks
