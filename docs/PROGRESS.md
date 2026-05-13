# aeogenerator — Implementation Progress

> Bu dosya `aeogen-orchestrator` skill tarafından her milestone sonrası
> güncellenir. Manuel düzenleme yapılırsa orkestratör konfliği fark
> eder ve kullanıcıya sorar.

**Son güncelleme:** 2026-05-13 (git init + 3 branch + push + GitHub MCP
kurulumu tamamlandı; Faz 0 ve Faz 1 A'nın bazı task'ları bitti)
**Mevcut faz:** Faz 0 — langchain-master skill (⏳ Pending) + Faz 1 A
(🔄 In progress: T3 sırada)
**Mevcut alt-proje:** A — Foundation Bootstrap
**Mevcut task:** A.T3 — pnpm workspace skeleton (sıradaki) **VEYA**
Faz 0 T1 — langchain-master skill scaffold (bağımsız, paralel
yapılabilir)
**Sıradaki milestone:** Faz 0 complete (~1 gün)
**Toplam ilerleme:** 5 / ~70 task (%7)

## Faz durumları

| # | Faz | Durum | Süre tahmini | Notlar |
|---|---|---|---|---|
| 0 | langchain-master skill | ⏳ Pending | 1 gün | Plan hazır: `docs/superpowers/plans/2026-05-13-langchain-master-skill.md` (11 task) |
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

## Faz 0 — `langchain-master` Skill (⏳ Pending)

**Spec:** `docs/superpowers/specs/2026-05-13-langchain-master-skill-design.md`
**Plan:** `docs/superpowers/plans/2026-05-13-langchain-master-skill.md`
**Hedef:** Senior LangChain Python advisor skill — Claude Code
geliştirici (insan + AI) için. Production agent DEĞİL.

- [ ] T1: Skill directory scaffold (`memory/`, `references/`, `_index.json`)
- [ ] T2: SKILL.md frontmatter + ToC
- [ ] T3: Persona section
- [ ] T4: 6-step Workflow section (normalize → check refs → check
      memory → MCP query → promotion check → return)
- [ ] T5: Topic-key normalization rules
- [ ] T6: Cache file formats (`_index.json`, `memory/<key>.md`)
- [ ] T7: Cache management (TTL=30d, promotion @ hit_count≥3, decline)
- [ ] T8: Error recovery (corrupted index, missing memory, MCP fail)
- [ ] T9: Output format template
- [ ] T10: README.md overview
- [ ] T11: End-to-end manual verification (8 dry-run sub-tasks)

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
- [ ] T3: pnpm workspace skeleton (`pnpm-workspace.yaml`, `package.json`)
- [ ] T4: `apps/web/` Next.js 15 scaffold (App Router, TS strict, Tailwind, shadcn init)
- [ ] T5: `apps/api/` FastAPI 3.12 scaffold (uv veya poetry, ruff, black, mypy strict)
- [ ] T6: `packages/shared/` Pydantic + Zod parity schemas (JSON Schema bridge)
- [ ] T7: `infra/docker-compose.dev.yml` (Postgres + Redis + Adminer)
- [ ] T8: `supabase/config.toml` + Supabase Cloud projesi link
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
