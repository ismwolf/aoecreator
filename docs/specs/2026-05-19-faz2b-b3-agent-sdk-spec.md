# Faz 2 B.3 — Agent SDK Support + pgvector Spec

Date: 2026-05-19
Phase: Faz 2 B (data layer) → sub-cycle B.3 (agent SDK + retrieval foundation) — **closes Faz 2 B**
Predecessors: B.1 ✅ (tenancy + RLS helpers), B.2 ✅ (5 domain tables + `private.user_workspace_ids()` + `private.is_org_admin()`)
Successors: Faz 2 G (provision-org-on-signup + invite flow), Faz 3 C (Agent Core SDK consumes agent_memory + agent_skills), Faz 4 D (crawl pipeline writes embeddings)

## Problem

B.1 ve B.2 tenancy + domain temelini kurdu. Şimdi Agent Core SDK (Faz 3 C) ve crawl pipeline (Faz 4 D) ihtiyacı olan 4 supporting tablo eksik:

- **`agent_memory`** — Faz 3 C agent runtime'ı için (global/workspace/agent scoped key-value memory + LRU stats)
- **`agent_skills`** — global skill registry (LangChain `langchain-master` skill cache pattern'ine analog)
- **`embeddings`** — pgvector tabanlı hybrid retrieval foundation (BGE-M3 1024-dim dense + sparse jsonb)
- **`audit_log`** — append-only org-level compliance/audit kaydı (org admin SELECT, service_role INSERT)

Plus: `pgvector` (vector) extension enable.

**B.3 alt-cycle'ı** Faz 2 B'yi kapatır — sonrasında veri katmanı agent dispatch için tamamen hazır.

## Goals

- 4 tablo + pgvector extension enable
- Schema decisions (locked 2026-05-19):
  1. `agent_memory.scope text + CHECK in ('global', 'workspace', 'agent')` (3-değerli enum)
     - `workspace_id NOT NULL` ⟺ `scope = 'workspace'`
     - `scope IN ('global', 'agent')` ⟹ `workspace_id IS NULL`
  2. `embeddings.embedding vector(1024)` + **HNSW cosine, m=16 ef_construction=64** (Supabase default, BGE-M3 production-ready)
  3. `audit_log`: `org_id NOT NULL` + `workspace_id NULL`'able + **append-only** (no INSERT/UPDATE/DELETE app-level policies; service_role only)
  4. `agent_skills`: **global registry**, no `workspace_id`. SELECT open to authenticated, mutations service_role only.
- Inherit B.1/B.2 patterns:
  - `extensions.uuid_generate_v4()` PK default
  - `moddatetime` trigger (only on non-append-only tables: agent_memory, agent_skills, embeddings)
  - Soft-delete (`deleted_at`) on mutable tables; NOT on audit_log
  - Partial indexes `where deleted_at is null` on soft-delete tables; plain indexes on audit_log
  - RLS: `TO authenticated`, `WITH CHECK` on writes
  - For workspace-scoped data: predicate `workspace_id in (select private.user_workspace_ids())`
  - For org-scoped (audit_log): predicate `private.is_org_admin(org_id)` (B.1 helper reused)
- Migration MCP `apply_migration` + lokal mirror (global rule)
- `database.types.ts` regenerate → 13 tables (B.1's 4 + B.2's 5 + B.3's 4)
- `get_advisors('security')` clean

## Non-Goals (deferred)

- **Agent runtime logic** (memory write, skill resolve, promotion) → Faz 3 C SDK
- **Embedding ingest pipeline** (Crawl4AI → BGE-M3 → embeddings INSERT) → Faz 4 D
- **Hybrid retrieval function** (`hybrid_search(workspace, query, k)` combining dense cosine + sparse BM25-like) → Faz 4 D / Faz 3 C
- **Sparse vector format spec** (jsonb shape: `{token_id: weight}` vs `{token: weight}`) → Faz 3 C SDK contract
- **Audit triggers** on B.1/B.2 mutations → Faz 6 F / Faz 7 H (manual `select audit_emit(...)` from app for now)
- **Provisioning + invite flow** → Faz 2 G
- **GDPR hard-purge** of soft-deleted rows + audit_log retention policy → Faz 7 H
- **`agent_memory` TTL eviction job** (Celery Beat) → Faz 3 C / Faz 7 H
- **`audit_log` partitioning by month** (large-table optimization) → v1.5 / Faz 7 H
- **Pytest BOLA integration test** → Faz 2 G (real auth.users)

## Approach

### 0. pgvector extension enable

```sql
create extension if not exists vector with schema extensions;
```

Idempotent. Supabase Cloud project zaten desteklerse no-op.

### 1. Schema

```sql
-- agent_memory
create table public.agent_memory (
  id            uuid        primary key default extensions.uuid_generate_v4(),
  agent_name    text        not null check (length(trim(agent_name)) between 1 and 80),
  scope         text        not null check (scope in ('global', 'workspace', 'agent')),
  workspace_id  uuid        references public.workspaces(id) on delete cascade,
  key           text        not null check (length(trim(key)) between 1 and 200),
  value         jsonb,
  cached_at     timestamptz not null default now(),
  expires_at    timestamptz,
  hit_count     integer     not null default 0 check (hit_count >= 0),
  promoted      boolean     not null default false,
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz,
  -- Scope ↔ workspace_id invariant (locked decision)
  constraint agent_memory_scope_workspace_ck check (
    (scope = 'workspace' and workspace_id is not null)
    or (scope in ('global', 'agent') and workspace_id is null)
  )
);
create unique index agent_memory_unique_key_active_uq
  on public.agent_memory (agent_name, scope, coalesce(workspace_id::text, ''), key)
  where deleted_at is null;

-- agent_skills (global registry — no workspace_id)
create table public.agent_skills (
  id            uuid        primary key default extensions.uuid_generate_v4(),
  agent_name    text        not null check (length(trim(agent_name)) between 1 and 80),
  skill_key     text        not null check (length(trim(skill_key)) between 1 and 120),
  content       text        not null check (length(content) between 1 and 65536),  -- 64KB max
  source        text        not null default 'builtin'
                            check (source in ('builtin', 'promoted', 'manual')),
  version       integer     not null default 1 check (version >= 1),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);
create unique index agent_skills_agent_key_version_active_uq
  on public.agent_skills (agent_name, skill_key, version) where deleted_at is null;

-- embeddings (pgvector hybrid retrieval foundation)
create table public.embeddings (
  id                uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid        not null references public.workspaces(id) on delete cascade,
  page_id           uuid        not null references public.pages(id) on delete cascade,
  chunk_id          integer     not null check (chunk_id >= 0),
  content           text        not null check (length(content) between 1 and 8192),  -- ~512 tokens
  embedding         extensions.vector(1024) not null,
  embedding_sparse  jsonb       not null default '{}'::jsonb,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz
);
create unique index embeddings_page_chunk_active_uq
  on public.embeddings (page_id, chunk_id) where deleted_at is null;

-- audit_log (append-only org-level compliance log)
create table public.audit_log (
  id            uuid        primary key default extensions.uuid_generate_v4(),
  org_id        uuid        not null references public.organizations(id) on delete cascade,
  workspace_id  uuid        references public.workspaces(id) on delete cascade,
  actor         uuid        references auth.users(id) on delete set null,  -- null = system
  action        text        not null check (length(trim(action)) between 1 and 80),
  resource      text        not null check (length(trim(resource)) between 1 and 200),
  metadata      jsonb       not null default '{}'::jsonb,
  ts            timestamptz not null default now()
  -- No updated_at / deleted_at — append-only
);
```

### 2. RLS policies

**agent_memory** (mixed scope):

```sql
alter table public.agent_memory enable row level security;

create policy "agent_memory_select" on public.agent_memory
  for select to authenticated
  using (
    deleted_at is null
    and (
      scope = 'global'
      or scope = 'agent'
      or (scope = 'workspace' and workspace_id in (select private.user_workspace_ids()))
    )
  );

create policy "agent_memory_insert_workspace" on public.agent_memory
  for insert to authenticated
  with check (
    scope = 'workspace'
    and workspace_id in (select private.user_workspace_ids())
  );

create policy "agent_memory_update_workspace" on public.agent_memory
  for update to authenticated
  using (
    scope = 'workspace'
    and workspace_id in (select private.user_workspace_ids())
    and deleted_at is null
  )
  with check (
    scope = 'workspace'
    and workspace_id in (select private.user_workspace_ids())
  );
-- Global/agent scope mutations: service_role only (RLS bypass)
```

**agent_skills** (global, read-open):

```sql
alter table public.agent_skills enable row level security;

create policy "agent_skills_select_all" on public.agent_skills
  for select to authenticated
  using (deleted_at is null);
-- INSERT/UPDATE/DELETE: service_role only (no app policy)
```

**embeddings** (workspace-scoped, B.2 pattern):

```sql
alter table public.embeddings enable row level security;

create policy "embeddings_select" on public.embeddings
  for select to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null);

create policy "embeddings_insert" on public.embeddings
  for insert to authenticated
  with check (workspace_id in (select private.user_workspace_ids()));

create policy "embeddings_update" on public.embeddings
  for update to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null)
  with check (workspace_id in (select private.user_workspace_ids()));
```

**audit_log** (append-only, org-admin SELECT):

```sql
alter table public.audit_log enable row level security;

create policy "audit_log_select_org_admin" on public.audit_log
  for select to authenticated
  using (private.is_org_admin(org_id));
-- NO INSERT/UPDATE/DELETE app-level policies — service_role bypass only
```

### 3. Indexes

```sql
-- agent_memory perf
create index agent_memory_agent_scope_idx on public.agent_memory(agent_name, scope) where deleted_at is null;
create index agent_memory_workspace_id_idx on public.agent_memory(workspace_id) where deleted_at is null and workspace_id is not null;
create index agent_memory_expires_at_idx on public.agent_memory(expires_at) where deleted_at is null and expires_at is not null;
create index agent_memory_promotion_idx on public.agent_memory(agent_name, hit_count desc) where deleted_at is null and promoted = false;

-- agent_skills perf
create index agent_skills_agent_key_idx on public.agent_skills(agent_name, skill_key) where deleted_at is null;

-- embeddings perf + HNSW vector
create index embeddings_workspace_id_idx on public.embeddings(workspace_id) where deleted_at is null;
create index embeddings_page_id_idx on public.embeddings(page_id) where deleted_at is null;
create index embeddings_vector_hnsw on public.embeddings
  using hnsw (embedding extensions.vector_cosine_ops)
  with (m = 16, ef_construction = 64);
-- Sparse GIN: deferred until first query pattern (Faz 4 D)

-- audit_log perf (plain, not partial — no soft-delete)
create index audit_log_org_ts_idx on public.audit_log(org_id, ts desc);
create index audit_log_workspace_ts_idx on public.audit_log(workspace_id, ts desc) where workspace_id is not null;
create index audit_log_actor_idx on public.audit_log(actor) where actor is not null;
create index audit_log_action_idx on public.audit_log(action);
```

### 4. moddatetime triggers (3 of 4 — audit_log skipped)

```sql
create trigger handle_updated_at before update on public.agent_memory
  for each row execute function extensions.moddatetime(updated_at);
create trigger handle_updated_at before update on public.agent_skills
  for each row execute function extensions.moddatetime(updated_at);
create trigger handle_updated_at before update on public.embeddings
  for each row execute function extensions.moddatetime(updated_at);
-- audit_log: no trigger (append-only, no updated_at column)
```

### 5. Migration delivery

- Tek SQL dosyası `supabase/migrations/20260519010000_b3_agent_sdk.sql` (B.2'den 1 saat sonra UTC timestamp)
- MCP `apply_migration(name="b3_agent_sdk", query=...)`
- Local mirror (global rule)
- `database.types.ts` MCP regenerate → 13 tables
- `get_advisors('security')` boş

## Risks

- **pgvector extension version uyumsuzluğu:** Supabase Cloud zaten pgvector 0.7+ destekler (`vector(1024)` ve HNSW available). Eğer Cloud projesi eski plan'daysa version check gerekebilir. Mitigation: `list_extensions` ile check edilir (T1 öncesi).
- **HNSW build time** ilk insert sırasında küçük, ama embeddings dolduğunda (Faz 4 D'den sonra) reindex maliyetli olabilir. v1'de 10K-100K row beklenir; HNSW m=16 yeterli. v1.5'te 1M+ olursa parametrik tuning.
- **`agent_memory.unique` partial index** `coalesce(workspace_id::text, '')` kullanıyor çünkü NULL'lar Postgres'te unique constraint için "distinct" sayılır. `coalesce` ile workspace-null rows da unique key'e dahil olur. Doğru.
- **`agent_memory.scope` invariant CHECK** workspace=null when scope='global' or 'agent'; not null when scope='workspace'. Migration sonrası test: insert scope='workspace' workspace_id=null → fail. Insert scope='global' workspace_id=<some> → fail.
- **audit_log RLS:** `private.is_org_admin(org_id)` — B.1'de tanımlı SECURITY DEFINER stable function. NULL org_id imkansız (NOT NULL constraint). Function STABLE olduğu için her satırda eşit org_id için cache'lenir; performant.
- **audit_log append-only çiğnenirse:** Bir geliştirici yanlışlıkla SQL `update audit_log ...` yazarsa service_role ile bu çalışır. Mitigation: prod'da bir geri-dönüş kuralı/policy ileride eklenebilir (`for update to public using (false)` deny-all). v1'de değerlendirme + service_role discipline.
- **`embeddings.embedding_sparse jsonb`** default `'{}'` boş object. Ingest pipeline (Faz 4 D) BGE-M3 sparse çıktısını `{token_id_as_string: weight}` formatında dolduracak. GIN index eklenmesi Faz 4 D'de (sparse retrieval query pattern netleştiğinde).
- **`embeddings.workspace_id` denormalize tutarlılık:** B.2'deki gibi app-level discipline (page'in workspace_id'siyle eşit olmalı). v1.5'te trigger.
- **`audit_log` row volume:** her major mutation 1 row → workspace başına saatte ~50 row olabilir, aylık ~36K. 100 workspace × 36K = 3.6M/ay. Aylık partitioning Faz 7 H'da gerekirse.

## Open questions

1. **`agent_memory.value` boyut limiti:** jsonb maks ~1GB Postgres limit, ama pratik LangChain memory entry ~10KB. CHECK `pg_column_size(value) < 65536` eklemek? **Karar:** v1'de constraint yok, app discipline (langchain-master skill memory pattern: ≤30KB). v1.5'te ölçüldüğünde eklenir.
2. **`audit_log.action` enum mu yoksa free-form text mı?** Şu an `length 1..80` free-form CHECK. v1.5'te common action'lar listelenince ENUM-like CHECK constraint eklenebilir (örn `('create', 'update', 'delete', 'invite', 'kick', ...)`). v1: free-form.
3. **`audit_log.resource` shape:** `'<type>:<id>'` convention (örn `'workspace:abc-123'`). v1: free-form, app discipline.
4. **Promoted skills auto-cleanup:** memory hit≥3 → skills'e promote, promoted=true, memory expires_at set. v1: SDK'da implement. B.3 sadece kolonu açar.
5. **Service_role secret rotation impact:** audit_log INSERT'lerini service_role yaptığı için key rotation günlük workflow'u etkiler. v1.5 ops runbook (Faz 7 H).

---

## Acceptance criteria

- [ ] `mcp__supabase__list_tables(["public"], verbose=true)` → toplam 13 tablo (B.1: 4 + B.2: 5 + B.3: 4)
- [ ] B.3'ün 4 tablosu `rls_enabled = true`
- [ ] `agent_memory`: 3 policy (SELECT + INSERT-workspace + UPDATE-workspace)
- [ ] `agent_skills`: 1 policy (SELECT to authenticated)
- [ ] `embeddings`: 3 policy (SELECT + INSERT + UPDATE)
- [ ] `audit_log`: 1 policy (SELECT to org admin)
- [ ] `pgvector` extension installed (`list_extensions` returns `vector` with `installed_version != null`)
- [ ] HNSW index `embeddings_vector_hnsw` present (`pg_indexes` sorgusu)
- [ ] `get_advisors('security')` lints array empty
- [ ] `database.types.ts` regenerated, 13 tables
- [ ] `pnpm --filter @aeogen/web typecheck` + `lint` + `build` passes
- [ ] Local migration mirror `supabase/migrations/20260519010000_b3_agent_sdk.sql` content matches MCP-applied
- [ ] PR opened `feature/B.3-agent-sdk-support` → `dev`, code-reviewer PASS, merged
- [ ] PROGRESS.md updated → Faz 2 B ✅ complete (all 3 sub-cycles done)
- [ ] Memory entry written + MEMORY.md index updated
