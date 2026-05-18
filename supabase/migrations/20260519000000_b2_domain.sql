-- Faz 2 B.2 — Domain entities
-- Spec: docs/specs/2026-05-19-faz2b-b2-domain-spec.md
-- Plan: docs/plans/2026-05-19-faz2b-b2-domain-plan.md
-- 5 tables: sites, pages, analysis_runs, agent_executions, scores
-- workspace_id denormalized on every table for RLS perf (uses private.user_workspace_ids() from B.1).
-- Soft-delete, moddatetime triggers, partial unique + perf indexes, RLS with WITH CHECK.

-- ────────────────────────────────────────────────────────────────────
-- 0. Extensions (idempotent — B.1 already installed moddatetime)
-- ────────────────────────────────────────────────────────────────────

create extension if not exists moddatetime with schema extensions;

-- ────────────────────────────────────────────────────────────────────
-- 1. Tables
-- ────────────────────────────────────────────────────────────────────

-- sites: client websites under a workspace
create table public.sites (
  id                uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid        not null references public.workspaces(id) on delete cascade,
  url               text        not null check (length(trim(url)) between 1 and 2048 and url ~ '^https?://'),
  default_language  text        not null default 'tr' check (length(default_language) = 2),
  sector            text        check (sector is null or length(trim(sector)) between 1 and 80),
  last_crawled_at   timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz
);

comment on table public.sites is
  'Client websites under a workspace. URL is unique per workspace among active (non-soft-deleted) rows.';

-- pages: crawled pages under a site
create table public.pages (
  id                uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid        not null references public.workspaces(id) on delete cascade,
  site_id           uuid        not null references public.sites(id) on delete cascade,
  url               text        not null check (length(trim(url)) between 1 and 2048 and url ~ '^https?://'),
  html_path         text        check (html_path is null or length(trim(html_path)) between 1 and 512),
  parsed_content    jsonb,
  content_hash      text        check (content_hash is null or content_hash ~ '^[a-f0-9]{64}$'),
  last_crawled_at   timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz
);

comment on table public.pages is
  'Crawled pages under a site. workspace_id denormalized for RLS performance. content_hash is sha256 hex (64 chars).';

-- analysis_runs: a single AEO/GEO analysis pass over a site
create table public.analysis_runs (
  id                uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid        not null references public.workspaces(id) on delete cascade,
  site_id           uuid        not null references public.sites(id) on delete cascade,
  status            text        not null default 'queued'
                                check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled')),
  kicked_by         uuid        references auth.users(id) on delete set null,
  started_at        timestamptz,
  finished_at       timestamptz,
  total_cost_usd    numeric(10, 4) not null default 0 check (total_cost_usd >= 0),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz
);

comment on table public.analysis_runs is
  'One AEO/GEO analysis pass over a site. kicked_by SET NULL keeps historical runs after user deletion.';

-- agent_executions: per-agent execution log within a run
create table public.agent_executions (
  id                uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid        not null references public.workspaces(id) on delete cascade,
  run_id            uuid        not null references public.analysis_runs(id) on delete cascade,
  agent_name        text        not null check (length(trim(agent_name)) between 1 and 80),
  technique_id      smallint    not null check (technique_id between 1 and 12),
  status            text        not null default 'queued'
                                check (status in ('queued', 'running', 'succeeded', 'failed', 'cancelled', 'skipped')),
  input             jsonb,
  output            jsonb,
  score             numeric(5, 2) check (score is null or (score >= 0 and score <= 100)),
  llm_cost          numeric(10, 6) not null default 0 check (llm_cost >= 0),
  duration_ms       integer     check (duration_ms is null or duration_ms >= 0),
  trace_id          text        check (trace_id is null or length(trim(trace_id)) between 1 and 128),
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz
);

comment on table public.agent_executions is
  'Per-agent execution log within an analysis run. score normalized 0-100; raw per-technique score lives in output jsonb.';

-- scores: per-page per-technique score for a run
create table public.scores (
  id                uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid        not null references public.workspaces(id) on delete cascade,
  page_id           uuid        not null references public.pages(id) on delete cascade,
  run_id            uuid        not null references public.analysis_runs(id) on delete cascade,
  technique_id      smallint    not null check (technique_id between 1 and 12),
  score             numeric(5, 2) not null check (score >= 0 and score <= 100),
  prev_score        numeric(5, 2) check (prev_score is null or (prev_score >= 0 and prev_score <= 100)),
  recommendations   jsonb,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz
);

comment on table public.scores is
  'Per-page per-technique score for a given run. Unique (page_id, technique_id, run_id) among active rows.';

-- ────────────────────────────────────────────────────────────────────
-- 2. Indexes
-- ────────────────────────────────────────────────────────────────────

-- 2a. Unique partial indexes (soft-delete aware)
create unique index sites_workspace_url_active_uq
  on public.sites (workspace_id, url) where deleted_at is null;

create unique index pages_site_url_active_uq
  on public.pages (site_id, url) where deleted_at is null;

create unique index scores_page_technique_run_active_uq
  on public.scores (page_id, technique_id, run_id) where deleted_at is null;

-- 2b. Performance partial indexes (RLS hot path + FK + status filters)
create index sites_workspace_id_idx
  on public.sites(workspace_id) where deleted_at is null;

create index pages_workspace_id_idx
  on public.pages(workspace_id) where deleted_at is null;

create index pages_site_id_idx
  on public.pages(site_id) where deleted_at is null;

create index analysis_runs_workspace_id_idx
  on public.analysis_runs(workspace_id) where deleted_at is null;

create index analysis_runs_site_id_idx
  on public.analysis_runs(site_id) where deleted_at is null;

create index analysis_runs_status_idx
  on public.analysis_runs(status) where deleted_at is null and status in ('queued', 'running');

create index agent_executions_workspace_id_idx
  on public.agent_executions(workspace_id) where deleted_at is null;

create index agent_executions_run_id_idx
  on public.agent_executions(run_id) where deleted_at is null;

create index agent_executions_status_idx
  on public.agent_executions(status) where deleted_at is null and status in ('queued', 'running');

create index scores_workspace_id_idx
  on public.scores(workspace_id) where deleted_at is null;

create index scores_page_id_idx
  on public.scores(page_id) where deleted_at is null;

create index scores_run_id_idx
  on public.scores(run_id) where deleted_at is null;

-- ────────────────────────────────────────────────────────────────────
-- 3. Enable RLS
-- ────────────────────────────────────────────────────────────────────

alter table public.sites             enable row level security;
alter table public.pages             enable row level security;
alter table public.analysis_runs     enable row level security;
alter table public.agent_executions  enable row level security;
alter table public.scores            enable row level security;

-- ────────────────────────────────────────────────────────────────────
-- 4. RLS policies — 3 per table (SELECT / INSERT / UPDATE)
--    DELETE is app-level soft-delete (UPDATE deleted_at = now()); no DELETE policy.
--    Predicate: workspace_id in (select private.user_workspace_ids()) — B.1 helper.
-- ────────────────────────────────────────────────────────────────────

-- sites
create policy "sites_select" on public.sites
  for select to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null);

create policy "sites_insert" on public.sites
  for insert to authenticated
  with check (workspace_id in (select private.user_workspace_ids()));

create policy "sites_update" on public.sites
  for update to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null)
  with check (workspace_id in (select private.user_workspace_ids()));

-- pages
create policy "pages_select" on public.pages
  for select to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null);

create policy "pages_insert" on public.pages
  for insert to authenticated
  with check (workspace_id in (select private.user_workspace_ids()));

create policy "pages_update" on public.pages
  for update to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null)
  with check (workspace_id in (select private.user_workspace_ids()));

-- analysis_runs
create policy "analysis_runs_select" on public.analysis_runs
  for select to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null);

create policy "analysis_runs_insert" on public.analysis_runs
  for insert to authenticated
  with check (workspace_id in (select private.user_workspace_ids()));

create policy "analysis_runs_update" on public.analysis_runs
  for update to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null)
  with check (workspace_id in (select private.user_workspace_ids()));

-- agent_executions
create policy "agent_executions_select" on public.agent_executions
  for select to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null);

create policy "agent_executions_insert" on public.agent_executions
  for insert to authenticated
  with check (workspace_id in (select private.user_workspace_ids()));

create policy "agent_executions_update" on public.agent_executions
  for update to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null)
  with check (workspace_id in (select private.user_workspace_ids()));

-- scores
create policy "scores_select" on public.scores
  for select to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null);

create policy "scores_insert" on public.scores
  for insert to authenticated
  with check (workspace_id in (select private.user_workspace_ids()));

create policy "scores_update" on public.scores
  for update to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null)
  with check (workspace_id in (select private.user_workspace_ids()));

-- ────────────────────────────────────────────────────────────────────
-- 5. moddatetime triggers — bump updated_at on every UPDATE
-- ────────────────────────────────────────────────────────────────────

create trigger handle_updated_at before update on public.sites
  for each row execute function extensions.moddatetime(updated_at);

create trigger handle_updated_at before update on public.pages
  for each row execute function extensions.moddatetime(updated_at);

create trigger handle_updated_at before update on public.analysis_runs
  for each row execute function extensions.moddatetime(updated_at);

create trigger handle_updated_at before update on public.agent_executions
  for each row execute function extensions.moddatetime(updated_at);

create trigger handle_updated_at before update on public.scores
  for each row execute function extensions.moddatetime(updated_at);
