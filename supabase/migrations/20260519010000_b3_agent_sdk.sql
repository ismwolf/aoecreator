-- Faz 2 B.3 — Agent SDK Support + pgvector
-- Spec:  docs/specs/2026-05-19-faz2b-b3-agent-sdk-spec.md
-- Plan:  docs/plans/2026-05-19-faz2b-b3-agent-sdk-plan.md
--
-- Adds 4 tables (agent_memory, agent_skills, embeddings, audit_log) plus
-- the pgvector extension. Closes Faz 2 B (B.1 + B.2 + B.3).
--
-- Inherits B.1/B.2 patterns:
--   * extensions.uuid_generate_v4() PK default
--   * moddatetime trigger on mutable tables (skipped on audit_log)
--   * Soft-delete (deleted_at) on mutable tables (skipped on audit_log)
--   * RLS TO authenticated + WITH CHECK on writes
--   * Workspace-scoped: workspace_id in (select private.user_workspace_ids())
--   * Org-scoped:       private.is_org_admin(org_id)

-- ============================================================================
-- 0. Extensions
-- ============================================================================

create extension if not exists vector with schema extensions;

-- ============================================================================
-- 1. Tables
-- ============================================================================

-- agent_memory: 3-scope (global/workspace/agent) key-value with LRU stats.
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
  -- Scope ↔ workspace_id invariant
  constraint agent_memory_scope_workspace_ck check (
    (scope = 'workspace' and workspace_id is not null)
    or (scope in ('global', 'agent') and workspace_id is null)
  )
);

-- agent_skills: global registry — no workspace_id.
create table public.agent_skills (
  id            uuid        primary key default extensions.uuid_generate_v4(),
  agent_name    text        not null check (length(trim(agent_name)) between 1 and 80),
  skill_key     text        not null check (length(trim(skill_key)) between 1 and 120),
  content       text        not null check (length(content) between 1 and 65536),
  source        text        not null default 'builtin'
                            check (source in ('builtin', 'promoted', 'manual')),
  version       integer     not null default 1 check (version >= 1),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);

-- embeddings: BGE-M3 1024-dim dense + sparse jsonb (hybrid retrieval foundation).
create table public.embeddings (
  id                uuid                       primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid                       not null references public.workspaces(id) on delete cascade,
  page_id           uuid                       not null references public.pages(id) on delete cascade,
  chunk_id          integer                    not null check (chunk_id >= 0),
  content           text                       not null check (length(content) between 1 and 8192),
  embedding         extensions.vector(1024)    not null,
  embedding_sparse  jsonb                      not null default '{}'::jsonb,
  created_at        timestamptz                not null default now(),
  updated_at        timestamptz                not null default now(),
  deleted_at        timestamptz
);

-- audit_log: append-only org-level compliance log (no updated_at / deleted_at).
create table public.audit_log (
  id            uuid        primary key default extensions.uuid_generate_v4(),
  org_id        uuid        not null references public.organizations(id) on delete cascade,
  workspace_id  uuid        references public.workspaces(id) on delete cascade,
  actor         uuid        references auth.users(id) on delete set null,
  action        text        not null check (length(trim(action)) between 1 and 80),
  resource      text        not null check (length(trim(resource)) between 1 and 200),
  metadata      jsonb       not null default '{}'::jsonb,
  ts            timestamptz not null default now()
);

-- ============================================================================
-- 2. Unique partial indexes (3)
-- ============================================================================

-- agent_memory: unique (agent, scope, workspace_or_empty, key) for live rows.
-- coalesce keeps null workspaces in the unique-key space (Postgres treats NULLs
-- as distinct otherwise).
create unique index agent_memory_unique_key_active_uq
  on public.agent_memory (agent_name, scope, coalesce(workspace_id::text, ''), key)
  where deleted_at is null;

create unique index agent_skills_agent_key_version_active_uq
  on public.agent_skills (agent_name, skill_key, version)
  where deleted_at is null;

create unique index embeddings_page_chunk_active_uq
  on public.embeddings (page_id, chunk_id)
  where deleted_at is null;

-- ============================================================================
-- 3. Performance indexes (10)
-- ============================================================================

-- agent_memory (4)
create index agent_memory_agent_scope_idx
  on public.agent_memory(agent_name, scope)
  where deleted_at is null;

create index agent_memory_workspace_id_idx
  on public.agent_memory(workspace_id)
  where deleted_at is null and workspace_id is not null;

create index agent_memory_expires_at_idx
  on public.agent_memory(expires_at)
  where deleted_at is null and expires_at is not null;

create index agent_memory_promotion_idx
  on public.agent_memory(agent_name, hit_count desc)
  where deleted_at is null and promoted = false;

-- agent_skills (1)
create index agent_skills_agent_key_idx
  on public.agent_skills(agent_name, skill_key)
  where deleted_at is null;

-- embeddings (2 perf + 1 HNSW below)
create index embeddings_workspace_id_idx
  on public.embeddings(workspace_id)
  where deleted_at is null;

create index embeddings_page_id_idx
  on public.embeddings(page_id)
  where deleted_at is null;

-- audit_log (4 plain — no soft-delete column)
create index audit_log_org_ts_idx
  on public.audit_log(org_id, ts desc);

create index audit_log_workspace_ts_idx
  on public.audit_log(workspace_id, ts desc)
  where workspace_id is not null;

create index audit_log_actor_idx
  on public.audit_log(actor)
  where actor is not null;

create index audit_log_action_idx
  on public.audit_log(action);

-- ============================================================================
-- 4. HNSW vector index (1)
-- ============================================================================

create index embeddings_vector_hnsw
  on public.embeddings
  using hnsw (embedding extensions.vector_cosine_ops)
  with (m = 16, ef_construction = 64);

-- ============================================================================
-- 5. Enable RLS
-- ============================================================================

alter table public.agent_memory enable row level security;
alter table public.agent_skills enable row level security;
alter table public.embeddings   enable row level security;
alter table public.audit_log    enable row level security;

-- ============================================================================
-- 6. RLS policies (8 total)
-- ============================================================================

-- agent_memory (3): mixed scope reads; workspace-scoped writes only via app.
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
-- Global/agent scope mutations: service_role only (RLS bypass).

-- agent_skills (1): global read-open; mutations service_role only.
create policy "agent_skills_select_all" on public.agent_skills
  for select to authenticated
  using (deleted_at is null);

-- embeddings (3): B.2 pattern, workspace-scoped.
create policy "embeddings_select" on public.embeddings
  for select to authenticated
  using (
    workspace_id in (select private.user_workspace_ids())
    and deleted_at is null
  );

create policy "embeddings_insert" on public.embeddings
  for insert to authenticated
  with check (workspace_id in (select private.user_workspace_ids()));

create policy "embeddings_update" on public.embeddings
  for update to authenticated
  using (
    workspace_id in (select private.user_workspace_ids())
    and deleted_at is null
  )
  with check (workspace_id in (select private.user_workspace_ids()));

-- audit_log (1): org-admin SELECT; append-only via service_role.
create policy "audit_log_select_org_admin" on public.audit_log
  for select to authenticated
  using (private.is_org_admin(org_id));
-- NO INSERT/UPDATE/DELETE app-level policies — service_role bypass only.

-- ============================================================================
-- 7. moddatetime triggers (3 of 4 — audit_log excluded, append-only)
-- ============================================================================

create trigger handle_updated_at before update on public.agent_memory
  for each row execute function extensions.moddatetime(updated_at);

create trigger handle_updated_at before update on public.agent_skills
  for each row execute function extensions.moddatetime(updated_at);

create trigger handle_updated_at before update on public.embeddings
  for each row execute function extensions.moddatetime(updated_at);
