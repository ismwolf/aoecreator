# Faz 3 C.2 — LangGraph Checkpoint + `langgraph` Schema Plan

Date: 2026-05-20
Spec: `docs/specs/2026-05-20-faz3c-c2-langgraph-checkpoint-spec.md`
Phase: Faz 3 C → sub-cycle C.2
Predecessors: C.1 ✅ (Agent ABC iskeleti, langchain-core/langgraph/langsmith pinned)
Successors: C.3 (OpenRouter LLM), C.4 (memory backend), C.5 (skill registry), C.6 (telemetry bodies), C.7 (tests)

## Pre-flight assumptions

- Branch `feature/C.2-langgraph-checkpoint` already checked out by orchestrator.
- C.1 merged on dev: `langgraph==0.6.11` dep present, `AsyncPostgresSaver` importable from `langgraph.checkpoint.postgres.aio`.
- Supabase MCP authenticated, project `ngjlxlkdfgfhiookndpl`.
- B.1+B.2+B.3 migrations on Cloud (3 migrations in registry).
- TDD: tests first (RED), implementation second (GREEN).
- Per global rule: MCP `apply_migration` + local file mirror.

## Tasks

### T1 — Verify AsyncPostgresSaver API (~3 min)

Run via `uv run python -c "..."`:
```python
import inspect
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
print(inspect.signature(AsyncPostgresSaver.from_conn_string))
print(AsyncPostgresSaver.from_conn_string.__doc__[:500] if AsyncPostgresSaver.from_conn_string.__doc__ else "no doc")
```

Two outcomes:
- **A.** Signature accepts a `schema` / `schema_name` kwarg → use it.
- **B.** No schema kwarg → inject `options=-csearch_path%3Dlanggraph` into the connection string.

Document the actual choice in `checkpoint.py` docstring + commit message.

If `AsyncPostgresSaver` doesn't even import → STOP, report (langgraph dep broken).

---

### T2 — Write RED test first (~5 min)

Create `apps/api/tests/test_checkpoint_factory.py` per spec §4:
- `test_build_postgres_saver_is_async_context_manager` — calls factory, checks `isinstance(cm, AbstractAsyncContextManager)`
- `test_build_postgres_saver_signature` — inspects signature, asserts `db_url: str` param

Run `uv run pytest tests/test_checkpoint_factory.py -v` → expect `ModuleNotFoundError` (RED — checkpoint.py doesn't exist yet). Quote the error.

---

### T3 — Apply migration via MCP (~3 min)

Write `supabase/migrations/20260520000000_langgraph_schema.sql` per spec §1.

Apply:
```
mcp__supabase__apply_migration(
  name="langgraph_schema",
  query=<SQL body>
)
```

If error:
- Schema name conflict (already exists) → already created (rare); proceed with verify
- Permission denied → STOP, report (service_role grant unexpected fail)

Verify:
```
mcp__supabase__execute_sql("select schema_name from information_schema.schemata where schema_name='langgraph';")
```
Expect 1 row. If 0 rows → STOP.

```
mcp__supabase__get_advisors(type="security")
```
Expect `{"lints": []}` (or document any `langgraph` schema warning as accepted exception).

---

### T4 — Extend Settings (~5 min)

Edit `apps/api/src/aeogen/settings.py`:
- Add import: `from pydantic import PostgresDsn, AliasChoices` (if not present)
- Add field: `database_url: PostgresDsn = Field(..., validation_alias=AliasChoices("DATABASE_URL"), description="Direct Postgres connection — NOT Supabase API URL")`
- Optional: `repr=False` on Field to prevent leak in logs

Update `apps/api/.env.example`:
```bash
# === Postgres direct connection (NOT Supabase API URL) ===
# Used by AsyncPostgresSaver. Supabase: Project Settings > Database >
# Connection String > URI. Use Session pooler (port 5432), NOT Transaction
# pooler (6543) — LangGraph uses transactions that break in transaction mode.
DATABASE_URL=postgresql://postgres.<project-ref>:<password>@aws-0-<region>.pooler.supabase.com:5432/postgres
```

Update `apps/api/tests/conftest.py` to inject a fake DATABASE_URL for tests (else Settings instantiation fails):
```python
# Top of conftest, before any aeogen imports
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
```

Run `uv run mypy src` — should still be Success.

---

### T5 — Implement `checkpoint.py` (~10 min)

Create `apps/api/src/aeogen/agents/core/checkpoint.py` per spec §3.

**Schema selection logic (decision branch from T1):**
- If T1 found schema kwarg → use it in `from_conn_string(db_url, schema="langgraph")` or equivalent
- Else → rewrite db_url to append `?options=-csearch_path%3Dlanggraph` (preserve existing query params with proper URL parse)

Example (branch B fallback):
```python
from urllib.parse import urlsplit, urlunsplit, parse_qsl, urlencode

def _with_search_path(db_url: str, schema: str) -> str:
    parts = urlsplit(db_url)
    query = dict(parse_qsl(parts.query))
    existing_options = query.get("options", "")
    new_option = f"-csearch_path={schema}"
    query["options"] = f"{existing_options} {new_option}".strip()
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@asynccontextmanager
async def build_postgres_saver(db_url: str) -> AsyncIterator[AsyncPostgresSaver]:
    dsn = _with_search_path(db_url, "langgraph")  # only if T1 branch B
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
        yield saver
```

Run `uv run mypy src/aeogen/agents/core/checkpoint.py` — Success expected.

---

### T6 — Update re-exports (~2 min)

Edit `apps/api/src/aeogen/agents/core/__init__.py`:
- Add `from aeogen.agents.core.checkpoint import build_postgres_saver`
- Append `"build_postgres_saver"` to `__all__` (sorted, 15 symbols total)

Run pytest again — expect 2 new tests PASS (GREEN). Quote the pass output.

---

### T7 — Regenerate `database.types.ts` (~2 min)

After migration, run `mcp__supabase__generate_typescript_types()`. The output adds `langgraph` schema to the `Database` type (even though we won't read it from frontend). Write to `apps/web/src/lib/database.types.ts`.

Verify:
```powershell
pnpm --filter @aeogen/web typecheck
pnpm --filter @aeogen/web lint
pnpm --filter @aeogen/web build
```
All exit 0.

---

### T8 — Full gate run + commit + push (~5 min)

```powershell
cd apps/api
uv run ruff check .
uv run ruff format --check .
uv run mypy src
uv run pytest -v
uv lock --check
```

All exit 0. Pytest: 9+ passed (6 C.1 + 2 health + 2 new = 10).

Stage:
- `supabase/migrations/20260520000000_langgraph_schema.sql` (new)
- `apps/api/src/aeogen/settings.py` (modified)
- `apps/api/src/aeogen/agents/core/__init__.py` (modified, +1 symbol)
- `apps/api/src/aeogen/agents/core/checkpoint.py` (new)
- `apps/api/tests/test_checkpoint_factory.py` (new)
- `apps/api/tests/conftest.py` (modified — DATABASE_URL env injection)
- `apps/api/.env.example` (modified)
- `apps/web/src/lib/database.types.ts` (modified — langgraph schema added)
- `docs/specs/2026-05-20-faz3c-c2-langgraph-checkpoint-spec.md` (new)
- `docs/plans/2026-05-20-faz3c-c2-langgraph-checkpoint-plan.md` (new)

Do NOT stage `docs/PROGRESS.md` — orchestrator handles.

Commit (HEREDOC):
```
feat(api/agents,db): C.2 LangGraph checkpoint + `langgraph` schema (Faz 3 C.2)

- New `langgraph` schema in Supabase via MCP apply_migration (no DDL
  tables — AsyncPostgresSaver creates checkpoints/blobs/writes via
  .setup() at first call, drift-safe)
- `apps/api/src/aeogen/agents/core/checkpoint.py`: build_postgres_saver
  async context manager wraps AsyncPostgresSaver.from_conn_string with
  auto-setup() + search_path=langgraph injection
- Settings: DATABASE_URL: PostgresDsn (direct Postgres conn, NOT API URL)
- .env.example: format hint + Session pooler note (Transaction mode
  breaks LangGraph's BEGIN/SAVEPOINT usage)
- 2 type/contract tests (no real DB) — Testcontainers DB test deferred
  to C.7

Decisions (locked 2026-05-20):
- Schema-only migration (PostgresSaver auto-creates tables — drift-safe)
- PostgresDsn validator (fail-fast at app startup on bad URL)
- Per-run from_conn_string lifecycle (no pool — v1.5 reconsiders)
- Type/factory test only (real integration via Testcontainers → C.7)
- A.T9 env vars distributed JIT — DATABASE_URL here, OPENROUTER_API_KEY
  in C.3, REDIS_URL in Celery phase

Spec: docs/specs/2026-05-20-faz3c-c2-langgraph-checkpoint-spec.md
Plan: docs/plans/2026-05-20-faz3c-c2-langgraph-checkpoint-plan.md
```

Push `feature/C.2-langgraph-checkpoint`. Do NOT open PR.

---

### T9 — Orchestrator handles

- Code-reviewer dispatch
- Paranoia MCP re-check (`get_advisors`, `list_tables langgraph`, `execute_sql` schema verify)
- `gh pr create` + merge
- PROGRESS.md edit (mark C.2 ✅, A.T9 distributed note, sıradaki C.3)
- Memory entry `project_faz3c2_checkpoint_baseline.md` + MEMORY.md index
- `git checkout dev && git pull && git branch -d feature/C.2-langgraph-checkpoint`

## Risks

- **AsyncPostgresSaver schema API uncertainty** (T1 resolves). If both branches fail (unlikely), fallback: explicit `set search_path = langgraph` SQL before saver calls — invasive, not preferred.
- **Settings instantiation breaks existing tests** if DATABASE_URL not in test env. T4 includes conftest env injection. Verify A.T5 health tests still pass.
- **`PostgresDsn` rejects asyncpg-style URL** — `postgresql+asyncpg://` not accepted. We need raw `postgresql://`. Code-writer ensures `.env.example` uses raw form. LangGraph wraps with its own driver internally.
- **`.setup()` first run** writes 3 tables. If multi-instance cold-start race, Postgres serializes — second instance sees IF EXISTS and proceeds. No data corruption risk; minor latency spike at first deploy.
- **Pooler mode** — Session pooler (port 5432) required. Transaction pooler (6543) silently breaks LangGraph's transactions. Documented in `.env.example`; user enforces.
- **`langgraph` schema RLS advisor warning** — Supabase Advisor may flag absence of RLS on framework schema. Manual exception OK; document in memory if it fires.
- **`database.types.ts` regen** — may grow significantly (langgraph schema can be empty initially, but might include PostgresSaver tables after `.setup()`). Acceptable.

## Verification gate

```
mcp__supabase__execute_sql("select schema_name from information_schema.schemata where schema_name='langgraph';") → 1 row
mcp__supabase__get_advisors("security") → {"lints": []} (or only langgraph schema warning, documented)
mcp__supabase__list_migrations() → langgraph_schema entry present (4 migrations total)
uv run ruff check . → exit 0
uv run ruff format --check . → exit 0
uv run mypy src → exit 0 (strict)
uv run pytest -v → 10 passed (6 C.1 + 2 health + 2 new)
uv lock --check → exit 0
pnpm --filter @aeogen/web typecheck/lint/build → all exit 0
git status --porcelain → only expected files staged
```

## Branch + commit suggestion

- Branch: `feature/C.2-langgraph-checkpoint`
- Commit: see T8
- PR target: `dev`
- After merge: PROGRESS marks C.2 ✅, sıradaki C.3 (OpenRouter LLM adapter + OPENROUTER_API_KEY Settings + langchain-openai dep)
