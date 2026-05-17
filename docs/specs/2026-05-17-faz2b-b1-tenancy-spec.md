# Faz 2 B.1 — Tenancy + Multi-Tenant RLS Foundation Spec

Date: 2026-05-17
Phase: Faz 2 B (data layer) → sub-cycle B.1 (tenancy foundation)
Predecessors: A.T8 ✅ (Supabase Cloud link, MCP authenticated, types stub merged)
Successors: B.2 (sites + analysis artifacts — 5 tables, FK depends on workspaces), B.3 (agent SDK support — agent_memory, agent_skills, embeddings, audit_log), Faz 2 G (provision-org-on-signup Edge Function + invite flow)

## Problem

aeogenerator bir ajans-için-ajansa-müvekkil multi-tenant SaaS. Her tablo (sites, pages, runs, scores, embeddings, audit_log) sonunda bir `workspace_id` veya `org_id` taşıyacak. RLS olmadan tenant izolasyonu yok = BOLA (OWASP API1) açığı = bir kullanıcı başka müvekkilin verisini görebilir.

**B.1 alt-cycle'ı:** Tenant taksonomisinin temelini (organizations → workspaces) ve RLS foundation helper'larını kuran 4 tablo + 2 SECURITY DEFINER function + tam RLS policy seti. Bundan sonraki tüm tablolar (B.2, B.3) bu foundation üstüne `references workspaces(id)` koyar ve `using (workspace_id in (select public.user_workspace_ids()))` policy pattern'ını kullanır.

## Goals

- Master plan §4.B'deki 4 tenancy tablosunu ata: `organizations`, `org_members`, `workspaces`, `workspace_members`
- Her tabloya RLS aktif et + `TO authenticated` policy'ler + `WITH CHECK` INSERT/UPDATE'te
- `public.user_workspace_ids()` SECURITY DEFINER stable function — RLS policy'lerin tek noktadan tüketeceği helper
- `public.current_org_id()` STABLE function — JWT `app_metadata.org_id` claim'ini cast edip uuid döner
- Soft-delete: her tabloda `deleted_at timestamptz`, RLS predicates `and deleted_at is null` filtreli
- `updated_at` otomatik bakım: `moddatetime` extension trigger
- Her FK + her RLS-referenced column'a partial index (`where deleted_at is null`)
- Migration MCP `apply_migration` ile uygulanır + paralelde `supabase/migrations/<ts>_b1_tenancy.sql` lokal dosyasına yazılır (global rule)
- `database.types.ts` regenerate: `Database['public']['Tables']` 4 tablo + Row/Insert/Update + Constants tipleri
- `get_advisors('security')` boş döner (no missing RLS, no policy issues)

## Non-Goals (deferred)

- **Provisioning trigger / Edge Function** — `auth.users` insert → org+workspace auto-create — **Faz 2 G** (B.1 sadece tabloları + RLS'i atmak)
- **Invite flow** — `invitations` table, email send, accept-invite — **Faz 2 G**
- **Stripe customer linkage** (`organizations.stripe_customer_id`) — **Faz 2 G/Faz 6** (master plan §11.3 açık konu)
- **White-label** (`organizations.logo_url`, `brand_colors`) — **v2** (master plan §11.4)
- **Workspace LLM budget** (`workspaces.monthly_llm_budget_usd`) — **Faz 3 C** (cost guard ile birlikte)
- **Slug fields** (`organizations.slug`, `workspaces.slug`) — **Faz 6 F** (dashboard URL routing'i geldikten sonra)
- **Sektör enum** (`workspaces.default_sector`) — **Faz 5 E** (agent prompts'a giderken)
- **B.2 tabloları** (`sites`, `pages`, `analysis_runs`, `agent_executions`, `scores`) — ayrı sub-cycle
- **B.3 tabloları** (`agent_memory`, `agent_skills`, `embeddings`, `audit_log`) — ayrı sub-cycle
- **Pytest BOLA integration test** (User A token → User B workspace = 0 rows) — Faz 2 G (gerçek auth.users + sign-up flow varken)
- **Periodic GDPR hard-purge job** — Faz 7 H ops (soft-deleted rows N gün sonra hard-delete)
- **Audit trail trigger** her mutation'da audit_log row — **B.3** (audit_log tablosu B.3'te gelir)

## Approach

### 1. Schema

```sql
-- organizations
create table public.organizations (
  id          uuid        primary key default extensions.uuid_generate_v4(),
  name        text        not null check (length(trim(name)) between 1 and 120),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  deleted_at  timestamptz
);

-- org_members
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

-- workspaces
create table public.workspaces (
  id          uuid        primary key default extensions.uuid_generate_v4(),
  org_id      uuid        not null references public.organizations(id) on delete cascade,
  name        text        not null check (length(trim(name)) between 1 and 120),
  created_at  timestamptz not null default now(),
  updated_at  timestamptz not null default now(),
  deleted_at  timestamptz
);

-- workspace_members
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
```

### 2. SECURITY DEFINER helper functions

```sql
-- Returns user's active workspace memberships
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

-- Returns JWT-claimed org_id (single org per user)
create or replace function public.current_org_id()
returns uuid
language sql
stable
as $$
  select nullif((select auth.jwt()) -> 'app_metadata' ->> 'org_id', '')::uuid
$$;

-- Returns true if current user is org owner or admin
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
```

### 3. RLS policies (4 tables × CRUD)

`alter table … enable row level security;` her tabloda + deny-all default + explicit policies:

**organizations:**
- SELECT: `id = current_org_id() and deleted_at is null`
- UPDATE: `id = current_org_id() and deleted_at is null and is_org_admin(id)` (WITH CHECK aynı)
- INSERT: `with check (is_org_admin(id))` — sadece owner/admin yeni org row tutamaz aslında; org creation Faz 2 G Edge Function (service_role) ile, INSERT policy `with check (false)` deny + Edge Function bypass eder service role ile. **Pratik:** authenticated user `insert into organizations` yapamamalı.
- DELETE (soft): app-level `update set deleted_at = now()`, separate DELETE policy yok (UPDATE policy yeterli)

**org_members:**
- SELECT: `org_id = current_org_id() and deleted_at is null`
- INSERT: `with check (is_org_admin(org_id))` — owner/admin yeni member ekleyebilir
- UPDATE: same predicate + WITH CHECK
- DELETE: same (kendisini owner çıkartamaz — invariant guard plan'da)

**workspaces:**
- SELECT: `org_id = current_org_id() and deleted_at is null and (id in (select public.user_workspace_ids()) or is_org_admin(org_id))`
- INSERT: `with check (is_org_admin(org_id))` — sadece owner/admin yeni workspace yaratabilir
- UPDATE: SELECT predicate + admin guard + WITH CHECK
- DELETE: app-level soft

**workspace_members:**
- SELECT: `workspace_id in (select public.user_workspace_ids()) and deleted_at is null`
- INSERT/UPDATE/DELETE: `is_org_admin((select org_id from workspaces where id = workspace_id))` — org admin invite/remove eder

### 4. Indexes (FK + RLS columns, partial)

```sql
create index on public.org_members(user_id) where deleted_at is null;
create index on public.org_members(org_id) where deleted_at is null;
create index on public.workspaces(org_id) where deleted_at is null;
create index on public.workspace_members(user_id) where deleted_at is null;
create index on public.workspace_members(workspace_id) where deleted_at is null;
```

### 5. moddatetime triggers

```sql
create extension if not exists moddatetime with schema extensions;

create trigger handle_updated_at before update on public.organizations
  for each row execute function extensions.moddatetime(updated_at);
-- ... aynı pattern org_members, workspaces, workspace_members için
```

### 6. Migration delivery

- **Tek SQL dosyası** `supabase/migrations/20260517000000_b1_tenancy.sql` (UTC timestamp + slug naming)
- **MCP `apply_migration`** — Cloud'a uygulanır + Supabase migration metadata'sına kaydedilir
- **Aynı SQL local'e yazılır** (global rule: MCP apply_migration lokal dosya yaratmaz)
- **`database.types.ts`** MCP `generate_typescript_types` ile regenerate
- **`get_advisors('security')`** çalıştır → empty lints sonucu beklenir

## Risks

- **`current_org_id()` döner null** eğer `app_metadata.org_id` claim yok → RLS predicates `null = id` false döner → kullanıcı hiçbir satır göremez. Bu **istenen davranış** (provisioning Faz 2 G'de claim'i set eder). B.1 testinde user has no org → 0 row görür, doğru.
- **Service role `current_org_id()`** = null fakat service role RLS bypass eder, dolayısıyla provisioning Edge Function (Faz 2 G) sorunsuz INSERT yapar.
- **`auth.users` cascade delete:** kullanıcı silinirse tüm `org_members`/`workspace_members` row'ları silinir. Eğer kullanıcı sole org owner ise org orphan kalır (deleted_at null ama hiç member yok). Faz 7 H ops runbook: orphan org detect + cleanup. **B.1'de sadece flag — fix Faz 7 H.**
- **`unique (org_id, user_id) where deleted_at is null` partial:** kullanıcı leave + rejoin senaryosunda eski row deleted_at != null kalır, yeni row eklenir. Aynı user 1 active + N soft-deleted history rows. **Kabul:** soft-delete kararının doğal sonucu.
- **moddatetime extension** zaten supabase/postgres'te available (default_version=1.0, installed_version=null). `create extension if not exists` idempotent.
- **`is_org_admin()` SECURITY DEFINER + recursive RLS:** function `org_members` tablosunu okur, fakat function security definer + stable, RLS bypass eder. Recursion riski yok.
- **`auth.jwt() -> 'app_metadata'`** null safety: `nullif(... ->> 'org_id', '')::uuid` boş string `null` cast hatası engeller. Eksik claim → function null döner → RLS deny.
- **migration timestamp collision:** birden fazla developer aynı dakikada migration yaratırsa çakışır. Tek developer şu an, sorun yok; Faz 8 team scale'inde Supabase CLI'in random suffix'i çözer.
- **MCP apply_migration vs local file sync:** MCP migration name + body verir, local dosyaya da AYNI body yazmak ZORUNLU. Drift kontrol Faz 2 B.3 sonunda audit'lenmeli (veya hemen B.1'de).

## Open questions

1. **Provisioning Edge Function timeline:** Faz 2 G ne zaman? B.1 merge edildikten sonra hemen mi, yoksa B.2 + B.3 bittikten sonra mı? **Recommend:** B.3 sonrası, çünkü provisioning sadece tabloları doldurur, schema değişmez. — Sonra netleştirilebilir.
2. **`is_org_admin()` farklı yerlere mi koyalım?** Şu an public schema, RLS policy'lerin tüketmesi için. **OK olarak kabul** — schema lock-in.
3. **`extensions.uuid_generate_v4()` vs `gen_random_uuid()`:** `uuid-ossp` installed (extensions schema). `pgcrypto` da installed → `gen_random_uuid()` de çalışır. **Pick uuid_generate_v4()** çünkü Supabase docs'un canonical pattern'i. — Lock.
4. **Slug, monthly_llm_budget_usd, sector** alanları — Non-Goals'da listelendi, hangi task'ta eklenecek yukarıda not düşüldü. — OK.
5. **`audit.audit_log` trigger** her DML için — B.3'te audit_log tablosu geldikten sonra B.1 tablolarına da retroaktif trigger eklenebilir. Şu an B.1'de yok. — Defer.

---

## Acceptance criteria

- [ ] `mcp__supabase__list_tables(["public"], verbose=true)` → 4 tablo görünür (organizations, org_members, workspaces, workspace_members)
- [ ] Her tablo `rls_enabled = true`
- [ ] Her tablo en az 4 policy (SELECT + INSERT + UPDATE + DELETE veya birleştirilmiş USING + WITH CHECK)
- [ ] `get_advisors('security')` lints array empty
- [ ] `database.types.ts` regenerated, 4 tablo `Database['public']['Tables']` altında
- [ ] `pnpm --filter @aeogen/web typecheck` passes
- [ ] `supabase/migrations/20260517000000_b1_tenancy.sql` local file present, content matches MCP-applied migration
- [ ] PR opened, reviewed, merged to dev
- [ ] PROGRESS.md updated, memory entry written
