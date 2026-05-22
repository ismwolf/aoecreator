# Faz 3 C.1 — Agent SDK SOLID Protocols Implementation Plan

Date: 2026-05-19
Spec: `docs/specs/2026-05-19-faz3c-c1-protocols-spec.md`
Phase: Faz 3 C → sub-cycle C.1 (foundation contracts)
Predecessors: Faz 2 B ✅
Successors: C.2 (LangGraph + PostgresSaver + langgraph schema), C.3 (OpenRouter LLM adapter), C.4-C.7

## Pre-flight assumptions

- Branch `feature/C.1-agent-protocols` already checked out by orchestrator.
- `apps/api/` baseline operational (A.T5): uv + ruff + mypy strict + pytest-asyncio + pydantic-settings.
- `apps/api/src/aeogen/` package exists with `py.typed` marker.
- No DB migration in C.1 (langgraph schema deferred to C.2).
- No OpenRouter Settings change in C.1 (deferred to C.3).
- TDD discipline: tests written FIRST (RED), implementation SECOND (GREEN), refactor LAST.

## Tasks

### T1 — Add dependency pins to `apps/api/pyproject.toml` (~2 min)

Edit `apps/api/pyproject.toml` `[project.dependencies]`. Add:

```toml
"langchain-core>=0.3,<0.4",
"langgraph>=0.6,<0.7",
"langsmith>=0.5,<0.6",
```

(Don't add `langchain-openai` — that's C.3.)

Then:

```powershell
cd apps/api
uv sync
```

Confirm lockfile updates clean. If `langchain-core` cannot resolve with current `pydantic`/`fastapi` pins, STOP and report version conflict.

---

### T2 — Write RED tests first (`tests/test_agent_core_protocols.py`) (~10 min)

Create `apps/api/tests/test_agent_core_protocols.py` with the 5 tests from spec §7:

1. `test_llm_provider_protocol_shape` — `_FakeLLM` implements Protocol (compile-time mypy + runtime no-op)
2. `test_agent_requires_classvars` — Agent subclass missing ClassVars raises TypeError
3. `test_agent_invalid_kind_rejected` — kind ≠ analyzer/generator/orchestrator raises TypeError
4. `test_agent_technique_id_out_of_range_rejected` — technique_id outside 1-12 raises
5. `test_agent_valid_subclass_succeeds` — well-formed subclass class-defines cleanly
6. `test_agent_context_immutable` — frozen pydantic model rejects attribute set

Run `uv run pytest tests/test_agent_core_protocols.py -v` — **expect ImportError** (RED state — no modules yet). That's the failing test confirmation.

---

### T3 — Implement `types.py` (~5 min)

Create `apps/api/src/aeogen/agents/__init__.py` (empty for now; T7 fills re-export).
Create `apps/api/src/aeogen/agents/core/__init__.py` (empty for now; T7 fills re-export).

Create `apps/api/src/aeogen/agents/core/types.py` with the 6 Pydantic BaseModels from spec §3:

- Message
- LLMResponse
- LLMChunk
- MemoryHit
- Skill
- AgentContext

All `model_config = ConfigDict(extra="forbid", frozen=True)`. AgentContext also has `arbitrary_types_allowed=True` (for opaque `db_session: Any`).

Verify with `uv run mypy src/aeogen/agents/core/types.py`. Exit 0.

---

### T4 — Implement `protocols.py` (~5 min)

Create `apps/api/src/aeogen/agents/core/protocols.py` with the 5 Protocols from spec §2:

- `LLMProvider` (chat + stream)
- `EmbeddingProvider` (embed)
- `MemoryBackend` (get + set + search)
- `SkillProvider` (get_skill + list_skills)
- `AgentTool` (name + schema + run)

All `@runtime_checkable`. Import data classes from `aeogen.agents.core.types`.

Verify `uv run mypy src/aeogen/agents/core/protocols.py` exit 0.

---

### T5 — Implement `base.py` (~10 min)

Create `apps/api/src/aeogen/agents/core/base.py` with `Agent` ABC from spec §4:

- 4 ClassVars (name, technique_id, kind, default_llm)
- `__init_subclass__` validator (raises TypeError on missing/invalid ClassVars)
- `__init__(llm, memory, skills, *, callbacks=None)`
- `@abstractmethod async def run(input, ctx)`

Module-level `AgentKind = Literal["analyzer", "generator", "orchestrator"]`.

Import `AsyncCallbackHandler` from `langchain_core.callbacks` (NOT `langchain.callbacks` legacy).

Verify `uv run mypy src/aeogen/agents/core/base.py` exit 0.

---

### T6 — Implement `callbacks.py` iskeleti (~5 min)

Create `apps/api/src/aeogen/agents/core/callbacks.py` from spec §5:

- `CostTracker(AsyncCallbackHandler)` — `__init__(execution_id, db_session)` + `on_llm_end` raises NotImplementedError
- `LangSmithTraceHandler(AsyncCallbackHandler)` — `__init__(execution_id, db_session)` + `on_llm_start` raises NotImplementedError

Both classes' docstrings reference C.6 as the implementer.

Verify `uv run mypy src/aeogen/agents/core/callbacks.py` exit 0.

---

### T7 — Wire re-exports + run GREEN test pass (~5 min)

Fill `apps/api/src/aeogen/agents/core/__init__.py` with the 14-symbol `__all__` from spec §6.
Fill `apps/api/src/aeogen/agents/__init__.py` with `from aeogen.agents.core import Agent` short import.

Now run:

```powershell
cd apps/api
uv run pytest tests/test_agent_core_protocols.py -v
```

Expect **5+ tests PASS** (GREEN). If any fails, stop and diagnose — likely a Protocol signature mismatch or ClassVar wiring bug.

---

### T8 — Full gate run + commit (~5 min)

```powershell
cd apps/api
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
uv lock --check
```

All exit 0. Existing health tests still pass. New conformance tests pass.

Stage files (NEVER `git add .`):

- `apps/api/pyproject.toml` (deps added)
- `apps/api/uv.lock` (regenerated by `uv sync`)
- `apps/api/src/aeogen/agents/__init__.py` (new)
- `apps/api/src/aeogen/agents/core/__init__.py` (new)
- `apps/api/src/aeogen/agents/core/protocols.py` (new)
- `apps/api/src/aeogen/agents/core/types.py` (new)
- `apps/api/src/aeogen/agents/core/base.py` (new)
- `apps/api/src/aeogen/agents/core/callbacks.py` (new)
- `apps/api/tests/test_agent_core_protocols.py` (new)
- `docs/specs/2026-05-19-faz3c-c1-protocols-spec.md` (new)
- `docs/plans/2026-05-19-faz3c-c1-protocols-plan.md` (new)

Do NOT stage `docs/PROGRESS.md` — orchestrator handles after merge.

Commit message:

```
feat(api/agents): C.1 SOLID protocols + Agent ABC iskeleti (Faz 3 C.1)

5 typing.Protocol (LLMProvider, EmbeddingProvider, MemoryBackend,
SkillProvider, AgentTool) + 6 Pydantic data classes (Message,
LLMResponse, LLMChunk, MemoryHit, Skill, AgentContext) + Agent ABC
with ClassVar invariants (__init_subclass__ enforces) + CostTracker
+ LangSmithTraceHandler iskeleti (raise NotImplementedError, C.6
implements).

Decisions (locked 2026-05-19):
- typing.Protocol for swap-able providers; abc.ABC for Agent;
  pydantic.BaseModel for data classes (langchain-master consultation)
- Module path: apps/api/src/aeogen/agents/core/ (master plan §4.C aligned)
- AgentContext minimal 3-field: execution_id, workspace_id, db_session
- Test strategy: mypy strict + Protocol conformance + ABC invariant
  (5 tests, no real LLM/DB integration)
- SkillProvider DB-only (no filesystem fallback)
- LangChain pin: langchain-core/langgraph/langsmith range pins
- langgraph schema migration deferred to C.2
- OPENROUTER_API_KEY Settings change deferred to C.3
- Concrete impls deferred to C.3 (LLM), C.4 (memory), C.5 (skills),
  C.6 (telemetry bodies), C.7 (integration tests)

5 conformance tests pass; ruff + mypy strict + pytest all green.

Spec: docs/specs/2026-05-19-faz3c-c1-protocols-spec.md
Plan: docs/plans/2026-05-19-faz3c-c1-protocols-plan.md
```

Push `feature/C.1-agent-protocols`. Do NOT open PR — orchestrator handles.

---

### T9 — Orchestrator handles

- Code-reviewer dispatch (`aeogen-code-reviewer`)
- `gh pr create` + merge
- PROGRESS.md edit
- Memory entry `project_faz3c1_protocols_baseline.md`
- `git checkout dev && git pull && git branch -d feature/C.1-agent-protocols`

## Risks

- **`uv sync` resolver conflict** — langchain-core might pull pydantic v2.10+ when our pin is `<3`. Mitigation: range pin both. If conflict, narrow to specific minor that aligns (e.g., `pydantic>=2.9,<2.12`).
- **mypy strict + Protocol** — `@runtime_checkable` + abstract methods sometimes produces `Cannot instantiate abstract class` false positives. Mitigation: tests use concrete classes (`_FakeLLM`), never `LLMProvider()` directly.
- **`__init_subclass__` triggered by re-import** — pytest discovers test classes; if a test class accidentally inherits Agent without ClassVars, fails at collection. Mitigation: test fixtures use `class _Good(Agent): ...` inside test functions (local scope), not module-level.
- **`langchain_core.callbacks.AsyncCallbackHandler` import path** — at 0.3.x this is stable; if it moves in 0.3.x.y patch, mypy catches. Pin range conservative.
- **Pydantic `frozen=True` + `arbitrary_types_allowed=True`** for AgentContext — well-supported in pydantic 2.9+. mypy understands.
- **`langgraph` import in C.1** — not actually used by C.1 code, but listed in deps for C.2 prep. uv sync still pulls it. Acceptable.
- **`langsmith` import in C.1** — same as above, dep listed but unused until C.6.

## Verification gate

```
uv sync → exit 0, lockfile current
uv run ruff check . → exit 0
uv run ruff format --check . → exit 0
uv run mypy src → exit 0 (strict)
uv run pytest -v → 5+ new tests pass, existing health tests pass, total >= 7 PASSED
uv lock --check → exit 0
git diff --stat → ~10-12 files: 1 pyproject, 1 lock, 6 source, 1 test, 2 doc
```

## Branch + commit suggestion

- Branch: `feature/C.1-agent-protocols`
- Commit: see T8
- PR target: `dev`
- After merge: PROGRESS marks Faz 3 C.1 ✅, sıradaki C.2 (LangGraph + PostgresSaver + langgraph schema migration)
