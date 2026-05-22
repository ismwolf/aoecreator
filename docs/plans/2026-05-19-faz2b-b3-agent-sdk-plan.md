# Faz 2 B.3 — Agent SDK Support + pgvector Implementation Plan

Date: 2026-05-19
Spec: `docs/specs/2026-05-19-faz2b-b3-agent-sdk-spec.md`
Phase: Faz 2 B → sub-cycle B.3 (closes Faz 2 B)
Predecessors: B.1 ✅, B.2 ✅
Successors: Faz 2 G, Faz 3 C, Faz 4 D

## Pre-flight assumptions

- Branch `feature/B.3-agent-sdk-support` already checked out.
- Supabase MCP authenticated, `ngjlxlkdfgfhiookndpl`.
- B.1 + B.2 merged to dev (`private.user_workspace_ids()`, `private.is_org_admin(uuid)`, `extensions.moddatetime`, `extensions.uuid_generate_v4()` all available).
- `pages.id` exists (B.2) — embeddings FK target.
- `pgvector` extension support on Cloud project — verify in T0 (`list_extensions`).
- Per global rule: MCP `apply_migration` + local file mirror.

## Tasks

### T0 — Pre-flight pgvector check (~1 min)

**Tool call:**

```
mcp__supabase__list_extensions()
```

Confirm `vector` extension is `available_version != null` (Cloud should have 0.7+). If not available → STOP, escalate (Supabase plan upgrade may be required).

If `installed_version is null` → migration will install it. If already installed → `create extension if not exists` is no-op.

---

### T1 — Compose migration SQL + write to `supabase/migrations/` (~12 min)

**File created:** `supabase/migrations/20260519010000_b3_agent_sdk.sql`

Order:

1. `create extension if not exists vector with schema extensions;`
2. **4 table CREATE** in dependency order: `agent_memory`, `agent_skills`, `embeddings` (depends on `pages` + `workspaces`), `audit_log` (depends on `organizations`, `workspaces`, `auth.users`)
3. **Unique partial indexes** (3):
   - `agent_memory_unique_key_active_uq` on `(agent_name, scope, coalesce(workspace_id::text, ''), key) where deleted_at is null`
   - `agent_skills_agent_key_version_active_uq` on `(agent_name, skill_key, version) where deleted_at is null`
   - `embeddings_page_chunk_active_uq` on `(page_id, chunk_id) where deleted_at is null`
4. **Performance indexes** (10):
   - agent_memory (4): `agent_scope`, `workspace_id` (partial), `expires_at` (partial), `promotion`
   - agent_skills (1): `agent_key`
   - embeddings (2): `workspace_id`, `page_id` (both partial)
   - audit_log (4): `org_ts`, `workspace_ts` (partial), `actor` (partial), `action`
5. **HNSW vector index** (1):
   `create index embeddings_vector_hnsw on public.embeddings using hnsw (embedding extensions.vector_cosine_ops) with (m = 16, ef_construction = 64);`
6. **Enable RLS** on all 4 tables
7. **RLS policies** — 8 total:
   - agent_memory: 3 (`select`, `insert_workspace`, `update_workspace`)
   - agent_skills: 1 (`select_all`)
   - embeddings: 3 (B.2 pattern: `select`, `insert`, `update`)
   - audit_log: 1 (`select_org_admin` using `private.is_org_admin(org_id)`)
8. **moddatetime triggers** (3 — agent_memory, agent_skills, embeddings; NOT audit_log)

SQL byte-equivalent to what gets passed to MCP in T2.

---

### T2 — Apply migration via MCP `apply_migration` (~3 min)

```
mcp__supabase__apply_migration(
  name="b3_agent_sdk",
  query=<exact SQL string from T1 file>
)
```

If error:

- **`vector` extension not available** → STOP (T0 should have caught)
- **`private.is_org_admin` missing** → B.1 not fully present; STOP, escalate
- **Syntax error** → fix T1 file, re-apply (MCP atomic rollback on failure)

---

### T3 — Verify schema + RLS + pgvector (~4 min)

```
mcp__supabase__list_tables(schemas=["public"], verbose=true)
mcp__supabase__get_advisors(type="security")
mcp__supabase__list_extensions()
mcp__supabase__execute_sql("""
  select tablename, count(*) as policy_count
  from pg_policies
  where schemaname='public' and tablename in ('agent_memory','agent_skills','embeddings','audit_log')
  group by tablename order by tablename;
""")
mcp__supabase__execute_sql("""
  select indexname, indexdef from pg_indexes
  where schemaname='public' and indexname = 'embeddings_vector_hnsw';
""")
```

**Expected:**

- 13 tables in public; B.3's 4 with `rls_enabled=true`
- Advisors: `{"lints": []}`
- `vector` extension has `installed_version != null`
- Policy counts: agent_memory=3, agent_skills=1, embeddings=3, audit_log=1
- HNSW index present with correct definition (`USING hnsw (embedding extensions.vector_cosine_ops) WITH (m='16', ef_construction='64')` or similar pg_indexes formatting)

If any check fails → STOP, fix in a follow-up migration (do not patch silently).

---

### T4 — Regenerate `database.types.ts` (~2 min)

```
mcp__supabase__generate_typescript_types()
```

Write to `apps/web/src/lib/database.types.ts`, replacing the B.2-era file (9 tables → 13 tables). New types: agent_memory, agent_skills, embeddings, audit_log.

Note: `embeddings.embedding` (vector type) will likely surface as `string` or `unknown` in TS — Supabase generator does not have a dedicated vector type. Document this in the memory entry for Faz 4 D consumers (will need a custom Zod/Pydantic schema for vector serde).

---

### T5 — Typecheck + lint + build sanity (~3 min)

```powershell
pnpm --filter @aeogen/web typecheck
pnpm --filter @aeogen/web lint
pnpm --filter @aeogen/web build
```

All must exit 0. Code-writer reports last 10 lines of each.

---

### T6 — Commit + push + PR (~5 min)

Stage:

- `supabase/migrations/20260519010000_b3_agent_sdk.sql`
- `apps/web/src/lib/database.types.ts`
- `docs/specs/2026-05-19-faz2b-b3-agent-sdk-spec.md`
- `docs/plans/2026-05-19-faz2b-b3-agent-sdk-plan.md`

Do NOT stage `docs/PROGRESS.md` — orchestrator updates in T7.

Commit:

```
feat(db): B.3 agent SDK + pgvector — memory, skills, embeddings, audit_log (Faz 2 B.3, closes Faz 2 B)

4 tables + pgvector extension:
- agent_memory: 3-scope (global/workspace/agent) key-value with LRU stats
- agent_skills: global registry, versioned, source enum (builtin/promoted/manual)
- embeddings: BGE-M3 1024-dim + sparse jsonb, HNSW cosine m=16 ef_construction=64
- audit_log: append-only, org_id + nullable workspace_id, org-admin SELECT only

Schema decisions (locked 2026-05-19):
- agent_memory.scope 3-value enum with scope↔workspace_id invariant CHECK
- HNSW Supabase default (m=16, ef_construction=64) — production-ready for BGE-M3
- audit_log append-only via service_role (no app-level INSERT/UPDATE/DELETE policies)
- agent_skills global (no workspace_id) — SELECT open, mutations service_role only

8 RLS policies, 13 perf indexes + 3 unique partial + 1 HNSW vector.
moddatetime triggers on 3/4 (audit_log skipped).

Migration applied via mcp__supabase__apply_migration + mirrored to
supabase/migrations/20260519010000_b3_agent_sdk.sql.

database.types.ts regenerated — 13 tables (B.1: 4 + B.2: 5 + B.3: 4).

Faz 2 B now complete. Next: Faz 2 G (provision-org + invite) or
Faz 3 C (Agent Core SDK consuming agent_memory + agent_skills).

Spec: docs/specs/2026-05-19-faz2b-b3-agent-sdk-spec.md
Plan: docs/plans/2026-05-19-faz2b-b3-agent-sdk-plan.md
```

Push `feature/B.3-agent-sdk-support`. Do NOT open PR (orchestrator).

---

### T7 — Orchestrator handles (NOT code-writer's job)

- Code-reviewer dispatch
- Paranoia MCP re-check
- `gh pr create` + merge
- PROGRESS.md edit (mark Faz 2 B ✅, sıradaki Faz 2 G or Faz 3 C)
- Memory entry `project_faz2b3_agent_sdk_baseline.md` + MEMORY.md index
- `git checkout dev && git pull`

## Risks

- **`vector` extension missing on plan tier** — T0 verifies pre-flight. Supabase Free + Pro tiers include pgvector by default.
- **HNSW index build on empty table is instant** — no perf concern at migration time. First Faz 4 D bulk insert triggers incremental builds (HNSW supports online insert; v1 OK).
- **`coalesce(workspace_id::text, '')`** in unique index — Postgres lets this work but verify on Cloud (rare edge: expression indexes on nullable columns). B.1 has expression indexes; pattern proven.
- **`agent_memory.scope` invariant CHECK** may reject some legitimate edge cases. Manually test in T3:
  ```sql
  -- should succeed:
  insert into agent_memory (agent_name, scope, key) values ('test', 'global', 'k');
  -- should fail:
  insert into agent_memory (agent_name, scope, workspace_id, key) values ('test', 'global', gen_random_uuid(), 'k');
  ```
  T3 includes a smoke-check via `execute_sql` (with rollback).
- **Migration size:** ~300-350 SQL lines (4 tables, 16 indexes, 8 policies, 3 triggers, 1 extension). B.2 was 266 lines and applied atomically — B.3 should fit. If MCP rejects, split into b3a (DDL+ext) + b3b (policies+vector index).
- **`pgvector` HNSW availability:** requires pgvector 0.5+. Supabase Cloud has 0.7+. Pre-flight check covers.

## Verification gate

```
mcp__supabase__list_extensions() → vector installed
mcp__supabase__list_tables(["public"], true) → 13 tables, B.3's 4 with rls_enabled
mcp__supabase__get_advisors("security") → {"lints": []}
mcp__supabase__list_migrations() → b3_agent_sdk present
pg_policies count → agent_memory=3, agent_skills=1, embeddings=3, audit_log=1
pg_indexes → embeddings_vector_hnsw present, HNSW with m=16 ef=64
pnpm --filter @aeogen/web typecheck/lint/build → all exit 0
git log feature/B.3-agent-sdk-support → 1 commit with HEREDOC body
```

## Branch + commit suggestion

- Branch: `feature/B.3-agent-sdk-support` (already on it)
- Commit: see T6 message
- PR target: `dev`
- After merge → Faz 2 B ✅ complete milestone
