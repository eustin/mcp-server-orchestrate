from typing import Any

from pydantic import BaseModel, Field


class InitResult(BaseModel):
    success: bool
    session_id: str | None = None
    phase: str | None = None
    sop_instructions: str | None = None
    error: str | None = None


class StatusResult(BaseModel):
    active_session: bool
    phase: str | None = None
    message: str


class ApproveResult(BaseModel):
    success: bool
    phase: str | None = None
    message: str | None = None
    error: str | None = None


class VerifyResult(BaseModel):
    success: bool
    phase: str
    previous_phase: str | None = None
    next_sop_instructions: str | None = None
    errors: list[str] = Field(default_factory=list)


class ArchiveResult(BaseModel):
    success: bool
    archived_session_id: str | None = None
    message: str | None = None
    error: str | None = None


class DAGBatch(BaseModel):
    batch_number: int
    tasks: list[dict[str, Any]]


class DAGResult(BaseModel):
    success: bool
    batches: list[DAGBatch] = Field(default_factory=list)
    total_tasks: int = 0
    error: str | None = None


class AgentSummary(BaseModel):
    name: str
    role: str
    description: str


class AgentListResult(BaseModel):
    success: bool
    agents: list[AgentSummary] = Field(default_factory=list)
    error: str | None = None
