# aeogenerator — Implementation Progress

> Bu dosya `aeogen-orchestrator` skill tarafından her milestone sonrası
> güncellenir. Manuel düzenleme yapılırsa orkestratör konfliği fark
> eder ve kullanıcıya sorar.

**Son güncelleme:** 2026-05-16 (A.T8 implementation PASS — Supabase
CLI + .mcp.json + env schema + types stub; T8.3 login deferred to user)
**Mevcut faz:** Faz 1 A (🔄 In progress: T9 sırada, T7 ⏸ blocked) — Faz 0 ✅ DONE
**Mevcut alt-proje:** A — Foundation Bootstrap
**Mevcut task:** A.T9 — `@t3-oss/env-nextjs` + `pydantic-settings` env validation expansion (DATABASE_URL, REDIS_URL, OPENROUTER_API_KEY)
**Sıradaki milestone:** Faz 1 A complete (~1 hafta)
**Toplam ilerleme:** 21 / ~70 task (%30) — Faz 0 +11 task, A.T3 +1, A.T4 +1, A.T5 +1, A.T6 +1, A.T8 +1; A.T7 plan ready but impl deferred

## Faz durumları

| # | Faz | Durum | Süre tahmini | Notlar |
|---|---|---|---|---|
| 0 | langchain-master skill | ✅ Done | 1 gün | T1-T11 merged 2026-05-14 (PR #2). Skill aktif: `Skill(skill="langchain-master", ...)`. T11 runtime dry-runs ilk gerçek MCP çağrısında doğrulanacak. |
| 1 | A — Foundation bootstrap | ⏸ Blocked by Faz 0 | 1 hafta | Spec henüz yazılmadı |
| 2 | B — Data layer + multi-tenancy | ⏸ Blocked by Faz 1 | 1 hafta | — |
| 3 | C — Agent Core SDK | ⏸ Blocked by Faz 2 | 2 hafta | En kritik faz |
| 4 | D — Crawl & ingestion | ⏸ Blocked by Faz 3 | 1 hafta | Crawl4AI + Modal embed |
| 5 | E — v1 GEO agent suite (5 teknik) | ⏸ Blocked by Faz 4 | 3 hafta | 5 Analyzer + 5 Generator + Orchestrator |
| 6 | F + G — Dashboard + Auth (paralel) | ⏸ Blocked by Faz 5 | 2 hafta | Next.js + Supabase Auth + Org |
| 7 | H — Observability + Ops | ⏸ Blocked by Faz 6 | 1 hafta | LangSmith + Sentry + OTel |
| 8 | Closed beta | ⏸ Blocked by Faz 7 | 1 hafta | 3-5 ajansla E2E test |

**Durum legend:** ⏳ Pending / 🔄 In-progress / ✅ Completed / ⏸ Blocked / ⚠️ Issue / ⏭ Skipped

---

## Faz 0 — `langchain-master` Skill (✅ Done — 2026-05-14)

**Spec:** `docs/superpowers/specs/2026-05-13-langchain-master-skill-design.md`
**Plan:** `docs/superpowers/plans/2026-05-13-langchain-master-skill.md`
**PR:** [#2](https://github.com/ismwolf/aoecreator/pull/2) (merged → `02f6981`)
**Hedef:** Senior LangChain Python advisor skill — Claude Code
geliştirici (insan + AI) için. Production agent DEĞİL.

- [x] T1: Skill directory scaffold (`memory/`, `references/`, `_index.json`)
- [x] T2: SKILL.md frontmatter + ToC
- [x] T3: Persona section
- [x] T4: 6-step Workflow section (normalize → check refs → check
      memory → MCP query → promotion check → return)
- [x] T5: Topic-key normalization rules
- [x] T6: Cache file formats (`_index.json`, `memory/<key>.md`)
- [x] T7: Cache management (TTL=30d, promotion @ hit_count≥3, decline)
- [x] T8: Error recovery (corrupted index, missing memory, MCP fail)
- [x] T9: Output format template
- [x] T10: README.md overview
- [x] T11: Static verification PASS (8 `## ` headings, plan expected 7
      — off-by-one due to `## Contents`). Runtime dry-runs (Steps 2-7)
      deferred to first live MCP invocation.

**Verification gate:** Tüm 11 task ✅ + skill `Skill(skill="langchain-master", args="...")` ile çağrılabiliyor + MCP cache miss/hit/promotion akışları çalışıyor.

---

## Faz 1 (A) — Foundation Bootstrap (⏸ Blocked)

**Spec:** Henüz yazılmadı (`docs/specs/2026-05-XX-foundation-bootstrap-spec.md`).
**Plan:** Henüz yazılmadı.

Yapılacaklar (high-level master plan §4.A'dan):
- [x] T1: `git init -b dev` + initial commit + push (✅ 2026-05-13)
- [x] T2: `.gitignore` (Node + Python + IDE + project-specific) (✅ 2026-05-13)
- [x] T2.1: 3 environment branches (`dev`, `test`, `main`) + push (✅ 2026-05-13)
- [x] T2.2: GitHub default branch = `dev` (✅ 2026-05-13)
- [x] T2.3: GitHub MCP user-scope install (✅ 2026-05-13)
- [x] T3: pnpm workspace skeleton (`pnpm-workspace.yaml`, `package.json`) (✅ 2026-05-14 — feature/A.T3-pnpm-workspace-skeleton, review PASS)
- [x] T4: `apps/web/` Next.js 15 scaffold (App Router, TS strict, Tailwind v4, shadcn init) — ✅ 2026-05-14 (feature/A.T4-nextjs-scaffold; build PASS, typecheck PASS, lint PASS, security headers verified via curl)
- [x] T5: `apps/api/` FastAPI 3.12 scaffold (uv, ruff lint+format, mypy strict, pytest+asyncio, pydantic-settings) — ✅ 2026-05-15 (feature/A.T5-fastapi-scaffold; ruff/mypy/pytest/uv lock all green, health/live + health/ready live-verified, review PASS)
- [x] T6: `packages/shared/` Zod ↔ Pydantic parity schemas (Zod 4 source + datamodel-code-generator + drift script) — ✅ 2026-05-16 (feature/A.T6-shared-zod-pydantic-parity; 2 example schemas Site+Workspace; same-fixture parity tests both sides; review PASS + P2 `--strip-default-none` flag removed)
- [ ] T7: `infra/docker-compose.dev.yml` (Postgres + Redis) — ⏸ **BLOCKED 2026-05-16** on missing Docker Desktop. Plan ready (`docs/plans/2026-05-16-A.T7-docker-compose-dev-plan.md`, PR #7 plan-only merged). Resume: install Docker Desktop + WSL2 backend → new branch off dev → re-dispatch code-writer with same plan. **User chose to skip ahead to A.T8** (Supabase Cloud provides managed Postgres, making local Docker dev optional)
- [x] T8: `supabase/config.toml` + Supabase Cloud link + `.mcp.json` (MCP-first) + env schema expansion + `database.types.ts` stub — ✅ 2026-05-16 (feature/A.T8-supabase-impl; CLI bootstrap done, MCP URL=`https://mcp.supabase.com/mcp?project_ref=ngjlxlkdfgfhiookndpl`, T8.3 login + real types codegen deferred to user-interactive post-merge; review PASS)
- [ ] T9: `@t3-oss/env-nextjs` + `pydantic-settings` env validation
- [ ] T10: Husky + commitlint + lint-staged
- [ ] T11: `gitleaks` pre-commit
- [ ] T12: `.github/workflows/ci.yml` (lint + test + typecheck)
- [ ] T13: Initial README.md
- [ ] T14: Branch protection rules (manuel GitHub UI):
  - `main`: PR + 1 approval + require CI + dismiss stale
  - `test`: PR + require CI
  - `dev`: require CI checks (when CI exists)

**Verification gate:** `pnpm install` + `pnpm dev` çalışıyor; `cd apps/api && uv run uvicorn main:app --reload` ayağa kalkıyor; `docker compose up` Postgres+Redis sağlıklı; `pnpm test` ve `pnpm typecheck` yeşil; CI bir PR'da geçiyor.

---

## Faz 2 (B) — Data Layer + Multi-Tenancy (⏸ Blocked)

**Spec/Plan:** Henüz yazılmadı.
Master plan §4.B'den özet:
- [ ] Supabase migrations (11 tablo)
- [ ] RLS policies (her tablo, `TO authenticated` + `with check`)
- [ ] Indexes (RLS sütunları + FK'lar)
- [ ] `provision-org-on-signup` Edge Function
- [ ] `npx supabase gen types typescript --linked > apps/web/src/lib/database.types.ts`
- [ ] BOLA isolation test (User A workspace ↛ User B token)

---

## Faz 3 (C) — Agent Core SDK (⏸ Blocked)

**Spec/Plan:** Henüz yazılmadı.
Master plan §4.C'den özet:
- [ ] C.1: SOLID protocols (LLMProvider, EmbeddingProvider, MemoryBackend, SkillProvider, AgentTool, Agent ABC)
- [ ] C.2: LangGraph entegrasyonu + PostgresSaver checkpoint
- [ ] C.3: OpenRouter LLM adapter + per-agent model + cost tracking + fallback chain
- [ ] C.4: Memory backend (cache + long-term, pgvector retrieval)
- [ ] C.5: Skill registry (DB + filesystem)
- [ ] C.6: Telemetry (LangSmith + OTel + Sentry + `agent_executions`)
- [ ] C.7: Tests (pytest-asyncio + Testcontainers Postgres+Redis)

---

## Faz 4 (D) — Crawl & Ingestion Pipeline (⏸ Blocked)

**Spec/Plan:** Henüz yazılmadı.
- [ ] D.1: Crawl4AI spider wrapper (sitemap + robots + rate limit)
- [ ] D.2: Schema.org + meta extractor
- [ ] D.3: Semantic chunker (~512 token)
- [ ] D.4: Modal BGE-M3 embedding service deploy
- [ ] D.5: pgvector insert (`embeddings` tablosu) + sparse hybrid
- [ ] D.6: Celery task `crawl_site(site_id)` + retry logic
- [ ] D.7: HTML snapshot → Supabase Storage `crawls/<site_id>/<hash>.html`

---

## Faz 5 (E) — v1 GEO Agent Suite (⏸ Blocked)

**Spec/Plan:** Her teknik için ayrı veya gruplanmış spec/plan.
- [ ] E.5: Question-Intent Targeting (Analyzer + Generator + skills)
- [ ] E.2: Structured Knowledge (Analyzer + Generator + skills)
- [ ] E.11: AI-Readable Formatting (Analyzer + Generator + skills)
- [ ] E.3: Entity-Based SEO (Analyzer + Generator + skills)
- [ ] E.4: Citation Optimization (Analyzer + Generator + skills)
- [ ] E.O: AnalysisOrchestrator LangGraph workflow (5 paralel + aggregate)
- [ ] E.P: RecommendationPrioritizer (impact × effort matrix)

---

## Faz 6 (F + G) — Dashboard + Auth (⏸ Blocked, paralel)

**F (dashboard):**
- [ ] (marketing) landing
- [ ] (auth) login / signup / accept-invite
- [ ] (app) dashboard / workspaces / sites / runs / pages / agents / settings
- [ ] Server Actions (addSite, triggerAnalysis, inviteMember, applyRecommendation)
- [ ] Supabase Realtime progress
- [ ] PDF report (white-label)
- [ ] Playwright E2E (10 golden rules)

**G (auth):**
- [ ] `provision-org-on-signup` Edge Function
- [ ] Invite flow
- [ ] Role enforcement (DB + API + UI 3 katman)
- [ ] 2FA (opsiyonel)
- [ ] Stripe (v1.5'e ertelenebilir)

---

## Faz 7 (H) — Observability + Ops (⏸ Blocked)

- [ ] LangSmith integration
- [ ] Sentry web + api
- [ ] OpenTelemetry FastAPI auto-instrument
- [ ] structlog (Python) + pino (Node)
- [ ] `/metrics` Prometheus + Grafana Cloud
- [ ] Health: `/health/live`, `/health/ready`
- [ ] Backup: daily auto + weekly pg_dump
- [ ] Runbook'lar (`docs/runbooks/`)

---

## Faz 8 — Closed Beta (⏸ Blocked)

- [ ] 3-5 ajansla onboarding
- [ ] Production deploy Hostinger KVM2 (Caddy + Docker Compose)
- [ ] DNS + SSL otomatize
- [ ] Cost monitoring (OpenRouter spend, Modal usage)
- [ ] Feedback loop + bugbash
- [ ] v1 launch decision

---

## Logbook (orkestratör tarafından append-only)

### 2026-05-13
- Planning oturumu tamamlandı (8 AskUserQuestion turu)
- Master plan onaylandı: `docs/plans/2026-05-13-master-plan.md`
- `C:\Users\iso\.claude\projects\C--aeogenerator\memory\` altında 5 memory dosyası yazıldı
- Proje CLAUDE.md, PROGRESS.md ve `aeogen-orchestrator` skill kuruldu
- Tam otonom modu seçildi
- **GitHub MCP** user scope'da kuruldu (npm `@modelcontextprotocol/server-github`)
- **Repo:** https://github.com/ismwolf/aoecreator (user: ismwolf, gh auth keyring)
- **Faz 1 (A) — Foundation bootstrap kısmı başladı:**
  - ✅ A.T1: `git init -b dev`
  - ✅ A.T2: `.gitignore` (Node + Python + IDE + project-specific)
  - ✅ Remote add origin
  - ✅ İlk commit `22daff1` (11 files, 2487 insertions) + push
  - ✅ Branch'ler: `dev` (default), `test`, `main` — hepsi push'lu
  - ✅ GitHub'da default branch `dev` olarak set edildi
- **Sonraki adım:** Faz 0 — `langchain-master` skill implementation
  (sonra Faz 1 A.T3 pnpm workspace skeleton)

### 2026-05-14
- **Agent fleet kuruldu (Opus)** — `C:\aeogenerator\.claude\agents\`:
  - `aeogen-orchestrator.md` (model: opus) — dispatcher agent
  - `aeogen-code-writer.md` (model: opus) — default implementation agent
  - `aeogen-code-reviewer.md` (model: opus, no Edit/Write tools) — verdict-only reviewer
- Orkestratör SKILL.md dispatch matrix güncellendi: implementation
  defaultu artık `aeogen-code-writer`, review defaultu `aeogen-code-reviewer`
- **A.T3 ✅ pnpm workspace skeleton** (smoke test):
  - Branch: `feature/A.T3-pnpm-workspace-skeleton`
  - Files: `pnpm-workspace.yaml` (`apps/web` + `packages/shared`),
    `package.json` (`pnpm@10.18.0`, Node ≥20.11, fan-out scripts)
  - Review: `superpowers:code-reviewer` → PASS (P2 packageManager fix
    applied — `10.0.0` → `10.18.0` for Corepack reproducibility)
- **NOT:** Custom aeogen-* agent'lar bu sessionda Agent tool listesine
  yüklenmedi (Claude Code agent'ları session başında okur). Bir sonraki
  session'da otomatik aktif olacak. Smoke test için review leg
  `superpowers:code-reviewer` ile çalıştırıldı.
- **Pending:** Commit + push to feature branch + PR to `dev`
  (kullanıcı onayı bekliyor — global CLAUDE.md "no auto-commit" kuralı)
- **Update (later same day):** Kullanıcı tam otonom commit+push+PR+merge
  yetkisi verdi (memory: `feedback_autonomous_git.md`).
- ✅ A.T3 PR #1 (`a83c37f`) → merged to dev (`ec6307c`)
- ✅ chore(orchestrator) direct push to dev (`5460244`) — agent fleet
  files + dispatch matrix + `.gitignore` unignore `.claude/agents/`
- **Faz 0 langchain-master skill (T1-T11) — paralel dispatch (general-purpose subagent):**
  - All 11 tasks PASS (T11 runtime checks deferred to live MCP invocation)
  - PR #2 → merged to dev (`02f6981`)
  - Skill now appears in Skill tool list: `Skill(skill="langchain-master", ...)`
- **A.T4 plan — paralel dispatch (Plan subagent):**
  - 7 sub-tasks plan: `docs/plans/2026-05-14-A.T4-nextjs-scaffold-plan.md`
  - 7 açık soru flag'lendi (Tailwind v4/v3, Vitest stub timing, route collision, CSP, Turbopack, typedRoutes)
  - PR #3 → merged to dev (`4de4103`)
- **A.T4 implementation ✅** (feature/A.T4-nextjs-scaffold):
  - T4.1 package shell, T4.2 ts/eslint/postcss, T4.3 env.ts (t3-env) ✅
  - T4.4 shadcn init — Tailwind **v4** path; CLI required `next.config.ts` first so T4.6 ran before T4.4 (minor reorder, no scope impact)
  - shadcn's new `base-nova` preset added `@base-ui/react`, `tw-animate-css` deps + a baseline `button.tsx` (auto-generated by init, not added manually — within plan scope)
  - T4.5 route groups: `(marketing)/page.tsx` → `/`, `(auth)/login/page.tsx`, `(app)/dashboard/page.tsx` (collision-safe; no root `app/page.tsx`)
  - T4.6 `next.config.ts` with HSTS, X-Content-Type-Options, Referrer-Policy, X-Frame-Options, Permissions-Policy, permissive CSP placeholder; `typedRoutes` moved from `experimental` to top-level per Next 15.5 deprecation
  - T4.7 verification: `pnpm -r typecheck` ✅ · `pnpm -r lint` ✅ · `pnpm -r build` ✅ (4 routes: `/`, `/dashboard`, `/login`, `/_not-found`) · `pnpm -r test` placeholder ✅ · `curl -I http://localhost:3001/` confirms all 6 security headers present
  - **Review (`superpowers:code-reviewer`):** CHANGES_REQUESTED
    - P1: build broke without `.env.local` — fixed by `.default("http://localhost:3000")` on the Zod schema in `src/lib/env.ts`. Re-verified env-less `pnpm -r build` PASS.
    - P2: shadcn `base-nova` preset accepted as new CLI default; documented in `apps/web/README.md`.
  - **PR #4** → merged to `dev` — 22 files / ~9k lines (incl. `pnpm-lock.yaml`)
- **Sıradaki:** A.T5 — `apps/api/` FastAPI 3.12 scaffold (plan henüz yazılmadı)

### 2026-05-15
- **A.T5 plan** — Plan subagent dispatch:
  - User confirmed **uv** (Astral) as Python package manager (vs poetry/hatch+pip-tools)
  - 7-task plan: `docs/plans/2026-05-15-A.T5-fastapi-scaffold-plan.md` (566 lines)
  - 7 open questions resolved by orchestrator defaults: ruff format only (no black); pre-commit deferred to A.T10; module-level `app` + factory both; monorepo invocation Option B (README-only, no root script changes); license UNLICENSED; CORS deferred to A.T8; .env precedence Next.js parity
  - Plan committed to `feature/A.T5-fastapi-scaffold` (`0e706cd`) + pushed
- **A.T5 implementation ✅** (aeogen-code-writer subagent):
  - T5.1 package shell + uv init, T5.2 ruff/mypy/pytest config block, T5.3 package skeleton (`__init__.py` + `py.typed`), T5.4 pydantic-settings parity for env.ts, T5.5 `create_app` factory + `/health/live` + `/health/ready`, T5.6 pytest-asyncio integration tests, T5.7 README polish + full gate
  - Deps pinned: fastapi `<0.116`, pydantic `<3`, uvicorn `<0.33`, ruff `<0.7`, mypy `<2`, pytest `<9`, pytest-asyncio `<0.25`, httpx `<0.28`
  - 13 files created under `apps/api/` (incl. `uv.lock`, 523 lines). No files outside `apps/api/` touched. `apps/api/` intentionally NOT in `pnpm-workspace.yaml`.
  - Gates verified: `uv sync` clean · `uv run ruff check .` 0 errors · `uv run ruff format --check .` 6 files formatted · `uv run mypy src` Success 3 files · `uv run pytest -v` 2 passed · `uv lock --check` exit 0 · live curl `/health/live` + `/health/ready` JSON OK · root `pnpm -r typecheck/lint/build` still green for `@aeogen/web`
- **Review (aeogen-code-reviewer subagent):** PASS — plan-conformance ✓, MUST/MUST NOT compliance ✓, no secrets, scope-fit clean (no Supabase/Celery/LangChain leakage), gates re-run match writer's claims
  - P2 nit (non-blocking): only happy-path tests; negative/edge case coverage deferred to first real-endpoint task
  - P3 nits: VIRTUAL_ENV host-shell warning (cosmetic); `dict[str, Any]` health return could tighten to `TypedDict` later
- **Sıradaki:** A.T6 — `packages/shared/` Pydantic + Zod parity schemas (plan TBD)

### 2026-05-16
- **A.T6 plan** — Plan subagent dispatch:
  - User confirmed **Zod-first + Pydantic codegen** strategy (vs Pydantic-first / manual / TypeBox)
  - 9-task plan: `docs/plans/2026-05-15-A.T6-shared-zod-pydantic-parity-plan.md` (650 lines)
  - 8 open questions resolved: Zod 4 bump (single workspace major), `pydantic_v2.BaseModel`, defer apps/api install to Faz 2 B, `.strict()` default, `z.iso.datetime()`, default UUID chain, FAIL-on-drift, build-script-only (hooks to A.T10/T12)
  - Plan committed to `feature/A.T6-shared-zod-pydantic-parity` (`66b8725`)
- **A.T6 implementation ✅** (aeogen-code-writer subagent):
  - T6.1 package shell, T6.2 apps/web zod 3→4 bump (no env.ts breakage), T6.3 TS toolchain, T6.4 Site + Workspace Zod schemas, T6.5 emit-json-schema.ts with `stripRedundantPatterns` + `collapseNullableAnyOf` rewriters, T6.6 pyproject.toml + codegen + check-drift scripts, T6.7 first codegen run (committed `python/aeogen_shared/{site,workspace}.py`), T6.8 parity tests (3 Vitest + 3 pytest against same fixtures), T6.9 README polish + full gate
  - 26 files created under `packages/shared/`, 2 modified (`apps/web/package.json`, `pnpm-lock.yaml`)
  - Justified deviations from plan: added `--use-annotated` (mypy strict needs it for `constr(...)`); custom `stripRequiredNullableDefault()` post-process (preserves Zod `.nullable()` required-semantics); JSON Schema rewriters bridge Zod 4 ↔ datamodel-code-generator output quirks
  - Generated `Site` shape: `id: UUID, workspace_id: UUID, url: AnyUrl, default_language: Literal[...], sector: Annotated[str | None, Field(min=1, max=120)]`; `model_config = ConfigDict(extra="forbid")`. `Workspace` similar.
  - Gates verified: pnpm build ✓ · vitest 3 passed · ruff ✓ · mypy 3 files Success · pytest 3 passed · check:drift OK · pnpm -r typecheck/lint/build/test ✓ · apps/api still 2 passed
- **Review (aeogen-code-reviewer subagent):** PASS — plan-conformance ✓, deviations justified, cross-language parity invariant confirmed (omitted-required-nullable fails on BOTH sides; explicit-null accepted on BOTH; extra key rejected on BOTH), drift detection genuinely catches real drift (reviewer modified site.ts, ran check:drift → exit 1, reverted)
  - P2: `--strip-default-none` codegen flag redundant today + future-risk when first `z.optional()` field lands. **Fix shipped:** flag removed from `codegen-pydantic.ts`, build re-run produces identical Python, all gates re-verified
  - P3 follow-ups deferred to A.T10/T11: regex escape `fieldName` in stripRequiredNullableDefault, eliminate Node 22 `[DEP0190]` warning (spawn `pnpm.cmd` with shell:false on win32), extend `collapseNullableAnyOf` for 3-way unions when needed, lock omitted-required-nullable edge cases into committed parity tests
- **Sıradaki:** A.T7 — `infra/docker-compose.dev.yml` (Postgres + Redis + Adminer)
- **A.T7 plan-only PR** — Plan dispatch + decisions:
  - User locked: `supabase/postgres:15.8.1.060` + bind mounts under `./.docker-data/` + no admin UI + hybrid dev (apps stay on host)
  - 6-task plan written: `docs/plans/2026-05-16-A.T7-docker-compose-dev-plan.md` (501 lines, 12 open questions resolved)
  - Plan committed to `feature/A.T7-docker-compose-dev` (`c70e845`) + push
- **A.T7 implementation ⏸ BLOCKED** (aeogen-code-writer subagent pre-flight):
  - Docker Desktop yüklü değil (`docker info` → command not found)
  - WSL2 distro yok (`wsl --list --verbose` → "no installed distributions")
  - Code-writer correctly STOPPED per pre-flight rule (no speculative file writes, no verification bypass)
  - **User choice:** skip ahead to A.T8 (Supabase Cloud managed Postgres makes local Docker dev optional for now)
  - Plan stays valid + merged for future resume when Docker installed
- **Sıradaki:** A.T8 — `supabase/config.toml` + Supabase Cloud link + types codegen
- **A.T8 plan** — Plan subagent dispatch + user-locked decisions:
  - User confirmed: project ref `ngjlxlkdfgfhiookndpl`, MCP-first workflow ("tablo açacaksın"), MCP URL literal `https://mcp.supabase.com/mcp?project_ref=ngjlxlkdfgfhiookndpl` (no `read_only`/`features` params), `supabase login` not yet run
  - 8-task plan: `docs/plans/2026-05-16-A.T8-supabase-link-plan.md` (~640 lines)
  - Plan PR #8 (autonomous merge during "Continue from where you left off"): plan + `.mcp.json` + `.mcp.json.example`
- **A.T8 implementation ✅** (aeogen-code-writer + manual URL pin):
  - T8.1 supabase@^2.98.2 CLI as workspace devDep
  - T8.2 `supabase init` scaffold: `supabase/config.toml` (`project_id = "aeogen"`), `.gitignore`, `migrations/.gitkeep`, `README.md` (MCP-first workflow)
  - T8.3 `supabase login` + `link` **DEFERRED** to user-interactive post-merge (browser OAuth)
  - T8.4 `apps/web/src/lib/database.types.ts` hand-authored STUB (~110 lines, mirrors CLI empty-schema output, drop-in replaceable)
  - T8.5 Runtime deps: web `@supabase/ssr@0.10.3` + `@supabase/supabase-js@2.105.4`; api `supabase==2.30.0` (`>=2.6,<3` pinned)
  - T8.6 Env schemas: web `env.ts` t3-env client/server split with regex `sb_publishable_*` / `sb_secret_*`; api `Settings` with `HttpUrl` + `SecretStr` + `field_validator`; `.env.example` files extended; `conftest.py` env injection at MODULE TOP (lru_cache ordering)
  - T8.7 `.mcp.json` URL: user's literal `?project_ref=ngjlxlkdfgfhiookndpl` only (no params) — pinned manually after autonomous run
  - T8.8 `.gitignore` extensions (supabase scratch + `.mcp.local.json`); `package.json` `pnpm.onlyBuiltDependencies` removed (duplicate of `pnpm-workspace.yaml`)
  - Justified deviations: `onlyBuiltDependencies` in pnpm-workspace.yaml (pnpm 10 canonical); manual one-time `node scripts/postinstall.js` for supabase.exe fetch; `mypy # type: ignore[call-arg]` on `Settings()` (pydantic-settings + mypy strict false-positive); conftest env at module top (not fixture) for lru_cache safety
  - Gates verified: typecheck/lint/build green for `@aeogen/web` (with placeholder env vars); apps/api 2 tests passed; packages/shared 3+3 tests passed; check:drift OK; no secret leak; supabase 2.98.2 CLI version confirmed
- **Review (aeogen-code-reviewer subagent):** PASS — plan-conformance ✓ (T8.3 + real types codegen marked "deferred per plan"), MUST/MUST NOT ✓, stub quality "high-fidelity, drop-in replaceable", no scope creep
  - P3 #1: `onlyBuiltDependencies` duplicate (fixed before commit — removed from `package.json`)
  - P3 #2: no negative-path tests for new env validators (deferred to A.T9/A.T10)
  - P3 #3: `import 'server-only'` discipline acknowledged for Faz 2 G consumers
- **Post-merge user actions REQUIRED:**
  1. `pnpm exec supabase login` (browser OAuth)
  2. `pnpm exec supabase link --project-ref ngjlxlkdfgfhiookndpl`
  3. Restart Claude Code so `.mcp.json` loads `mcp__supabase__*` tools
  4. Regenerate `apps/web/src/lib/database.types.ts` via MCP or CLI `--linked`
- **Sıradaki:** A.T9 — env validation expansion (DATABASE_URL, REDIS_URL, OPENROUTER_API_KEY, gen-types CI)
