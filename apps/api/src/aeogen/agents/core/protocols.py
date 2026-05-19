"""Agent SDK swap-able provider Protocols.

Structural typing: any object with the matching shape conforms.
No inheritance required. mypy --strict enforces conformance.
"""

from collections.abc import AsyncIterator
from typing import Protocol, runtime_checkable

from aeogen.agents.core.types import (
    AgentContext,
    LLMChunk,
    LLMResponse,
    MemoryHit,
    Message,
    Skill,
)


@runtime_checkable
class LLMProvider(Protocol):
    """Chat-style LLM provider. C.3 implements via OpenRouter+ChatOpenAI."""

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse: ...

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> AsyncIterator[LLMChunk]: ...


@runtime_checkable
class EmbeddingProvider(Protocol):
    """Text embedding provider. C.3 implements via Modal BGE-M3."""

    async def embed(self, texts: list[str]) -> list[list[float]]: ...


@runtime_checkable
class MemoryBackend(Protocol):
    """Agent memory backend. C.4 implements via Supabase agent_memory + pgvector."""

    async def get(
        self,
        agent_name: str,
        scope: str,
        key: str,
        *,
        workspace_id: str | None = None,
    ) -> dict[str, object] | None: ...

    async def set(
        self,
        agent_name: str,
        scope: str,
        key: str,
        value: dict[str, object],
        *,
        workspace_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None: ...

    async def search(
        self,
        agent_name: str,
        scope: str,
        query: str,
        k: int = 5,
        *,
        workspace_id: str | None = None,
    ) -> list[MemoryHit]: ...


@runtime_checkable
class SkillProvider(Protocol):
    """Skill registry. C.5 implements via Supabase agent_skills table (DB-only).

    Decision (2026-05-19): no filesystem fallback. All skills seeded into DB.
    """

    async def get_skill(
        self,
        agent_name: str,
        skill_key: str,
        *,
        version: int | None = None,
    ) -> Skill | None: ...

    async def list_skills(self, agent_name: str) -> list[Skill]: ...


@runtime_checkable
class AgentTool(Protocol):
    """Tool that an Agent can invoke. C.3+ implements concrete tools."""

    name: str
    schema: type[object]  # type[BaseModel] — narrow to BaseModel at impl site

    async def run(
        self,
        input: object,  # BaseModel instance matching self.schema
        ctx: AgentContext,
    ) -> object: ...
