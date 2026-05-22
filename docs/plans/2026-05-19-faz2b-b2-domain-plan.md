# Faz 2 B.2 — Domain Entities Implementation Plan

Date: 2026-05-19
Spec: `docs/specs/2026-05-19-faz2b-b2-domain-spec.md`
Phase: Faz 2 B → sub-cycle B.2
Predecessors: B.1 ✅ (tenancy + RLS helpers in `private` schema, MCP authenticated)
Successors: B.3 (agent_memory, agent_skills, embeddings + pgvector, audit_log), Faz 2 G (provision-org-on-signup)

## Pre-flight assumptions

- Branch `feature/B.2-domain-entities` already checked out (orchestrator created).
- Supabase MCP authenticated, project `ngjlxlkdfgfhiookndpl` reachable.
- `private.user_workspace_ids()` SECURITY DEFINER stable function available (from B.1).
- `extensions.uuid_generate_v4()` available (uuid-ossp 1.1).
- `moddatetime` extension already installed (from B.1).
- `database.types.ts` currently has 4 tables; will be regenerated with 9.
- Per global rule (CLAUDE.md + supabase.md): MCP `apply_migration` MUST be mirrored to a local `supabase/migrations/<ts>_<name>.sql` file. **Plan executes BOTH.**

## Tasks

### T1 — Compose migration SQL + write to `supabase/migrations/` (~10 min)

**File created:** `supabase/migrations/20260519000000_b2_domain.sql`

Contents follow the spec exactly. Order:

1. `create extension if not exists moddatetime with schema extensions;` (idempotent, B.1 already did this; harmless re-statement)
2. **5 table CREATE statements** in dependency order: `sites`, `pages`, `analysis_runs`, `agent_executions`, `scores`
3. **Unique partial indexes** (3):
   - `sites_workspace_url_active_uq` on (workspace_id, url) where deleted_at is null
   - `pages_site_url_active_uq` on (site_id, url) where deleted_at is null
   - `scores_page_technique_run_active_uq` on (page_id, technique_id, run_id) where deleted_at is null
4. **Performance partial indexes** (12 — spec §3):
   - `sites_workspace_id_idx`, `pages_workspace_id_idx`, `pages_site_id_idx`
   - `analysis_runs_workspace_id_idx`, `analysis_runs_site_id_idx`, `analysis_runs_status_idx`
   - `agent_executions_workspace_id_idx`, `agent_executions_run_id_idx`, `agent_executions_status_idx`
   - `scores_workspace_id_idx`, `scores_page_id_idx`, `scores_run_id_idx`
5. **Enable RLS** on all 5 tables (`alter table … enable row level security;`)
6. **RLS policies** — 3 per table × 5 = 15 policies. Pattern (replace `<tbl>` with each table):

   ```sql
   create policy "<tbl>_select" on public.<tbl>
     for select to authenticated
     using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null);

   create policy "<tbl>_insert" on public.<tbl>
     for insert to authenticated
     with check (workspace_id in (select private.user_workspace_ids()));

   create policy "<tbl>_update" on public.<tbl>
     for update to authenticated
     using (workspace_id in (select private.user_workspace_ids()) and deleted_at is null)
     with check (workspace_id in (select private.user_workspace_ids()));
   ```

7. **moddatetime triggers** (5 — one per table)

**Verification:** file exists, SQL syntactically valid. Can dry-run via `mcp__supabase__execute_sql` with a `select` after each statement before committing, but B.1 showed apply_migration's atomicity is sufficient.

---

### T2 — Apply migration via MCP `apply_migration` (~3 min)

**Tool call:**

```
mcp__supabase__apply_migration(
  name="b2_domain",
  query=<SQL body from T1>
)
```

If error:

- **Syntax error** → fix SQL in T1 file, re-apply (MCP doesn't store the partial state on failure — atomic rollback)
- **`private` schema not found** → B.1 helpers not present; STOP, recheck B.1 merged
- **`workspace_id` FK failure** → workspaces table missing or wrong column name; STOP

**Verification:**

- MCP returns success
- `mcp__supabase__list_migrations()` shows `b2_domain` in the list

---

### T3 — Verify schema + RLS state (~3 min)

**Tool calls:**

```
mcp__supabase__list_tables(schemas=["public"], verbose=true)
mcp__supabase__get_advisors(type="security")
```

**Expected:**

- `list_tables` returns 9 tables: B.1's 4 + B.2's 5 (`sites`, `pages`, `analysis_runs`, `agent_executions`, `scores`)
- Each B.2 table shows `rls_enabled: true`
- Each B.2 table has 3 policies (SELECT, INSERT, UPDATE)
- FK constraints present and pointing to expected parents
- `get_advisors('security')` → `{"lints": []}`

If advisors show ANY `level: "ERROR"` or `level: "WARN"` → STOP, fix in a follow-up migration.

---

### T4 — Regenerate `database.types.ts` via MCP (~2 min)

**Tool call:**

```
mcp__supabase__generate_typescript_types()
```

Write the output to `apps/web/src/lib/database.types.ts`, replacing the B.1-era file (which had 4 tables).

Expected: file now contains 9 tables under `Database['public']['Tables']`, each with `Row`, `Insert`, `Update` typings. Constants for the CHECK enums (status values, role) may appear.

---

### T5 — Typecheck + lint + build sanity (~3 min)

```powershell
pnpm --filter @aeogen/web typecheck
pnpm --filter @aeogen/web lint
pnpm --filter @aeogen/web build
```

All must pass. Build proves env.ts + database.types.ts integrate cleanly (no consumers yet, so types are silent — but the file must compile).

---

### T6 — Commit + push + PR (~5 min)

Stage:

- `supabase/migrations/20260519000000_b2_domain.sql` (new)
- `apps/web/src/lib/database.types.ts` (modified — 9 tables now)
- `docs/specs/2026-05-19-faz2b-b2-domain-spec.md` (new)
- `docs/plans/2026-05-19-faz2b-b2-domain-plan.md` (new)
- `docs/PROGRESS.md` (updated in T7)

Commit message:

```
feat(db): B.2 domain entities — sites, pages, runs, executions, scores (Faz 2 B.2)

5 tables: sites, pages, analysis_runs, agent_executions, scores.
Workspace_id denormalized on every table for RLS perf (using
private.user_workspace_ids() from B.1 — single subquery per statement).
Soft-delete, moddatetime triggers, partial unique + perf indexes.

Schema decisions (locked 2026-05-19):
- technique_id smallint + CHECK (1..12) — no separate techniques table v1
- status text + CHECK (B.1 role pattern) — ALTER-friendly vs pg ENUM
- kicked_by ON DELETE SET NULL — historical run preserved post-user-delete
- agent_executions.input/output jsonb — flexible per-technique shape

Migration applied via mcp__supabase__apply_migration to Cloud project
ngjlxlkdfgfhiookndpl + mirrored to supabase/migrations/20260519000000_
b2_domain.sql (global rule).

database.types.ts regenerated — 9 tables now typed.

B.3 (agent_memory, agent_skills, embeddings, audit_log + pgvector) builds
on this layer.

Spec: docs/specs/2026-05-19-faz2b-b2-domain-spec.md
Plan: docs/plans/2026-05-19-faz2b-b2-domain-plan.md
```

Push, open PR `feature/B.2-domain-entities` → `dev`.

PR title: `feat(db): B.2 domain entities — sites + pages + runs + executions + scores`
PR body: Summary (5 tables, RLS pattern, decisions), Test plan (MCP verify checklist).

---

### T7 — PROGRESS.md + memory update (~3 min)

- Mark B.2 acceptance criteria all `[x]`
- Update PROGRESS.md header: "Mevcut task: B.3 — agent SDK support (4 tables + pgvector)"
- Logbook entry under `### 2026-05-19` with T1-T6 summaries
- Memory: `C:\Users\iso\.claude\projects\c--aeogenerator\memory\project_faz2b2_domain_baseline.md` describing schema decisions + RLS pattern reuse
- Update `MEMORY.md` index with one-line entry
- Code-reviewer PASS before merging
- After merge: `git checkout dev && git pull && git branch -d feature/B.2-domain-entities`

## Risks

- **MCP `apply_migration` atomic per call** — entire SQL body succeeds or rolls back (B.1 confirmed). Good for B.2 (single migration, ~5 tables).
- **`private.user_workspace_ids()` dependency** — if B.1 migration was somehow not on dev branch's Cloud state (e.g., manual rollback), B.2 RLS policies fail. Mitigation: T3 list_tables also checks B.1 tables present.
- **`auth.users` FK on kicked_by** — Supabase upgrade risk same as B.1 (low).
- **Generated types diff size** — `database.types.ts` ~2x larger; expected, not a regression.
- **`typecheck` failure after regen** — possible if column name collides with TS reserved keyword. Unlikely with our naming.
- **Local file ↔ MCP drift** — T1 SQL string MUST equal T2 SQL string. Code-writer reads T1 file, passes to T2. Verify by diffing.
- **>300 line migration** — B.2 is ~250 SQL lines (5 tables + 15 policies + 15 indexes + 5 triggers). If MCP rejects, split into b2a (DDL) + b2b (policies+indexes); B.1 was ~180 lines, MCP accepted, so B.2 should be fine.
- **`recommendations jsonb` shape未lock:** application-side validation in Faz 5 E. DB allows any jsonb.

## Verification gate

```
mcp__supabase__list_tables(["public"], true)
  → 9 tables, B.2's 5 with rls_enabled=true each
mcp__supabase__get_advisors("security")
  → {"lints": []}
mcp__supabase__list_migrations()
  → b2_domain entry present (along with b1_tenancy + b1_security_hardening)
pnpm --filter @aeogen/web typecheck → exit 0
pnpm --filter @aeogen/web lint → exit 0
pnpm --filter @aeogen/web build → exit 0
git status --porcelain → only expected files staged (spec, plan, migration, types, PROGRESS)
```

## Branch + commit suggestion

- Branch: `feature/B.2-domain-entities` (already on it)
- Commit: see T6 message
- PR target: `dev`
