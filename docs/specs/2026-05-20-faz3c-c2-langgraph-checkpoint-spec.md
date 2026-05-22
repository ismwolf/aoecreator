# Faz 3 C.2 — LangGraph + AsyncPostgresSaver + `langgraph` Schema Spec

Date: 2026-05-20
Phase: Faz 3 C (Agent Core SDK) → sub-cycle C.2
Predecessors: Faz 3 C.1 ✅ (5 Protocols + 6 Pydantic types + Agent ABC iskeleti, PR #14)
Successors: C.3 (OpenRouter LLM adapter), C.4-C.7

## Problem

C.1 Agent ABC'sini `abstract run()` ile bıraktı. Concrete agent'lar (Faz 5 E) bir LangGraph `StateGraph` compile edip `AsyncPostgresSaver` ile checkpoint'leyecek — agent kesintide kaldığı yerden devam edebilir. Çekirdek altyapı eksik:

1. **`langgraph` schema** Supabase'de yok — checkpoint tabloları `public`'de istemiyoruz (Faz 2 B "public sadece tenant data" invariant'ını kırar)
2. **`DATABASE_URL` Settings'te yok** — apps/api şu an sadece Supabase API URL biliyor; `AsyncPostgresSaver` direct Postgres connection string istiyor
3. **Saver lifecycle helper yok** — her concrete agent kendi başına `from_conn_string` + `setup()` çağırmamalı (DRY ihlali + setup race riski)

C.2 alt-cycle'ı bu 3 boşluğu doldurur. C.3-C.7 bu altyapı üstüne çalışır.

## Goals

- **Yeni migration:** `supabase/migrations/<ts>_langgraph_schema.sql` — `create schema langgraph` + service_role grants (no DDL tables — PostgresSaver kendi 3 tablosunu `.setup()` ile yaratır, drift-safe)
- **`apps/api/src/aeogen/agents/core/checkpoint.py`** — `build_postgres_saver(db_url) -> AsyncIterator[AsyncPostgresSaver]` async context manager helper:
  - Opens `AsyncPostgresSaver.from_conn_string(db_url)` with `search_path=langgraph` (or LangGraph 0.6+'s native `schema_name` kwarg if available — code-writer verifies at impl)
  - Calls `await saver.setup()` (idempotent — LangGraph internal migration apply)
  - Yields saver for caller's use
  - Cleanup on exit (`__aexit__`)
- **`apps/api/src/aeogen/settings.py`** — add `DATABASE_URL: PostgresDsn` field + `model_config.env_nested_delimiter` if needed; loaded from env
- **`apps/api/.env.example`** — add `DATABASE_URL` placeholder with Supabase format hint:
  `# Postgres direct connection (NOT API URL). Supabase: Project Settings > Database > Connection String > URI`
  `DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres`
- **Test:** `apps/api/tests/test_checkpoint_factory.py` — type/contract assertions (no real DB connection):
  - `build_postgres_saver` returns async context manager
  - On enter, yields `AsyncPostgresSaver` instance
  - mypy strict: signature conforms to expected types
- All gates green: ruff, mypy strict, pytest (test count grows to 9: 6 C.1 + 2 health + 1 new)
- Apply migration via MCP `apply_migration` + local mirror
- `get_advisors('security')` clean (no new policies, just schema add)

## Non-Goals (deferred)

- **Actual StateGraph implementation** for any concrete agent → **Faz 5 E** (each agent owns its graph)
- **PostgresSaver `.setup()` table verification via execute_sql** → **C.7** (real DB integration test with Testcontainers)
- **Connection pooling** (asyncpg pool or SQLAlchemy AsyncEngine reuse) → **v1.5** (per-run from_conn_string is canonical v1 per brainstorm decision)
- **Multi-tenant thread_id scoping** (workspace_id namespacing in thread_id) → **Faz 5 E** (concrete agents decide thread_id format; spec advisory: `str(ctx.execution_id)`)
- **Checkpoint retention/cleanup job** (purge old checkpoints) → **Faz 7 H** ops runbook
- **RLS on `langgraph.*` tables** → **N/A** — checkpoint tables are framework infra, service_role-only access, no tenant data
- **C.3 OpenRouter Settings extension** → **C.3** PR adds `OPENROUTER_API_KEY: SecretStr`
- **`StateGraph` builder helper** (e.g., a common analyzer pattern factory) → **Faz 5 E**
- **Postgres `checkpointer.list()` audit query for ops dashboard** → **Faz 6 F**

## Approach

### 1. Migration: `supabase/migrations/20260520000000_langgraph_schema.sql`

```sql
-- Faz 3 C.2 — LangGraph checkpoint schema
-- AsyncPostgresSaver creates its own tables (checkpoints, checkpoint_blobs, checkpoint_writes)
-- in this schema via .setup() at runtime. We only create the schema + grants.

create schema if not exists langgraph;

-- service_role bypasses RLS, so it can write to any schema.
-- We don't grant authenticated/anon — checkpoint tables are framework infra,
-- never read directly from app/UI.
grant usage on schema langgraph to postgres, service_role;
grant create on schema langgraph to service_role;  -- so .setup() can CREATE TABLE
```

Notes:

- No `enable row level security` — `langgraph.*` tables are server-side only
- No RLS policies — only service_role connects via DATABASE_URL
- `service_role`'s `CREATE` grant lets `AsyncPostgresSaver.setup()` provision its 3 tables on first run

### 2. Settings extension: `apps/api/src/aeogen/settings.py`

```python
# Existing imports + Settings class — only diff shown
from pydantic import PostgresDsn, SecretStr

class Settings(BaseSettings):
    # ... existing fields (SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SECRET_KEY) ...

    database_url: PostgresDsn = Field(
        ...,
        description=(
            "Direct Postgres connection string (NOT Supabase API URL). "
            "Required for AsyncPostgresSaver. Format: "
            "postgresql://postgres.<ref>:<pwd>@aws-0-<region>.pooler.supabase.com:6543/postgres"
        ),
        validation_alias=AliasChoices("DATABASE_URL"),
    )
```

`PostgresDsn` validates the connection URL structure at import time — invalid format fails fast at app startup.

### 3. Checkpoint helper: `apps/api/src/aeogen/agents/core/checkpoint.py`

```python
"""LangGraph checkpoint helper.

Wraps AsyncPostgresSaver with auto-setup so concrete agents don't repeat boilerplate.
v1 pattern: per-Agent.run() context manager (no pool). v1.5 may add pool reuse.
"""
from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver


@asynccontextmanager
async def build_postgres_saver(db_url: str) -> AsyncIterator[AsyncPostgresSaver]:
    """Open an AsyncPostgresSaver pointing at the `langgraph` schema.

    Calls `.setup()` on entry (idempotent — LangGraph applies its own internal
    migrations). The yielded saver is ready to pass to `graph.compile(checkpointer=...)`.

    Args:
        db_url: Postgres connection string. Pass `str(settings.database_url)`.

    Usage:
        async with build_postgres_saver(str(settings.database_url)) as saver:
            graph = builder.compile(checkpointer=saver)
            result = await graph.ainvoke(
                input,
                config={"configurable": {"thread_id": str(ctx.execution_id)}},
            )
    """
    # LangGraph 0.6: AsyncPostgresSaver may accept a `schema` or `schema_name` kwarg
    # — if not, fall back to `?options=-csearch_path%3Dlanggraph` query param in db_url.
    # Code-writer verifies at impl time via signature inspection.
    async with AsyncPostgresSaver.from_conn_string(db_url) as saver:
        await saver.setup()
        yield saver
```

**Schema selection at impl time:** if `AsyncPostgresSaver.from_conn_string` does NOT accept a schema kwarg in 0.6.11, the helper rewrites the connection string to inject `options=-csearch_path%3Dlanggraph` so PostgresSaver's CREATE TABLE statements land in the right schema. Code-writer verifies via `inspect.signature(AsyncPostgresSaver.from_conn_string)` at T-time.

### 4. Test: `apps/api/tests/test_checkpoint_factory.py`

```python
"""C.2 checkpoint factory — type/contract assertions, no real DB."""
from contextlib import AbstractAsyncContextManager
from inspect import iscoroutinefunction

from aeogen.agents.core.checkpoint import build_postgres_saver


def test_build_postgres_saver_is_async_context_manager() -> None:
    """The factory must return an async context manager (not a saver directly)."""
    cm = build_postgres_saver("postgresql://fake:fake@localhost/test")
    assert isinstance(cm, AbstractAsyncContextManager)


def test_build_postgres_saver_signature() -> None:
    """Factory takes db_url: str."""
    import inspect

    sig = inspect.signature(build_postgres_saver)
    params = list(sig.parameters.values())
    assert len(params) == 1
    assert params[0].name == "db_url"
    assert params[0].annotation is str
```

**No real DB connection.** Connecting to `localhost/test` would fail anyway in CI. The CM is constructed but not entered. C.7 adds Testcontainers Postgres test that actually enters + `.setup()` + writes a checkpoint.

### 5. Re-exports update

`apps/api/src/aeogen/agents/core/__init__.py` `__all__` extended with `build_postgres_saver` (15 symbols total).

### 6. `.env.example` extension

```bash
# Add to apps/api/.env.example, near SUPABASE_* block:

# Postgres direct connection (NOT Supabase API URL).
# Supabase: Project Settings > Database > Connection String > URI (use pooler for serverless/edge)
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:6543/postgres
```

User must populate this in `.env.local` (gitignored) post-merge.

## Risks

- **`AsyncPostgresSaver.from_conn_string` schema kwarg API uncertain across versions.** Mitigation: code-writer inspects signature at impl, falls back to `search_path` connection param. Both approaches functionally equivalent.
- **`.setup()` idempotency:** LangGraph 0.6 docs state it's safe to call repeatedly. Multi-process race at first cold-start could see two processes attempting `CREATE TABLE` — Postgres serializes this, second sees "already exists" and proceeds. No-op for our cases.
- **`PostgresDsn` validation strictness:** doesn't allow `postgresql+asyncpg://` driver prefix. We need raw Postgres URL (LangGraph wraps with its own driver). User input format documented in `.env.example`.
- **Connection pool exhaustion** per-run pattern opens 1 conn per Agent.run(). For Celery workers running 100s of agents/min, this could exhaust the Supabase pooler. v1 OK (low traffic); v1.5 add `asyncpg.create_pool` reuse if monitoring shows pressure.
- **`langgraph` schema RLS:** intentionally NOT enabled. Supabase Advisor MAY flag this as "table without RLS" if the schema-level lint runs (B.1 advisor was clean for `private` schema, expect same for `langgraph`). Mitigation: if advisor flags, document the exception (framework infra schema, service_role-only).
- **Migration timestamp drift:** `20260520000000` is today's UTC. If a parallel developer commits at same timestamp, conflict. Single-developer now, no issue.
- **MCP `apply_migration` `name="langgraph_schema"`** — Supabase migration registry may complain if name collides with reserved word. Use `langgraph_schema_init` if first attempt fails.
- **`DATABASE_URL` leak risk:** Settings reads it, code logs Settings on debug. Pydantic's `SecretStr` would prevent leak in `__repr__` but `PostgresDsn` doesn't auto-redact. Mitigation: code-writer adds `repr=False` to the Field if pydantic v2 supports.

## Open questions

1. **AsyncPostgresSaver schema kwarg name** — `schema`? `schema_name`? `search_path`? Code-writer resolves via `inspect.signature(AsyncPostgresSaver.from_conn_string)` at T3. Plan covers both branches.
2. **Pooler vs direct connection** — Supabase offers Transaction pooler (6543), Session pooler (5432), and Direct (5432 with `?sslmode=require`). For long-lived agent runs with statement-spanning transactions, **Session pooler** is correct. Pooler (Transaction mode) breaks if `BEGIN; SAVEPOINT; ...` patterns used (LangGraph does this). Document in `.env.example` to use Session pooler URL.
3. **Settings field name:** `database_url` (snake case, matches env var `DATABASE_URL`) — pydantic-settings auto-handles. Lock.
4. **`build_postgres_saver` location** — `core/checkpoint.py` distinct from `core/callbacks.py`. Could merge as `core/integrations.py` but separation cleaner (different concerns: persistence vs telemetry).
5. **Schema explicit DDL in migration?** — already locked NO (drift-safe). Re-confirm.

---

## Acceptance criteria

- [ ] `supabase/migrations/20260520000000_langgraph_schema.sql` exists, applied via MCP `apply_migration`
- [ ] `mcp__supabase__execute_sql("select schema_name from information_schema.schemata where schema_name='langgraph';")` returns 1 row
- [ ] `get_advisors('security')` lints empty (or only documents `langgraph` schema as framework infra without RLS)
- [ ] `apps/api/src/aeogen/agents/core/checkpoint.py` exists with `build_postgres_saver` async context manager
- [ ] `apps/api/src/aeogen/settings.py` has `database_url: PostgresDsn` field
- [ ] `apps/api/.env.example` has `DATABASE_URL` placeholder with format hint
- [ ] `apps/api/src/aeogen/agents/core/__init__.py` re-exports `build_postgres_saver` (15-symbol `__all__`)
- [ ] `apps/api/tests/test_checkpoint_factory.py` has 2+ tests, both pass without real DB
- [ ] `uv run ruff check .` + `ruff format --check .` exit 0
- [ ] `uv run mypy src` exit 0 (strict)
- [ ] `uv run pytest -v` → 9+ passed (6 C.1 + 2 health + 2+ new)
- [ ] PR opened, code-reviewer PASS, merged to `dev`
- [ ] PROGRESS.md updated → Faz 3 C.2 ✅, sıradaki C.3
- [ ] Memory entry written + MEMORY.md index
