from .complete import COMPLETE_PHASE_PROMPT
from .design import DESIGN_PHASE_PROMPT
from .execute import EXECUTE_PHASE_PROMPT
from .plan import PLAN_PHASE_PROMPT
from .verify import VERIFY_PHASE_PROMPT

PROMPT_MAP = {
    "DESIGN": DESIGN_PHASE_PROMPT,
    "PLAN": PLAN_PHASE_PROMPT,
    "EXECUTE": EXECUTE_PHASE_PROMPT,
    "VERIFY": VERIFY_PHASE_PROMPT,
    "COMPLETE": COMPLETE_PHASE_PROMPT,
}


def get_phase_prompt(phase: str) -> str:
    """Return the SOP prompt for the given phase."""
    return PROMPT_MAP.get(phase.upper(), "")


__all__ = [
    "COMPLETE_PHASE_PROMPT",
    "DESIGN_PHASE_PROMPT",
    "EXECUTE_PHASE_PROMPT",
    "PLAN_PHASE_PROMPT",
    "VERIFY_PHASE_PROMPT",
    "get_phase_prompt",
]
