-- Faz 2 B.1 — Security hardening follow-up
-- Addresses 3 supabase_advisor WARN findings from migration 20260517030213_b1_tenancy:
--   1. function_search_path_mutable on public.current_org_id (no search_path set)
--   2. authenticated_security_definer_function_executable on public.is_org_admin
--   3. authenticated_security_definer_function_executable on public.user_workspace_ids
-- Fix: move helpers to `private` schema (not in PostgREST exposed schemas list),
-- so REST `/rpc/` exposure is removed but RLS can still call them via schema-qualified name.

-- ────────────────────────────────────────────────────────────────────
-- 1. Create private schema (NOT exposed by PostgREST)
-- ────────────────────────────────────────────────────────────────────

create schema if not exists private;
grant usage on schema private to authenticated;

-- ────────────────────────────────────────────────────────────────────
-- 2. Re-create helpers in private schema (with explicit search_path)
-- ────────────────────────────────────────────────────────────────────

create or replace function private.user_workspace_ids()
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
revoke all on function private.user_workspace_ids() from public, anon;
grant execute on function private.user_workspace_ids() to authenticated;

create or replace function private.current_org_id()
returns uuid
language sql
stable
set search_path = public
as $$
  select nullif((select auth.jwt()) -> 'app_metadata' ->> 'org_id', '')::uuid
$$;
revoke all on function private.current_org_id() from public, anon;
grant execute on function private.current_org_id() to authenticated;

create or replace function private.is_org_admin(target_org_id uuid)
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
revoke all on function private.is_org_admin(uuid) from public, anon;
grant execute on function private.is_org_admin(uuid) to authenticated;

-- ────────────────────────────────────────────────────────────────────
-- 3. Drop old public-schema helpers
--    (CASCADE drops dependent policies; we re-create them below)
-- ────────────────────────────────────────────────────────────────────

drop function public.is_org_admin(uuid) cascade;
drop function public.user_workspace_ids() cascade;
drop function public.current_org_id() cascade;

-- ────────────────────────────────────────────────────────────────────
-- 4. Re-create all policies using private.* references
-- ────────────────────────────────────────────────────────────────────

-- organizations
create policy "organizations_select" on public.organizations for select to authenticated
  using (id = private.current_org_id() and deleted_at is null);
create policy "organizations_insert_denied" on public.organizations for insert to authenticated
  with check (false);
create policy "organizations_update" on public.organizations for update to authenticated
  using (id = private.current_org_id() and deleted_at is null and private.is_org_admin(id))
  with check (id = private.current_org_id() and private.is_org_admin(id));
create policy "organizations_delete_denied" on public.organizations for delete to authenticated
  using (false);

-- org_members
create policy "org_members_select" on public.org_members for select to authenticated
  using (org_id = private.current_org_id() and deleted_at is null);
create policy "org_members_insert" on public.org_members for insert to authenticated
  with check (org_id = private.current_org_id() and private.is_org_admin(org_id));
create policy "org_members_update" on public.org_members for update to authenticated
  using (org_id = private.current_org_id() and private.is_org_admin(org_id))
  with check (org_id = private.current_org_id() and private.is_org_admin(org_id));
create policy "org_members_delete_denied" on public.org_members for delete to authenticated
  using (false);

-- workspaces
create policy "workspaces_select" on public.workspaces for select to authenticated
  using (
    org_id = private.current_org_id() and deleted_at is null
    and (id in (select private.user_workspace_ids()) or private.is_org_admin(org_id))
  );
create policy "workspaces_insert" on public.workspaces for insert to authenticated
  with check (org_id = private.current_org_id() and private.is_org_admin(org_id));
create policy "workspaces_update" on public.workspaces for update to authenticated
  using (org_id = private.current_org_id() and deleted_at is null and private.is_org_admin(org_id))
  with check (org_id = private.current_org_id() and private.is_org_admin(org_id));
create policy "workspaces_delete_denied" on public.workspaces for delete to authenticated
  using (false);

-- workspace_members
create policy "workspace_members_select" on public.workspace_members for select to authenticated
  using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null);
create policy "workspace_members_insert" on public.workspace_members for insert to authenticated
  with check (
    private.is_org_admin((select org_id from public.workspaces where id = workspace_id and deleted_at is null))
  );
create policy "workspace_members_update" on public.workspace_members for update to authenticated
  using (
    private.is_org_admin((select org_id from public.workspaces where id = workspace_id and deleted_at is null))
  )
  with check (
    private.is_org_admin((select org_id from public.workspaces where id = workspace_id and deleted_at is null))
  );
create policy "workspace_members_delete_denied" on public.workspace_members for delete to authenticated
  using (false);
