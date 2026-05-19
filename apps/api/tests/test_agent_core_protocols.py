"""C.1 Protocol conformance + ABC invariant tests.

These tests run BOTH:
- pytest at runtime (ABC checks via __init_subclass__)
- mypy --strict at type-check time (Protocol structural conformance)
"""

from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
from pydantic import ValidationError

from aeogen.agents.core import (
    Agent,
    AgentContext,
    LLMChunk,
    LLMProvider,
    LLMResponse,
    Message,
)

# ---------- Protocol conformance (compile-time via mypy --strict) ----------


class _FakeLLM:
    async def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        return LLMResponse(content="ok", model="test", input_tokens=1, output_tokens=1)

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> AsyncIterator[LLMChunk]:
        async def _gen() -> AsyncIterator[LLMChunk]:
            yield LLMChunk(delta="ok")

        return _gen()


def test_llm_provider_protocol_shape() -> None:
    """mypy enforces this at type-check time; pytest just confirms import OK."""
    instance: LLMProvider = _FakeLLM()  # type-checks under --strict
    assert instance is not None  # runtime no-op


# ---------- ABC invariant enforcement (runtime via __init_subclass__) ----------


def test_agent_requires_classvars() -> None:
    """Agent subclass without ClassVars raises TypeError at class definition."""
    with pytest.raises(TypeError, match="missing ClassVars"):

        class _BrokenAgent(Agent):
            async def run(self, input, ctx):  # type: ignore[no-untyped-def]
                return input


def test_agent_invalid_kind_rejected() -> None:
    with pytest.raises(TypeError, match="kind must be"):

        class _BadKind(Agent):
            name = "x"
            technique_id = 1
            kind = "wrong"  # type: ignore[assignment]
            default_llm = "anthropic/claude-sonnet-4-6"

            async def run(self, input, ctx):  # type: ignore[no-untyped-def]
                return input


def test_agent_technique_id_out_of_range_rejected() -> None:
    with pytest.raises(TypeError, match="technique_id must be 1-12"):

        class _BadTechId(Agent):
            name = "x"
            technique_id = 42
            kind = "analyzer"
            default_llm = "anthropic/claude-sonnet-4-6"

            async def run(self, input, ctx):  # type: ignore[no-untyped-def]
                return input


def test_agent_valid_subclass_succeeds() -> None:
    class _Good(Agent):
        name = "good"
        technique_id = 5
        kind = "analyzer"
        default_llm = "anthropic/claude-sonnet-4-6"

        async def run(self, input, ctx):  # type: ignore[no-untyped-def]
            return input

    assert _Good.name == "good"
    assert _Good.technique_id == 5


def test_agent_context_immutable() -> None:
    ctx = AgentContext(execution_id=uuid4(), workspace_id=uuid4(), db_session=None)
    with pytest.raises(ValidationError):  # pydantic frozen=True
        ctx.execution_id = uuid4()  # type: ignore[misc]
