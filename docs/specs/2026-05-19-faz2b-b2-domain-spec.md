# Faz 2 B.2 — Domain Entities Spec

Date: 2026-05-19
Phase: Faz 2 B (data layer) → sub-cycle B.2 (domain entities)
Predecessors: B.1 ✅ (organizations + workspaces + members + RLS helpers in `private` schema)
Successors: B.3 (agent_memory, agent_skills, embeddings, audit_log + pgvector enable), Faz 2 G (provision-org-on-signup Edge Function)

## Problem

B.1 tenancy temeli (`organizations`, `workspaces` + RLS helpers) hazır. Şimdi GEO/AEO analiz iş akışının çekirdek domain entity'leri eksik: müvekkil siteleri, crawl edilmiş sayfaları, analiz koşumları, agent execution kayıtları, ve teknik bazlı skor sonuçları. Bunlar olmadan ne agent dispatch (Faz 3 C), ne crawl pipeline (Faz 4 D), ne dashboard (Faz 6 F) ilerleyemez.

**B.2 alt-cycle'ı:** Master plan §3 entity ağacındaki `sites → pages` ve `analysis_runs → agent_executions / scores` zincirini kuran 5 tablo + RLS + index + trigger seti. B.3 (agent SDK support) bu tablolara FK koyacak (özellikle `embeddings.page_id` ve `audit_log` action_target alanı).

## Goals

- Master plan §4.B'deki 5 domain tablosunu yarat: `sites`, `pages`, `analysis_runs`, `agent_executions`, `scores`
- B.1 pattern'larını miras al (lock-in):
  - `extensions.uuid_generate_v4()` primary key default
  - Soft-delete (`deleted_at timestamptz`, partial index `where deleted_at is null`)
  - `moddatetime` trigger her tabloda
  - RLS aktif + `TO authenticated` + `WITH CHECK` (INSERT/UPDATE)
  - SECURITY DEFINER helper'lar `private` schema (B.1'den miras: `private.user_workspace_ids()`)
- **workspace_id denormalize** (RLS perf): 5 tablonun hepsinde `workspace_id uuid not null references public.workspaces(id) on delete cascade` — RLS predicate join'sız çalışır
- Brainstorm kararları (2026-05-19):
  - `technique_id smallint not null check (technique_id between 1 and 12)` (no separate techniques table v1)
  - `status text + CHECK constraint` (B.1 `role` ile tutarlı)
  - `kicked_by uuid references auth.users(id) on delete set null` (historical run kalır, attribution kaybolur)
  - `input jsonb`, `output jsonb` (master plan §4.B uyumlu, esnek per-technique shape)
- FK + RLS column'larına partial index
- Migration MCP `apply_migration` ile + lokal `supabase/migrations/<ts>_b2_domain.sql` mirror (global rule)
- `database.types.ts` regenerate
- `get_advisors('security')` boş döner

## Non-Goals (deferred)

- **pgvector enable** ve `embeddings` tablosu → **B.3**
- **`agent_memory`, `agent_skills`, `audit_log`** → **B.3**
- **Crawl/parse pipeline** (Crawl4AI integration, Modal embed) → **Faz 4 D**
- **Agent execution implementation** (gerçek dispatch logic, status transitions) → **Faz 3 C / Faz 5 E**
- **`pages.parsed_content` schema disiplini** (master plan §4.B'de "jsonb" diye geçiyor, exact shape Faz 4 D'de) → B.2 sadece kolon tipini koyar
- **`scores.recommendations` jsonb shape** (master plan §4: `{impact, effort, action}` Faz 5 E'de standartlaşır) → B.2 sadece kolon
- **Real-time channels** (`analysis_runs:run_id` Supabase Realtime) → Faz 6 F
- **GDPR hard-purge job** (90 günden eski `agent_executions` arşivler) → Faz 7 H (master plan §6)
- **Audit triggers** her B.2 mutation'da audit_log row → B.3 (audit_log tablosu B.3'te gelir)
- **Pytest BOLA integration test** → Faz 2 G (gerçek auth.users)
- **Strict workspace_id ↔ parent consistency trigger** (örn. `pages.workspace_id` her zaman `sites.workspace_id`'ye eşit olmak zorunda) → v1.5 (app-level enforcement yeterli, performans önemli)
- **GIN index on `input`/`output`/`parsed_content` jsonb** → ilk gerçek sorgu pattern'i çıkınca (B.2 sonrası, agent dispatch geldiğinde)
- **Cursor-based pagination** kolonları (örn. `analysis_runs` listede) → Faz 6 F dashboard'da

## Approach

### 1. Schema

```sql
-- sites
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
create unique index sites_workspace_url_active_uq
  on public.sites (workspace_id, url) where deleted_at is null;

-- pages
create table public.pages (
  id                uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid        not null references public.workspaces(id) on delete cascade,  -- denormalized for RLS perf
  site_id           uuid        not null references public.sites(id) on delete cascade,
  url               text        not null check (length(trim(url)) between 1 and 2048 and url ~ '^https?://'),
  html_path         text        check (html_path is null or length(trim(html_path)) between 1 and 512),  -- Supabase Storage path
  parsed_content    jsonb,
  content_hash      text        check (content_hash is null or content_hash ~ '^[a-f0-9]{64}$'),  -- sha256 hex
  last_crawled_at   timestamptz,
  created_at        timestamptz not null default now(),
  updated_at        timestamptz not null default now(),
  deleted_at        timestamptz
);
create unique index pages_site_url_active_uq
  on public.pages (site_id, url) where deleted_at is null;

-- analysis_runs
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

-- agent_executions
create table public.agent_executions (
  id                uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid        not null references public.workspaces(id) on delete cascade,  -- denormalized for RLS perf
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

-- scores
create table public.scores (
  id                uuid        primary key default extensions.uuid_generate_v4(),
  workspace_id      uuid        not null references public.workspaces(id) on delete cascade,  -- denormalized for RLS perf
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
create unique index scores_page_technique_run_active_uq
  on public.scores (page_id, technique_id, run_id) where deleted_at is null;
```

### 2. RLS policies

`alter table … enable row level security;` her tabloda. Predicates B.1 helper'larını kullanır.

Tüm 5 tablo aynı pattern:

- **SELECT:** `workspace_id in (select private.user_workspace_ids()) and deleted_at is null`
- **INSERT:** `with check (workspace_id in (select private.user_workspace_ids()))`
- **UPDATE:** `using (...) with check (...)` — SELECT pattern + WITH CHECK aynı
- **DELETE:** app-level soft (UPDATE deleted_at = now()) — explicit DELETE policy YOK

Ekstra: `sites` ve `analysis_runs` için INSERT/UPDATE'te workspace admin guard EKLENMEZ — workspace member rolüne sahip user (admin/member/viewer) zaten `user_workspace_ids()` set'inde, viewer dahil. **Karar:** viewer için INSERT/UPDATE deny ileride F dashboard'da app-level enforce edilir; B.2'de basit kalır (DB-level read = write parity).

### 3. Indexes (FK + RLS columns)

```sql
-- Partial indexes on workspace_id (RLS hot path) + parent FKs
create index sites_workspace_id_idx       on public.sites(workspace_id) where deleted_at is null;
create index pages_workspace_id_idx       on public.pages(workspace_id) where deleted_at is null;
create index pages_site_id_idx            on public.pages(site_id) where deleted_at is null;
create index analysis_runs_workspace_id_idx on public.analysis_runs(workspace_id) where deleted_at is null;
create index analysis_runs_site_id_idx    on public.analysis_runs(site_id) where deleted_at is null;
create index analysis_runs_status_idx     on public.analysis_runs(status) where deleted_at is null and status in ('queued', 'running');
create index agent_executions_workspace_id_idx on public.agent_executions(workspace_id) where deleted_at is null;
create index agent_executions_run_id_idx  on public.agent_executions(run_id) where deleted_at is null;
create index agent_executions_status_idx  on public.agent_executions(status) where deleted_at is null and status in ('queued', 'running');
create index scores_workspace_id_idx      on public.scores(workspace_id) where deleted_at is null;
create index scores_page_id_idx           on public.scores(page_id) where deleted_at is null;
create index scores_run_id_idx            on public.scores(run_id) where deleted_at is null;
```

### 4. moddatetime triggers

B.1 pattern'i 5 tabloya genişlet:

```sql
create trigger handle_updated_at before update on public.sites
  for each row execute function extensions.moddatetime(updated_at);
-- ... aynı pattern pages, analysis_runs, agent_executions, scores için
```

### 5. Migration delivery

- Tek SQL dosyası `supabase/migrations/20260519000000_b2_domain.sql` (UTC timestamp + slug)
- MCP `apply_migration(name="b2_domain", query=<SQL>)`
- Aynı SQL local dosyaya yazılır (global rule)
- `database.types.ts` MCP `generate_typescript_types` ile regenerate (5 yeni tablo eklenmiş olarak)
- `get_advisors('security')` çalıştır → empty lints beklenir

## Risks

- **`workspace_id` denormalize tutarlılık riski:** `pages.workspace_id` ile `pages.site.workspace_id` divergence olabilir (yanlış app code). v1.5'te trigger ile enforce. Şu an app-level discipline (DAL helpers) yeterli.
- **`sites_workspace_url_active_uq` unique partial:** aynı workspace'te aynı URL iki kez eklenemez. Soft-delete sonrası tekrar eklenebilir (eski row deleted_at not null). Kabul.
- **`scores` unique (page_id, technique_id, run_id):** her run'da her page için her technique max 1 score. v1 mantığı doğru. Re-run senaryosu yeni run_id ⇒ yeni unique key.
- **`analysis_runs.status` enum genişlemesi v2'de:** `pending_user_input` gibi yeni state'ler — text + CHECK pattern'i `ALTER TABLE ... DROP CONSTRAINT + ADD` ile çözer. Postgres ENUM'a göre daha esnek (lock-in).
- **`agent_executions.input/output` jsonb büyüklüğü:** Postgres TOAST otomatik handle eder, ama büyük (>1MB) payload'lar query latency'sini etkileyebilir. v1.5'te 64KB üstü `agent-io/<run>/<exec>.json` Supabase Storage'a offload kararı.
- **`technique_id` smallint + CHECK (1..12)** v2'de yeni teknik eklerken `ALTER TABLE ... DROP CONSTRAINT + ADD` — basit migration. Lock-in: master plan §1 tablosundaki 12 teknik sınırını aşmayız (öteki teknikler v2'de bile olsa 1-12 arası).
- **`kicked_by` SET NULL** + RLS: kullanıcı silindiğinde kicked_by null kalır ama row hâlâ workspace'te. RLS predicate workspace_id'ye dayanır, attribution kaybı sadece UI'da görünür ("deleted user").
- **MCP atomic migration:** B.1'de görülen pattern — tek SQL body ya tamamen başarılı ya rollback. 5 tablo + ~20 policy + ~12 index + 5 trigger tek migration'a sığar. Eğer >300 satır olursa B.2'yi B.2a (tablolar) + B.2b (policy + index) diye böleriz — ama B.1 tek migration olarak başarılı oldu, B.2 için de tek migration deneriz.
- **`create extension if not exists moddatetime`** B.1'de yapıldı, B.2'de tekrar yapmaya gerek yok ama idempotent — riske gerek yok, yine de migration'ın başında bırakırız.
- **Generated types diff:** `database.types.ts` ~2x büyür (4 → 9 tablo). PR diff büyük olur ama beklenen.

## Open questions

1. **`analysis_runs.total_cost_usd` precision** (10, 4) — yani max 999999.9999 USD. v1 için workspace başına aylık $500 budget cap düşünüldüğünde fazlasıyla yeterli. — Lock.
2. **`agent_executions.score` 0-100 normalized mı, yoksa technique-specific raw mı?** Master plan §4.B "score" diyor, normalize/raw belirtmiyor. **Karar:** 0-100 normalized (UI consumption + cross-technique karşılaştırma kolay). Each technique kendi raw score'unu output jsonb'de tutar. — Lock.
3. **`sites.default_language` kısıt:** length=2 (ISO 639-1 'tr', 'en', 'de'). v1.5'te BCP-47 ('tr-TR') gerekirse uzatılır.
4. **`pages.content_hash` sha256 hex (64 char)** vs sha1 (40 char). sha256 daha güçlü, storage farkı negligible. Lock.
5. **viewer rolü için INSERT/UPDATE deny:** B.2'de RLS basit (workspace_id check), viewer/member/admin ayrımı yok. App-level enforcement (DAL helpers) Faz 6 F'de. Spec'te accepted.
6. **`scores.prev_score` doldurma stratejisi:** her yeni run'da score insert ederken `prev_score = (select score from scores where page_id=? and technique_id=? order by created_at desc limit 1)`. Bu B.2 schema değil, application logic. B.2 sadece kolonu açar.

---

## Acceptance criteria

- [ ] `mcp__supabase__list_tables(["public"], verbose=true)` → toplam 9 tablo (B.1'in 4'ü + B.2'nin 5'i)
- [ ] B.2 5 tablo `rls_enabled = true`
- [ ] Her B.2 tablosunda min 3 policy (SELECT + INSERT + UPDATE; DELETE app-level soft)
- [ ] `get_advisors('security')` lints array empty
- [ ] `database.types.ts` regenerated, 9 tablo `Database['public']['Tables']` altında
- [ ] `pnpm --filter @aeogen/web typecheck` + `lint` + `build` passes
- [ ] `supabase/migrations/20260519000000_b2_domain.sql` local file content matches MCP-applied
- [ ] PR opened on `feature/B.2-domain-entities` → `dev`, code-reviewer PASS, merged
- [ ] PROGRESS.md updated, memory entry yazıldı
