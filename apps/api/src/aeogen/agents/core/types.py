"""Agent SDK data classes (Pydantic v2)."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class Message(BaseModel):
    """LLM chat message."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "user", "assistant", "tool"]
    content: str = Field(min_length=0)
    name: str | None = None  # tool name when role='tool'


class LLMResponse(BaseModel):
    """LLM chat response."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: str
    model: str  # e.g., "anthropic/claude-sonnet-4-6"
    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    cost_usd: float | None = Field(default=None, ge=0)  # OpenRouter response header


class LLMChunk(BaseModel):
    """Streaming chunk."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    delta: str
    finish_reason: str | None = None


class MemoryHit(BaseModel):
    """Retrieval result from MemoryBackend.search()."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    key: str
    value: dict[str, Any]
    score: float  # cosine similarity in [-1, 1]; impl normalizes


class Skill(BaseModel):
    """Skill record returned by SkillProvider."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    agent_name: str
    skill_key: str
    content: str
    version: int = Field(ge=1)
    source: Literal["builtin", "promoted", "manual"]


class AgentContext(BaseModel):
    """Per-execution agent context (minimal 3-field decision 2026-05-19).

    Carried through Agent.run() — provides identity + tenant + DB access.
    Telemetry (trace_id, callbacks) live in LangGraph config, NOT here.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, arbitrary_types_allowed=True)

    execution_id: UUID  # FK to agent_executions.id (B.2)
    workspace_id: UUID  # FK to workspaces.id (B.1)
    db_session: Any  # AsyncSession from sqlalchemy.ext.asyncio — opaque to core SDK
