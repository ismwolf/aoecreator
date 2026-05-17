-- Faz 2 B.1 — Tenancy + RLS foundation
-- Spec: docs/specs/2026-05-17-faz2b-b1-tenancy-spec.md
-- Plan: docs/plans/2026-05-17-faz2b-b1-tenancy-plan.md
-- 4 tables: organizations, org_members, workspaces, workspace_members
-- Soft-delete, moddatetime triggers, SECURITY DEFINER RLS helpers, full RLS.

-- ────────────────────────────────────────────────────────────────────
-- 0. Extensions
-- ────────────────────────────────────────────────────────────────────

create extension if not exists moddatetime with schema extensions;

-- ────────────────────────────────────────────────────────────────────
-- 1. Tables
-- ────────────────────────────────────────────────────────────────────

create table public.organizations (
  id          uuid        primary key default extensions.uuid_generate_v4(),
  name        text        not null check (length(trim(name)) between 1 and 120),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  deleted_at  timestamptz
);

comment on table public.organizations is
  'Agency tenant root. One org = one agency. Users belong to a single org via app_metadata.org_id JWT claim.';

create table public.org_members (
  id          uuid        primary key default extensions.uuid_generate_v4(),
  org_id      uuid        not null references public.organizations(id) on delete cascade,
  user_id     uuid        not null references auth.users(id) on delete cascade,
  role        text        not null check (role in ('owner', 'admin', 'member')),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  deleted_at  timestamptz
);

create unique index org_members_org_user_active_uq
  on public.org_members (org_id, user_id) where deleted_at is null;

comment on table public.org_members is
  'Many-to-many user↔org with role. Soft-delete + partial unique index permits leave/rejoin.';

create table public.workspaces (
  id          uuid        primary key default extensions.uuid_generate_v4(),
  org_id      uuid        not null references public.organizations(id) on delete cascade,
  name        text        not null check (length(trim(name)) between 1 and 120),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  deleted_at  timestamptz
);

comment on table public.workspaces is
  'Per-client container inside an org. All domain tables (B.2: sites, pages, runs; B.3: agent_memory, embeddings, audit_log) FK on this.';

create table public.workspace_members (
  id            uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id  uuid        not null references public.workspaces(id) on delete cascade,
  user_id       uuid        not null references auth.users(id) on delete cascade,
  role          text        not null check (role in ('admin', 'member', 'viewer')),
  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),
  deleted_at    timestamptz
);

create unique index workspace_members_ws_user_active_uq
  on public.workspace_members (workspace_id, user_id) where deleted_at is null;

comment on table public.workspace_members is
  'Many-to-many user↔workspace with role. Viewer is read-only. Org owner/admin implicitly has access to all workspaces in the org (RLS).';

-- ────────────────────────────────────────────────────────────────────
-- 2. SECURITY DEFINER helper functions (canonical RLS predicates)
-- ────────────────────────────────────────────────────────────────────

-- Returns current user's active workspace memberships.
-- Used by every domain-table RLS policy: `using (workspace_id in (select public.user_workspace_ids()))`.
create or replace function public.user_workspace_ids()
returns setof uuid
language sql
security definer
stable
set search_path = public
as $$
  select workspace_id
  from public.workspace_members
  where user_id = (select auth.uid())
    and deleted_at is null
$$;
revoke all on function public.user_workspace_ids() from public, anon;
grant execute on function public.user_workspace_ids() to authenticated;

-- Returns JWT-claimed org_id (single org per user).
-- Provisioning Edge Function (Faz 2 G) sets app_metadata.org_id on signup.
-- NULL during boot (no claim) → RLS denies all rows (intended).
create or replace function public.current_org_id()
returns uuid
language sql
stable
as $$
  select nullif((select auth.jwt()) -> 'app_metadata' ->> 'org_id', '')::uuid
$$;

-- Returns true if current user is owner or admin of target org.
-- SECURITY DEFINER bypasses org_members RLS (otherwise recursion).
create or replace function public.is_org_admin(target_org_id uuid)
returns boolean
language sql
security definer
stable
set search_path = public
as $$
  select exists (
    select 1 from public.org_members
    where org_id = target_org_id
      and user_id = (select auth.uid())
      and role in ('owner', 'admin')
      and deleted_at is null
  )
$$;
revoke all on function public.is_org_admin(uuid) from public, anon;
grant execute on function public.is_org_admin(uuid) to authenticated;

-- ────────────────────────────────────────────────────────────────────
-- 3. Enable RLS (deny-all default)
-- ────────────────────────────────────────────────────────────────────

alter table public.organizations      enable row level security;
alter table public.org_members        enable row level security;
alter table public.workspaces         enable row level security;
alter table public.workspace_members  enable row level security;

-- ────────────────────────────────────────────────────────────────────
-- 4. Policies — organizations
-- ────────────────────────────────────────────────────────────────────

create policy "organizations_select"
  on public.organizations for select
  to authenticated
  using (id = public.current_org_id() and deleted_at is null);

-- INSERT denied to authenticated; org creation only via service_role (Faz 2 G Edge Function).
create policy "organizations_insert_denied"
  on public.organizations for insert
  to authenticated
  with check (false);

create policy "organizations_update"
  on public.organizations for update
  to authenticated
  using (id = public.current_org_id() and deleted_at is null and public.is_org_admin(id))
  with check (id = public.current_org_id() and public.is_org_admin(id));

-- Hard DELETE denied; soft-delete via UPDATE deleted_at = now().
create policy "organizations_delete_denied"
  on public.organizations for delete
  to authenticated
  using (false);

-- ────────────────────────────────────────────────────────────────────
-- 5. Policies — org_members
-- ────────────────────────────────────────────────────────────────────

create policy "org_members_select"
  on public.org_members for select
  to authenticated
  using (org_id = public.current_org_id() and deleted_at is null);

create policy "org_members_insert"
  on public.org_members for insert
  to authenticated
  with check (org_id = public.current_org_id() and public.is_org_admin(org_id));

create policy "org_members_update"
  on public.org_members for update
  to authenticated
  using (org_id = public.current_org_id() and public.is_org_admin(org_id))
  with check (org_id = public.current_org_id() and public.is_org_admin(org_id));

create policy "org_members_delete_denied"
  on public.org_members for delete
  to authenticated
  using (false);

-- ────────────────────────────────────────────────────────────────────
-- 6. Policies — workspaces
-- ────────────────────────────────────────────────────────────────────

create policy "workspaces_select"
  on public.workspaces for select
  to authenticated
  using (
    org_id = public.current_org_id()
    and deleted_at is null
    and (
      id in (select public.user_workspace_ids())
      or public.is_org_admin(org_id)
    )
  );

create policy "workspaces_insert"
  on public.workspaces for insert
  to authenticated
  with check (org_id = public.current_org_id() and public.is_org_admin(org_id));

create policy "workspaces_update"
  on public.workspaces for update
  to authenticated
  using (
    org_id = public.current_org_id()
    and deleted_at is null
    and public.is_org_admin(org_id)
  )
  with check (org_id = public.current_org_id() and public.is_org_admin(org_id));

create policy "workspaces_delete_denied"
  on public.workspaces for delete
  to authenticated
  using (false);

-- ────────────────────────────────────────────────────────────────────
-- 7. Policies — workspace_members
-- ────────────────────────────────────────────────────────────────────

create policy "workspace_members_select"
  on public.workspace_members for select
  to authenticated
  using (
    workspace_id in (select public.user_workspace_ids())
    and deleted_at is null
  );

create policy "workspace_members_insert"
  on public.workspace_members for insert
  to authenticated
  with check (
    public.is_org_admin(
      (select org_id from public.workspaces where id = workspace_id and deleted_at is null)
    )
  );

create policy "workspace_members_update"
  on public.workspace_members for update
  to authenticated
  using (
    public.is_org_admin(
      (select org_id from public.workspaces where id = workspace_id and deleted_at is null)
    )
  )
  with check (
    public.is_org_admin(
      (select org_id from public.workspaces where id = workspace_id and deleted_at is null)
    )
  );

create policy "workspace_members_delete_denied"
  on public.workspace_members for delete
  to authenticated
  using (false);

-- ────────────────────────────────────────────────────────────────────
-- 8. Indexes — every FK + RLS-referenced column, partial on deleted_at
-- ────────────────────────────────────────────────────────────────────

create index org_members_user_id_active_idx
  on public.org_members (user_id) where deleted_at is null;

create index org_members_org_id_active_idx
  on public.org_members (org_id) where deleted_at is null;

create index workspaces_org_id_active_idx
  on public.workspaces (org_id) where deleted_at is null;

create index workspace_members_user_id_active_idx
  on public.workspace_members (user_id) where deleted_at is null;

create index workspace_members_workspace_id_active_idx
  on public.workspace_members (workspace_id) where deleted_at is null;

-- ────────────────────────────────────────────────────────────────────
-- 9. moddatetime triggers — auto-bump updated_at on UPDATE
-- ────────────────────────────────────────────────────────────────────

create trigger organizations_set_updated_at
  before update on public.organizations
  for each row execute function extensions.moddatetime(updated_at);

create trigger org_members_set_updated_at
  before update on public.org_members
  for each row execute function extensions.moddatetime(updated_at);

create trigger workspaces_set_updated_at
  before update on public.workspaces
  for each row execute function extensions.moddatetime(updated_at);

create trigger workspace_members_set_updated_at
  before update on public.workspace_members
  for each row execute function extensions.moddatetime(updated_at);
