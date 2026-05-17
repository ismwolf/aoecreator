# Faz 2 B.1 — Tenancy + RLS Foundation Implementation Plan

Date: 2026-05-17
Spec: `docs/specs/2026-05-17-faz2b-b1-tenancy-spec.md`
Phase: Faz 2 B → sub-cycle B.1
Predecessors: A.T8 ✅ (MCP authenticated, types stub merged)
Successors: B.2 (5 domain tables FK on workspaces), B.3 (4 agent SDK tables), Faz 2 G (provision-org-on-signup Edge Function + invite flow)

## Pre-flight assumptions

- Branch: `feature/B-data-layer-multitenancy` already checked out (orchestrator created).
- Supabase MCP authenticated, project `ngjlxlkdfgfhiookndpl` reachable.
- `supabase/migrations/` empty (no prior migrations) — A.T8 left `.gitkeep` only.
- `extensions.uuid_generate_v4()` available (uuid-ossp installed_version=1.1).
- `moddatetime` available but NOT installed (default_version=1.0); migration installs it.
- Per global rule (CLAUDE.md + supabase.md): MCP `apply_migration` MUST be mirrored to a local `supabase/migrations/<ts>_<name>.sql` file. **Plan executes BOTH.**

## Tasks

### T1 — Compose migration SQL + write to `supabase/migrations/` (~5 min)

**File created:** `supabase/migrations/20260517000000_b1_tenancy.sql`

Contents = the SQL body that will also be passed to `mcp__supabase__apply_migration` in T2. Order:
1. `create extension if not exists moddatetime with schema extensions`
2. `create table public.organizations …` (cols + constraints, no triggers yet)
3. `create table public.org_members …` + `unique index org_members_org_user_active_uq … where deleted_at is null`
4. `create table public.workspaces …`
5. `create table public.workspace_members …` + unique partial index
6. Helper functions: `public.user_workspace_ids()`, `public.current_org_id()`, `public.is_org_admin(uuid)` — all with `revoke … from public, anon; grant … to authenticated;` (the JWT helper `current_org_id` doesn't need revoke since it's pure SQL, but follow same pattern for consistency)
7. `alter table … enable row level security` for all 4 tables
8. RLS policies (4 tables × {SELECT, INSERT, UPDATE} = ~12 policies; DELETE handled via app-level soft-delete UPDATE)
9. Partial indexes (5 on FK + RLS-referenced columns)
10. `moddatetime` triggers (4 — one per table)

**Verification:** file exists, SQL syntactically valid (can paste into `mcp__supabase__execute_sql` dry-run if needed, OR rely on MCP apply_migration to reject malformed SQL).

---

### T2 — Apply migration via MCP `apply_migration` (~2 min)

**Tool call:**
```
mcp__supabase__apply_migration(
  name="b1_tenancy",
  query=<SQL body from T1>
)
```

If MCP returns error → STOP, surface to orchestrator. Common failures:
- Syntax error in policy → fix SQL, re-apply
- Permission denied on `auth.users` references → unlikely (Supabase grants this by default)
- Extension already exists in different schema → `create extension if not exists` handles idempotency

**Verification:** MCP returns success. `mcp__supabase__list_migrations()` shows the new migration in the list.

---

### T3 — Verify schema + RLS state (~3 min)

**Tool calls:**
```
mcp__supabase__list_tables(schemas=["public"], verbose=true)
mcp__supabase__get_advisors(type="security")
```

**Expected:**
- `list_tables` returns 4 tables: `organizations`, `org_members`, `workspaces`, `workspace_members`
- Each table shows `rls_enabled: true`
- Each table has columns matching spec (id uuid pk, role check, deleted_at timestamptz, etc.)
- FK constraints present
- `get_advisors('security')` → `{"lints": []}` (no missing RLS, no policy issues)

If advisors show ANY `level: "ERROR"` or `level: "WARN"` → STOP, fix.

---

### T4 — Regenerate `database.types.ts` via MCP (~2 min)

**Tool call:**
```
mcp__supabase__generate_typescript_types()
```

Write the output to `apps/web/src/lib/database.types.ts`, replacing the empty-schema stub.

Expected: file now contains `organizations`, `org_members`, `workspaces`, `workspace_members` under `Database['public']['Tables']`, each with `Row`, `Insert`, `Update` typings.

---

### T5 — Typecheck + lint sanity (~2 min)

```powershell
pnpm --filter @aeogen/web typecheck
pnpm --filter @aeogen/web lint
pnpm --filter @aeogen/web build
```

All must pass. Build proves env.ts + database.types.ts integrate cleanly.

---

### T6 — Commit + push + PR + merge (~5 min)

Stage:
- `supabase/migrations/20260517000000_b1_tenancy.sql` (new)
- `apps/web/src/lib/database.types.ts` (modified — now has real tables)
- `docs/specs/2026-05-17-faz2b-b1-tenancy-spec.md` (new)
- `docs/plans/2026-05-17-faz2b-b1-tenancy-plan.md` (new)
- `docs/PROGRESS.md` (updated in T7)

Commit message: `feat(db): B.1 tenancy + RLS foundation — 4 tables + helpers + policies (Faz 2 B.1)`

Push, open PR feature/B-data-layer-multitenancy → dev, merge.

---

### T7 — PROGRESS.md + memory update (~3 min)

- Mark Faz 2 status `🔄 In progress: B.1 done, B.2 next`
- Logbook entry under `### 2026-05-17`
- Memory: `C:\Users\iso\.claude\projects\c--aeogenerator\memory\project_faz2b1_tenancy_baseline.md`
- Update MEMORY.md index

## Risks

- **MCP `apply_migration` is atomic per call** — entire SQL body succeeds or rolls back. Good for B.1 (single migration).
- **`auth.users` FK** — if `auth.users` schema changes in Supabase upgrades (rare), our FK may break. Mitigation: pinned `supabase/postgres:15.x` image baseline (A.T7 plan, when Docker arrives), Cloud upgrade monitored.
- **Idempotency on re-apply** — `create table` fails if table exists. **Mitigation:** never re-apply same migration; if needed, rollback first via separate migration. MCP itself prevents duplicate apply via the migrations registry.
- **`get_advisors` may complain about future-tense things** (e.g., missing index on FK only used in B.2). Read advisors carefully; fix only B.1-scoped issues, document B.2 carryovers.
- **`typecheck` failure after regen** — generated types might surface a real schema issue (e.g., column name with reserved keyword). Fix in spec, re-migrate.
- **Local file ↔ MCP drift** — if T1 file content differs from T2 query body, future devs see mismatched truth. **Mitigation:** T1 and T2 use the SAME exact SQL string (read T1 file, pass to T2).

## Verification gate

```
mcp__supabase__list_tables(["public"], true) → 4 tables, rls_enabled=true each
mcp__supabase__get_advisors("security") → {"lints": []}
mcp__supabase__list_migrations() → b1_tenancy present
pnpm --filter @aeogen/web typecheck → exit 0
pnpm --filter @aeogen/web lint → exit 0
pnpm --filter @aeogen/web build → exit 0
git status --porcelain → only expected files staged
```

## Branch + commit suggestion

- Branch: `feature/B-data-layer-multitenancy` (already on it)
- Commit:
  ```
  feat(db): B.1 tenancy + RLS foundation (Faz 2 B.1)

  4 tables: organizations, org_members, workspaces, workspace_members.
  Soft-delete (deleted_at), unique-active partial indexes, moddatetime
  triggers. SECURITY DEFINER helpers: user_workspace_ids(),
  current_org_id(), is_org_admin(uuid). Full RLS: TO authenticated,
  WITH CHECK on writes, deleted_at filter, JWT-claim + DB-query hybrid.

  Migration applied via mcp__supabase__apply_migration to Cloud project
  ngjlxlkdfgfhiookndpl + mirrored to supabase/migrations/20260517000000_
  b1_tenancy.sql (global rule).

  database.types.ts regenerated via MCP — 4 tables now typed.

  B.2 (sites/pages/runs) + B.3 (agent SDK) build on this foundation.
  Faz 2 G adds provision-org-on-signup Edge Function + invite flow.

  Spec: docs/specs/2026-05-17-faz2b-b1-tenancy-spec.md
  Plan: docs/plans/2026-05-17-faz2b-b1-tenancy-plan.md
  ```
- PR target: `dev`
