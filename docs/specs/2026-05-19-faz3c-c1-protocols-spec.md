# Faz 3 C.1 — Agent SDK SOLID Protocols + Types + ABC Spec

Date: 2026-05-19
Phase: Faz 3 C (Agent Core SDK) → sub-cycle C.1 (foundation contracts)
Predecessors: Faz 2 B ✅ (13 tables including `agent_memory`, `agent_skills`, `agent_executions` ready as downstream sinks)
Successors: C.2 (LangGraph StateGraph + PostgresSaver), C.3 (OpenRouter LLM adapter), C.4 (memory backend impl), C.5 (skill registry impl), C.6 (telemetry callbacks), C.7 (tests with real impls)

## Problem

Faz 3 C kicks off the Agent Core SDK — every v1 GEO agent (5 analyzers + 5 generators + orchestrator) will inherit from this foundation. The SDK has 6 swap-able provider concerns + 1 base agent class. Without the abstraction layer locked first, C.2-C.6 implementations diverge in signatures and we get refactor churn.

**C.1 alt-cycle** kurar: 4 Python module (protocols, types, base, callbacks) + minimal Agent ABC iskeleti + conformance test. **No concrete implementation** — every method is `raise NotImplementedError`. C.3-C.6 doldurur.

This is the **interface-first SOLID foundation** master plan §4.C.1'de tarif edilen.

## Goals

- 4 Python module in `apps/api/src/aeogen/agents/core/`:
  - `protocols.py` — 5 `typing.Protocol` (LLMProvider, EmbeddingProvider, MemoryBackend, SkillProvider, AgentTool)
  - `types.py` — Pydantic v2 BaseModels (Message, LLMResponse, LLMChunk, MemoryHit, Skill, AgentContext)
  - `base.py` — `Agent` ABC with `ClassVar` invariants (`name`, `technique_id`, `kind`, `default_llm`)
  - `callbacks.py` — `CostTracker` AsyncCallbackHandler iskeleti (raise NotImplementedError, C.6 doldurur)
- All 5 lock-in decisions from langchain-master consultation (2026-05-19) implemented:
  1. `typing.Protocol` for providers; `abc.ABC` for Agent; `pydantic.BaseModel` for data
  2. `langgraph` schema migration → **deferred to C.2** (C.1 doesn't touch DB)
  3. OpenRouter via `langchain_openai.ChatOpenAI(base_url=...)` — **C.3 implements** (C.1 only declares Protocol)
  4. Cost tracking via `AsyncCallbackHandler` — **C.6 implements** (C.1 only declares class + `on_llm_end` signature)
  5. Agent ABC owns callback wiring — `Agent.__init__` accepts `callbacks: list[AsyncCallbackHandler]` and stores on self
- All 8 brainstorm decisions (locked 2026-05-19):
  - Scope: protocols + types + ABC iskeleti (no concrete impl, no test fakes)
  - langgraph schema: C.2 birlikte
  - AgentContext: minimal 3-field (execution_id, workspace_id, db_session)
  - Tests: mypy strict + Protocol conformance only
  - Module path: `apps/api/src/aeogen/agents/core/`
  - `OPENROUTER_API_KEY` Settings: C.3'te eklenecek (C.1 değil)
  - SkillProvider source: DB-only (B.3 `agent_skills` table)
  - LangChain pin: `langchain-core>=0.3,<0.4`, `langchain-openai>=0.3,<0.4`, `langgraph>=0.6,<0.7`, `langsmith>=0.5,<0.6`, `pydantic>=2.9,<3`
- Inherit apps/api conventions:
  - mypy strict + ruff lint/format
  - `py.typed` already present
  - pytest-asyncio
  - pydantic v2
- Tests: `tests/test_agent_core_protocols.py` — Protocol conformance assertions (compile-time, mypy enforces)

## Non-Goals (deferred)

- **Concrete `LLMProvider` implementation** (OpenRouter via ChatOpenAI) → **C.3**
- **PostgresSaver checkpoint integration** → **C.2**
- **`langgraph` schema migration** → **C.2** (own mini-migration in C.2 PR)
- **Concrete `MemoryBackend`** (Supabase `agent_memory` table + pgvector retrieval) → **C.4**
- **Concrete `SkillProvider`** (B.3 `agent_skills` table query) → **C.5**
- **`CostTracker` body** (OpenRouter cost extraction + agent_executions UPDATE) → **C.6**
- **LangSmith trace handler** → **C.6**
- **End-to-end smoke test** (real LLM call) → **C.7** (after C.3 + C.4 + C.5 + C.6)
- **OpenRouter API key in Settings** → **C.3**
- **Per-agent model config (yaml/db)** → **C.3 or Faz 5 E**
- **Streaming support beyond Protocol signature** → **C.3** (impl)
- **Tool calling integration** (LangChain `bind_tools`) → **C.3 / Faz 5 E**
- **Structured output binding** (Pydantic + `with_structured_output`) → **C.3 / Faz 5 E**

## Approach

### 1. File layout (under `apps/api/src/aeogen/`)

```
agents/
  __init__.py          # re-exports Agent for short import: `from aeogen.agents import Agent`
  core/
    __init__.py        # re-exports key classes: Agent, LLMProvider, MemoryBackend, ...
    protocols.py       # 5 typing.Protocol
    types.py           # Pydantic BaseModels (data classes)
    base.py            # Agent ABC
    callbacks.py       # AsyncCallbackHandler iskeleti (CostTracker, LangSmithTraceHandler)
```

### 2. `protocols.py` — 5 typing.Protocol

```python
"""Agent SDK swap-able provider Protocols.

Structural typing: any object with the matching shape conforms.
No inheritance required. mypy --strict enforces conformance.
"""
from typing import Protocol, AsyncIterator, runtime_checkable

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
```

### 3. `types.py` — Pydantic BaseModels

```python
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
    score: float  # cosine similarity ∈ [-1, 1]; impl normalizes


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
```

### 4. `base.py` — `Agent` ABC

```python
"""Agent base class.

Owns invariants (ClassVar fields), callback wiring, and the abstract `run()`.
Concrete agents (Faz 5 E) subclass this.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import ClassVar, Literal

from langchain_core.callbacks import AsyncCallbackHandler
from pydantic import BaseModel

from aeogen.agents.core.protocols import LLMProvider, MemoryBackend, SkillProvider
from aeogen.agents.core.types import AgentContext


AgentKind = Literal["analyzer", "generator", "orchestrator"]


class Agent(ABC):
    """Base for every GEO agent.

    Subclasses MUST declare the four ClassVars below.
    Enforcement runs in `__init_subclass__` — invalid subclasses raise at class
    definition time (not first instantiation), so misconfigurations fail fast.
    """

    name: ClassVar[str]
    technique_id: ClassVar[int | None]  # 1-12 (master plan §1), None for orchestrators
    kind: ClassVar[AgentKind]
    default_llm: ClassVar[str]  # OpenRouter model id, e.g., "anthropic/claude-sonnet-4-6"

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        if getattr(cls, "__abstractmethods__", None):
            return  # abstract subclasses (rare) skip the check
        required = ("name", "technique_id", "kind", "default_llm")
        missing = [f for f in required if f not in cls.__dict__]
        if missing:
            raise TypeError(
                f"Agent subclass {cls.__name__} missing ClassVars: {missing}"
            )
        if cls.kind not in ("analyzer", "generator", "orchestrator"):
            raise TypeError(f"{cls.__name__}.kind must be analyzer/generator/orchestrator")
        if cls.technique_id is not None and not (1 <= cls.technique_id <= 12):
            raise TypeError(f"{cls.__name__}.technique_id must be 1-12 or None")

    def __init__(
        self,
        llm: LLMProvider,
        memory: MemoryBackend,
        skills: SkillProvider,
        *,
        callbacks: list[AsyncCallbackHandler] | None = None,
    ) -> None:
        self.llm = llm
        self.memory = memory
        self.skills = skills
        self.callbacks: list[AsyncCallbackHandler] = callbacks or []

    @abstractmethod
    async def run(self, input: BaseModel, ctx: AgentContext) -> BaseModel:
        """Execute the agent's workflow.

        Concrete agents (Faz 5 E) typically build a LangGraph StateGraph here
        and invoke it with `config={"callbacks": self.callbacks, "configurable":
        {"thread_id": str(ctx.execution_id)}}`.
        """
        ...
```

### 5. `callbacks.py` — AsyncCallbackHandler iskeleti

```python
"""Agent telemetry callbacks.

C.6 fills in the bodies. C.1 only defines the class shape so Agent constructor
can accept `callbacks: list[AsyncCallbackHandler]`.
"""
from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult


class CostTracker(AsyncCallbackHandler):
    """Per-execution LLM cost tracker.

    Writes to agent_executions.llm_cost (B.2 column). C.6 implements.
    """

    def __init__(self, execution_id: UUID, db_session: Any) -> None:
        self.execution_id = execution_id
        self.db_session = db_session

    async def on_llm_end(self, response: LLMResult, **kwargs: object) -> None:
        raise NotImplementedError("Implemented in Faz 3 C.6 (telemetry)")


class LangSmithTraceHandler(AsyncCallbackHandler):
    """Captures LangSmith trace_id into agent_executions.trace_id (B.2 column).

    C.6 implements (likely via on_llm_start hook + run_id from kwargs).
    """

    def __init__(self, execution_id: UUID, db_session: Any) -> None:
        self.execution_id = execution_id
        self.db_session = db_session

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: object,
    ) -> None:
        raise NotImplementedError("Implemented in Faz 3 C.6 (telemetry)")
```

### 6. `__init__.py` — re-exports

```python
# apps/api/src/aeogen/agents/core/__init__.py
from aeogen.agents.core.base import Agent, AgentKind
from aeogen.agents.core.callbacks import CostTracker, LangSmithTraceHandler
from aeogen.agents.core.protocols import (
    AgentTool,
    EmbeddingProvider,
    LLMProvider,
    MemoryBackend,
    SkillProvider,
)
from aeogen.agents.core.types import (
    AgentContext,
    LLMChunk,
    LLMResponse,
    MemoryHit,
    Message,
    Skill,
)

__all__ = [
    "Agent",
    "AgentContext",
    "AgentKind",
    "AgentTool",
    "CostTracker",
    "EmbeddingProvider",
    "LangSmithTraceHandler",
    "LLMChunk",
    "LLMProvider",
    "LLMResponse",
    "MemoryBackend",
    "MemoryHit",
    "Message",
    "Skill",
    "SkillProvider",
]
```

```python
# apps/api/src/aeogen/agents/__init__.py
from aeogen.agents.core import Agent  # short import

__all__ = ["Agent"]
```

### 7. Tests — `tests/test_agent_core_protocols.py`

```python
"""C.1 Protocol conformance + ABC invariant tests.

These tests run BOTH:
- pytest at runtime (ABC checks via __init_subclass__)
- mypy --strict at type-check time (Protocol structural conformance)
"""
from typing import AsyncIterator
from uuid import uuid4

import pytest

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
    with pytest.raises(Exception):  # pydantic ValidationError on frozen
        ctx.execution_id = uuid4()  # type: ignore[misc]
```

### 8. Dependency pins (`apps/api/pyproject.toml`)

Add to `[project.dependencies]`:

```toml
dependencies = [
    # ... existing fastapi, pydantic, etc. ...
    "langchain-core>=0.3,<0.4",
    "langgraph>=0.6,<0.7",
    "langsmith>=0.5,<0.6",
]
```

**Note:** `langchain-openai` deferred to C.3 (only needed for OpenRouter adapter impl).
**Note:** `pydantic>=2.9,<3` already present from A.T5; verify.

### 9. mypy + ruff sanity

After files written, run:

```powershell
cd apps/api
uv sync  # pulls langchain-core, langgraph, langsmith
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
```

All gates exit 0.

## Risks

- **`typing.Protocol` + `@runtime_checkable` + mypy --strict** sometimes surfaces false positives on optional kwargs (`**opts`). Mitigation: use explicit keyword-only args (`*,` separator) in Protocol signatures — already done in spec.
- **`langchain-core` 0.3 stability:** semi-mature in 2026. Breaking changes happen at minor bumps. Pin range `>=0.3,<0.4` conservative; v1.5 evaluates 0.4.
- **`AsyncCallbackHandler` import** — at langchain-core 0.3, path is `langchain_core.callbacks` (NOT `langchain.callbacks` legacy). Spec uses the new path.
- **`runtime_checkable` Protocol with non-method attributes** (`AgentTool.name`, `AgentTool.schema`) → `isinstance()` checks work but slow. Used sparingly; type-check is the real gate.
- **`Agent.__init_subclass__` raise on abstract subclass** — guarded by `__abstractmethods__` check. Edge case: subclass that's still abstract (e.g., shared parent like `BaseAnalyzer`) — won't raise until concrete subclass.
- **`AgentContext.db_session: Any`** — opaque to core SDK to avoid importing sqlalchemy at this layer. C.4 narrows when impl arrives. mypy strict accepts `Any` here intentionally; lint rule `disallow-any-expr` is OFF (default).
- **No DB touch in C.1** — but tests import core module; if any test accidentally hits DB, it fails. Conformance tests are pure Python; no DB needed.
- **Master plan §4.C.1 signatures** vary slightly (master plan uses positional `query: str`, this spec uses `query: str` with keyword-only — minor refinement, not deviation).

## Open questions

1. **`AgentTool.schema: type[object]` vs `type[BaseModel]`** — at C.1 we can't import BaseModel in Protocol without circular risk. **Resolution:** use `type[object]`, narrow at concrete tool impl with `if not issubclass(self.schema, BaseModel): raise`. C.3 hardens.
2. **`MemoryBackend.search()` returns `score: float`** semantics — cosine similarity ∈ [-1, 1]? Or normalized 0-1? **Resolution:** Protocol declares `float` agnostic, C.4 impl documents cosine. Faz 5 E retrieval code asserts > threshold (e.g., 0.7).
3. **`SkillProvider.get_skill()` cache layer?** — DB query on every call expensive. **Resolution:** Protocol stays cache-agnostic. C.5 impl adds local LRU + DB query. v1.5 distributed cache.
4. **`Agent.run()` return type `BaseModel`** generic enough? Use `TypeVar` bound to BaseModel? **Resolution:** v1 uses non-generic `BaseModel`. v1.5 generic if needed.
5. **`callbacks.py` belongs in `core/` or `telemetry/`?** — `core/` for now (small file, callback wiring is core concern). C.6 can split if grows.

---

## Acceptance criteria

- [ ] `apps/api/src/aeogen/agents/__init__.py` re-exports `Agent`
- [ ] `apps/api/src/aeogen/agents/core/__init__.py` re-exports 14 symbols (Agent, AgentContext, AgentKind, AgentTool, CostTracker, EmbeddingProvider, LangSmithTraceHandler, LLMChunk, LLMProvider, LLMResponse, MemoryBackend, MemoryHit, Message, Skill, SkillProvider)
- [ ] `protocols.py` defines 5 `@runtime_checkable` Protocols
- [ ] `types.py` defines 6 Pydantic BaseModels with `extra="forbid"` + `frozen=True`
- [ ] `base.py` Agent ABC: 4 ClassVars + `__init_subclass__` validator + `__init__` accepting callbacks + abstract `run()`
- [ ] `callbacks.py` CostTracker + LangSmithTraceHandler classes with `raise NotImplementedError` bodies
- [ ] `tests/test_agent_core_protocols.py` contains 5+ tests: 1 LLMProvider conformance + 4 ABC invariant + AgentContext frozen
- [ ] `pyproject.toml` adds `langchain-core>=0.3,<0.4`, `langgraph>=0.6,<0.7`, `langsmith>=0.5,<0.6`
- [ ] `uv sync` succeeds with the new pins
- [ ] `uv run ruff check .` + `ruff format --check .` exit 0
- [ ] `uv run mypy src` exit 0 (strict mode, Protocols enforce conformance)
- [ ] `uv run pytest -v` runs new tests + existing health tests, all pass
- [ ] PR opened, code-reviewer PASS, merged to `dev`
- [ ] PROGRESS.md updated → Faz 3 C.1 ✅
- [ ] Memory entry written + MEMORY.md index
