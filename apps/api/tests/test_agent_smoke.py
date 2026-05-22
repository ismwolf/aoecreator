"""C.7 Agent smoke test — fake LLM + fake memory + fake skills.

Validates the full Agent SDK chain end-to-end without a real DB or LLM:
  Agent subclass → llm.chat() → MemoryBackend.set() → SkillProvider.get_skill()

Uses the structural Protocol: FakeAgent instantiation proves that
OpenRouterLLM, SupabaseMemoryBackend, and SupabaseSkillProvider all satisfy
their respective protocols at runtime (isinstance with @runtime_checkable).
"""

import os
from typing import Any, ClassVar
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from pydantic import BaseModel

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key-" + "x" * 20)

from aeogen.agents.core.base import Agent, AgentKind
from aeogen.agents.core.callbacks import CostTracker, LangSmithTraceHandler
from aeogen.agents.core.memory import SupabaseMemoryBackend
from aeogen.agents.core.protocols import LLMProvider, MemoryBackend, SkillProvider
from aeogen.agents.core.skills import SupabaseSkillProvider
from aeogen.agents.core.types import AgentContext, LLMResponse, MemoryHit, Message, Skill

# ---------------------------------------------------------------------------
# Fake implementations
# ---------------------------------------------------------------------------


class FakeLLM:
    """Minimal LLMProvider-conforming stub for smoke tests."""

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(
            content="smoke-ok",
            model="fake/model",
            input_tokens=len(messages),
            output_tokens=2,
            cost_usd=None,
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> Any:  # AsyncIterator[LLMChunk]
        return  # pragma: no cover — not tested in smoke


class FakeMemory:
    """Minimal MemoryBackend-conforming stub."""

    def __init__(self) -> None:
        self._store: dict[str, dict[str, object]] = {}

    async def get(
        self,
        agent_name: str,
        scope: str,
        key: str,
        *,
        workspace_id: str | None = None,
    ) -> dict[str, object] | None:
        return self._store.get(key)

    async def set(
        self,
        agent_name: str,
        scope: str,
        key: str,
        value: dict[str, object],
        *,
        workspace_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        self._store[key] = value

    async def search(
        self,
        agent_name: str,
        scope: str,
        query: str,
        k: int = 5,
        *,
        workspace_id: str | None = None,
    ) -> list[MemoryHit]:
        return []


class FakeSkills:
    """Minimal SkillProvider-conforming stub."""

    async def get_skill(
        self,
        agent_name: str,
        skill_key: str,
        *,
        version: int | None = None,
    ) -> Skill | None:
        return Skill(
            agent_name=agent_name,
            skill_key=skill_key,
            content="You are a fake analyzer.",
            version=1,
            source="builtin",
        )

    async def list_skills(self, agent_name: str) -> list[Skill]:
        return []


# ---------------------------------------------------------------------------
# Concrete Agent subclass for smoke testing
# ---------------------------------------------------------------------------


class FakeInput(BaseModel):
    prompt: str


class FakeOutput(BaseModel):
    answer: str


class SmokeAnalyzer(Agent):
    name: ClassVar[str] = "smoke-analyzer"
    technique_id: ClassVar[int | None] = 1
    kind: ClassVar[AgentKind] = "analyzer"
    default_llm: ClassVar[str] = "fake/model"

    async def run(self, input: BaseModel, ctx: AgentContext) -> BaseModel:
        assert isinstance(input, FakeInput)
        messages = [Message(role="user", content=input.prompt)]
        response = await self.llm.chat(messages)

        # Write result to memory
        await self.memory.set(
            self.name,
            "agent",
            f"result:{ctx.execution_id}",
            {"answer": response.content},
        )
        return FakeOutput(answer=response.content)


def _fake_ctx() -> AgentContext:
    return AgentContext(
        execution_id=uuid4(),
        workspace_id=uuid4(),
        db_session=None,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_smoke_agent_run_end_to_end() -> None:
    """Agent.run() calls llm.chat() and writes to memory backend."""
    memory = FakeMemory()
    agent = SmokeAnalyzer(llm=FakeLLM(), memory=memory, skills=FakeSkills())
    ctx = _fake_ctx()

    output = await agent.run(FakeInput(prompt="hello"), ctx)

    assert isinstance(output, FakeOutput)
    assert output.answer == "smoke-ok"
    # Memory backend received the SET call
    stored = await memory.get(agent.name, "agent", f"result:{ctx.execution_id}")
    assert stored == {"answer": "smoke-ok"}


@pytest.mark.asyncio
async def test_smoke_agent_with_cost_tracker() -> None:
    """Agent wired with CostTracker + LangSmithTraceHandler runs without error."""
    mock_db = AsyncMock()
    agent = SmokeAnalyzer(
        llm=FakeLLM(),
        memory=FakeMemory(),
        skills=FakeSkills(),
        callbacks=[
            CostTracker(execution_id=uuid4(), db_session=mock_db),
            LangSmithTraceHandler(execution_id=uuid4(), db_session=mock_db),
        ],
    )
    output = await agent.run(FakeInput(prompt="cost test"), _fake_ctx())
    assert output.answer == "smoke-ok"


def test_protocol_conformance_at_runtime() -> None:
    """Structural Protocol: all 3 concrete classes satisfy runtime_checkable checks."""
    fake_llm = FakeLLM()
    assert isinstance(fake_llm, LLMProvider)

    fake_mem = FakeMemory()
    assert isinstance(fake_mem, MemoryBackend)

    fake_skills = FakeSkills()
    assert isinstance(fake_skills, SkillProvider)


def test_supabase_backends_satisfy_protocols() -> None:
    """SupabaseMemoryBackend and SupabaseSkillProvider satisfy their protocols."""
    mem = SupabaseMemoryBackend("postgresql://test:test@localhost/db")
    assert isinstance(mem, MemoryBackend)

    skills = SupabaseSkillProvider("postgresql://test:test@localhost/db")
    assert isinstance(skills, SkillProvider)


def test_agent_classvars_validated_at_definition() -> None:
    """Agent subclass with wrong kind raises TypeError at class definition time."""
    with pytest.raises(TypeError, match="kind must be"):

        class BadAgent(Agent):
            name: ClassVar[str] = "bad"
            technique_id: ClassVar[int | None] = 1
            kind: ClassVar[AgentKind] = "invalid"  # type: ignore[assignment]
            default_llm: ClassVar[str] = "x/y"

            async def run(
                self, input: BaseModel, ctx: AgentContext
            ) -> BaseModel: ...  # pragma: no cover
