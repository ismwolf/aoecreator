# aeogenerator — Multi-Agent AEO/GEO SaaS High-Level Architecture Plan

**Tarih:** 2026-05-13
**Durum:** Plan (Brainstorming/Plan-mode kapısı geçildi, ExitPlanMode bekliyor)
**Proje konumu:** `C:\aeogenerator`
**Plan modu plan dosyası:** `C:\Users\iso\.claude\plans\sen-senor-bir-aeo-noble-liskov.md` (bu dosya)
**Sahibi:** ismailmardin10@gmail.com

> Bu dosya **bütün-sistem yüksek-seviye mimari planı**dır. Her alt-proje
> (A-H) için ayrı bir `docs/specs/<tarih>-<slug>-spec.md` ve
> `docs/plans/<tarih>-<slug>-plan.md` dökümü gelecek (CLAUDE.md kuralı).
> Bu dosya kapsamı, kontratları, sıralamayı tutar.

---

## 1. Context — neden bu proje

E-ticaret işletmeleri için **AEO (Answer Engine Optimization)** ve **GEO
(Generative Engine Optimization)** analizi yapan, sonuçları gösteren,
gerekli aksiyonları **ajanlara bölüp asenkron çalıştıran**, her ajanın
kendi memory + skill setine sahip olduğu, periyodik güncellemelerle
besli bir SaaS platformu.

**Birincil müşteri:** Dijital ajanslar. Her ajans 5-50 e-ticaret
müvekkili yönetir. ARPU $300-2000/ay.

**Çekirdek değer önerisi:** ChatGPT, Claude, Gemini, Perplexity, AI
Overviews gibi cevap motorlarında müşteri markasının cite edilme
oranını ölçülebilir şekilde artırmak.

**12 GEO/AEO tekniği** (Gereklilikler 1-2 resimlerinden):

| #   | Teknik                     | v1     | Not                                  |
| --- | -------------------------- | ------ | ------------------------------------ |
| 1   | Semantic Authority         | v2     | Topic-cluster gap analysis           |
| 2   | Structured Knowledge       | **v1** | 40-word rule, table/list             |
| 3   | Entity-Based SEO           | **v1** | spaCy + BGE-M3 entity gap            |
| 4   | Citation Optimization      | **v1** | Academic + reliable source insertion |
| 5   | Question-Intent Targeting  | **v1** | FAQ schema, prompt-matched Q         |
| 6   | Data-Rich Content          | v2     | Chart, benchmark, stats              |
| 7   | Knowledge Graph Alignment  | v2     | Wikidata + LLM internal graph        |
| 8   | Multi-Platform Presence    | v2     | YouTube/Medium/GitHub dist.          |
| 9   | Author Authority (E-E-A-T) | v2     | Author profile, LinkedIn             |
| 10  | Open Data / API Exposure   | v2     | RSS, JSON-LD, GitHub repo            |
| 11  | AI-Readable Formatting     | **v1** | H1/H2/H3 disiplini                   |
| 12  | Contextual Brand Embedding | v2     | Brand voice tuning                   |

**v1 hedef ROI (2026 araştırma bulguları):**

- FAQ schema + prompt-matched Q ⇒ AI extraction **3.1x**
- 40-word concise answer block ⇒ AI extraction **2.7x**
- Citation insertion ⇒ visibility **+30%**
- Statistics insertion ⇒ visibility **+30%**
- Expert quote insertion ⇒ visibility **+41%** (Princeton GEO study)
- Freshness: 2026'da AI Overviews citation'larının %85'i son 2 yıl

---

## 2. Mimari kararlar özeti (lock-in)

| Karar                  | Seçim                                                          | Q#              |
| ---------------------- | -------------------------------------------------------------- | --------------- |
| Planlama yaklaşımı     | Top-down full mimari                                           | Q1              |
| Hedef kitle            | Ajans / agency tool (org→workspace→site)                       | Q2              |
| Web stack              | Next.js 15 (App Router) + TS strict + Tailwind + shadcn/ui     | Q3              |
| Auth + DB + Storage    | Supabase Cloud (auth + Postgres + pgvector + Storage + RLS)    | Q3              |
| Agent backend          | Python 3.12 + FastAPI + LangChain + LangGraph + LangSmith      | (mevcut spec)   |
| LLM gateway            | OpenRouter (Claude, OpenAI, Gemini, Grok, Perplexity)          | (gereksinim)    |
| Task queue + scheduler | Celery + Redis + Celery Beat (periyodik)                       | Q4              |
| LangGraph persistence  | Postgres checkpoint (Supabase Postgres)                        | Q4              |
| Observability          | LangSmith + Sentry + OpenTelemetry                             | (best practice) |
| Crawler                | Crawl4AI (async Playwright, schema.org parse)                  | Q5              |
| Vector DB              | pgvector (Supabase Postgres)                                   | Q6              |
| Embedding model        | BGE-M3 self-host (Modal serverless GPU)                        | Q6              |
| v1 MVP scope           | 5 GEO teknik (2, 3, 4, 5, 11)                                  | Q7              |
| Hosting                | Hibrit: Hostinger KVM2 (app) + Supabase Cloud + Modal          | Q8              |
| Branş dili             | UI: TR (i18n: EN v1.5), kod/log/commit: EN                     | (default)       |
| Source control         | git (bu proje henüz init değil — kullanıcı `git init` yapacak) | —               |

---

## 3. Sistem topolojisi (high-level)

```
                       ┌─────────────────────────┐
                       │  Ajans kullanıcısı      │
                       │  (browser, dashboard)   │
                       └────────────┬────────────┘
                                    │ HTTPS
                       ┌────────────▼─────────────┐
                       │  Next.js 15 (Vercel ya   │
                       │  da KVM2'de PM2/Node)    │
                       │  - Marketing             │
                       │  - Auth (Supabase SSR)   │
                       │  - Dashboard             │
                       │  - Reports / PDF gen     │
                       │  - Server Actions (BFF)  │
                       └──┬──────────────┬────────┘
                          │              │
              Supabase SSR│              │REST /SSE
              getClaims() │              │(internal)
                          ▼              ▼
            ┌─────────────────┐   ┌────────────────────┐
            │  Supabase       │   │  FastAPI Gateway   │
            │  (Cloud)        │   │  (KVM2, Docker)    │
            │  - Auth         │◄──┤  - /agents/run     │
            │  - Postgres     │   │  - /crawl/start    │
            │  - pgvector     │   │  - /reports/gen    │
            │  - RLS          │   │  - SSE stream      │
            │  - Storage      │   └─────────┬──────────┘
            │  - Realtime     │             │
            └────────▲────────┘             │ enqueue
                     │                      ▼
                     │            ┌─────────────────────┐
                     │            │  Redis (KVM2)       │
                     │            │  - Celery broker    │
                     │            │  - Cache / lock     │
                     │            │  - Rate limit       │
                     │            └─────────┬───────────┘
                     │                      │
                     │              ┌───────┴────────┐
                     │              ▼                ▼
                     │   ┌─────────────────┐  ┌─────────────────┐
                     │   │ Celery workers  │  │ Crawl4AI worker │
                     │   │ (KVM2, x2)      │  │ (KVM2, x1)      │
                     │   │ - LangGraph     │  │ - Playwright    │
                     │   │   agent runs    │  │ - Schema parse  │
                     │   │ - OpenRouter    │  │ - Sitemap walk  │
                     │   │   LLM calls     │  └────────┬────────┘
                     │   └────────┬────────┘           │
                     │            │                    │ HTML/JSON
                     │            │ HTTPS              ▼
                     │            ▼              ┌──────────┐
                     │   ┌─────────────────┐    │ Supabase │
                     │   │ Modal           │    │ Storage  │
                     │   │ (serverless GPU)│    │ (HTML    │
                     │   │ - BGE-M3 embed  │    │ snap)    │
                     │   │ - /embed batch  │    └──────────┘
                     │   └─────────────────┘
                     │
                     │            ┌──────────────────────┐
                     └────────────┤ Celery Beat (KVM2)   │
                                  │ - weekly recrawl     │
                                  │ - daily score refresh│
                                  │ - cache eviction     │
                                  └──────────────────────┘

External LLMs (OpenRouter):
  Claude Sonnet 4.5 (generation)
  GPT-5 / GPT-4o (analysis)
  Gemini 2.5 Pro (multimodal/long)
  Perplexity Sonar (research + cite)
  Grok 4 (current trends, opsiyonel)
```

**Akış kısa hikayesi:**

1. Ajans kullanıcısı dashboard'dan müvekkil sitesini ekler → Next.js
   Server Action → Supabase `sites` tablosuna insert (RLS ile workspace
   izolasyonu).
2. UI "analyze now" tetikleyici → Next.js BFF → FastAPI Gateway
   `/agents/run` (auth = Supabase JWT, ownership check).
3. FastAPI bir `analysis_run` kaydı oluşturur (Postgres), Celery'ye
   parent task enqueue eder.
4. Parent task: Crawl4AI worker'a fan-out (sitemap → top N page →
   schema parse → Supabase Storage'a HTML snapshot, Postgres'e parsed
   content).
5. Sonra: her v1 tekniği için Analyzer LangGraph workflow Celery task
   olarak fan-out edilir. Analyzer Modal'a embed isteği gönderir
   (BGE-M3), OpenRouter'a LLM isteği gönderir, skor + öneriler üretir.
6. Sonuçlar Postgres'e yazılır. Supabase Realtime ile UI'a progress
   stream.
7. Generator (opt-in, UI'dan "fix" düğmesi) ⇒ önerilen HTML/JSON-LD
   diff üretir, draft olarak workspace'e kaydedilir.
8. Celery Beat haftalık recrawl + günlük score refresh çalıştırır.

---

## 4. 8 alt-proje (A-H) — kapsam ve sıra

Her alt-proje kendi `spec → plan → implement → verify` döngüsüne
girecek. Sıra **dependency-driven**.

### A. Foundation & Repo bootstrap (1 hafta)

- `git init` + Conventional Commits + Husky
- Monorepo veya iki-repo karar (öneri: pnpm workspace monorepo:
  `apps/web/` Next.js, `apps/api/` FastAPI, `packages/shared/` zod
  şemaları, `infra/` Docker Compose)
- `.editorconfig`, `Directory.Build.props` muadili Python için
  `pyproject.toml` + ruff + black + mypy strict
- `@t3-oss/env-nextjs` (web) + `pydantic-settings` (api) env validation
- `gitleaks` pre-commit
- GitHub Actions: lint/test/typecheck CI
- `infra/docker-compose.dev.yml`: Postgres + Redis + Adminer
- Supabase Cloud projesi oluştur, local CLI ile migration link
- **Kritik dosyalar:**
  - `apps/web/` (Next.js scaffold)
  - `apps/api/` (FastAPI scaffold)
  - `packages/shared/` (Pydantic + Zod ortak şemalar — JSON Schema
    bridge ile)
  - `infra/docker-compose.dev.yml`
  - `supabase/migrations/`
  - `.github/workflows/ci.yml`

### B. Data layer & multi-tenancy (1 hafta)

- Supabase migration'lar (CLI üzerinden):
  - `organizations` (ajans), `org_members` (rol: owner/admin/member)
  - `workspaces` (müvekkil), `workspace_members` (read-only viewer
    dahil)
  - `sites` (URL, language, sector)
  - `pages` (site_id, url, last_crawled_at, html_path, parsed_content)
  - `analysis_runs` (workspace, site, status, kicked_by, started_at)
  - `agent_executions` (run_id, agent_name, technique_id, status, input,
    output, score, llm_cost, duration_ms)
  - `scores` (page_id, technique_id, score, prev_score, recommendation)
  - `agent_memory` (agent_name, scope=global/workspace, key, value,
    cached_at)
  - `agent_skills` (agent_name, skill_key, content, source)
  - `embeddings` (page_id, chunk_id, content, embedding vector(1024),
    embedding_sparse jsonb) — pgvector + sparse hybrid
  - `audit_log` (org_id, actor, action, resource, ts)
- **RLS politikaları:** her tabloda
  - `TO authenticated`
  - `using ((select auth.jwt() -> 'app_metadata' ->> 'org_id')::uuid =
organization_id)` veya `workspace_id IN
(select unnest(string_to_array(auth.jwt() ->
'app_metadata' ->> 'workspace_ids', ',')::uuid[]))`
- Index'ler: her RLS sütununa + sık sorgulanan FK'lara
- `auth.jwt() -> 'app_metadata' ->> 'org_id'` claim'i kullanıcı
  organizasyona katıldığında `auth.users.app_metadata` üzerinden
  service-role API ile set edilir (Edge Function).
- `npx supabase gen types typescript --linked > apps/web/src/lib/database.types.ts`
- **Kritik dosyalar:**
  - `supabase/migrations/0001_init.sql` ... vs.
  - `apps/web/src/lib/dal/` (Data Access Layer, server-only)
  - `apps/api/src/aeogen/db/` (asyncpg + SQLAlchemy 2.0 async)

### C. Agent Core SDK (2 hafta — alt-projelerden en büyüğü)

**Amaç:** Tüm GEO agent'larının üzerine inşa edileceği base SDK. SOLID
prensiplerine bağlı, swap-able LLM provider, swap-able memory backend,
skill registry, structured output, retry/timeout, telemetry.

#### C.1 — Soyut katmanlar (interface-first, SOLID)

```python
# aeogen.agents.core.protocols

class LLMProvider(Protocol):
    async def chat(self, messages: list[Message], **opts) -> LLMResponse: ...
    async def stream(self, messages: list[Message], **opts) -> AsyncIterator[LLMChunk]: ...

class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[Vector]: ...

class MemoryBackend(Protocol):
    async def get(self, agent: str, scope: str, key: str) -> Any | None: ...
    async def set(self, agent: str, scope: str, key: str, value: Any, ttl: int | None) -> None: ...
    async def search(self, agent: str, scope: str, query: str, k: int) -> list[MemoryHit]: ...

class SkillProvider(Protocol):
    async def get_skill(self, agent: str, skill_key: str) -> Skill | None: ...
    async def list_skills(self, agent: str) -> list[Skill]: ...

class AgentTool(Protocol):
    name: str
    schema: type[BaseModel]
    async def run(self, input: BaseModel, ctx: AgentContext) -> Any: ...

class Agent(ABC):
    name: ClassVar[str]
    technique_id: ClassVar[int | None]  # 1-12, None for Orchestrator
    kind: ClassVar[Literal["analyzer", "generator", "orchestrator"]]
    default_llm: ClassVar[str]  # OpenRouter model id

    @abstractmethod
    async def run(self, input: AgentInput, ctx: AgentContext) -> AgentOutput: ...
```

#### C.2 — LangGraph entegrasyonu

- Her agent içeride **kendi mini LangGraph workflow'una** sahip
  olabilir (Researcher → Analyzer → Critic → Output node'ları).
- Üst-seviye `AnalysisOrchestrator` da bir LangGraph workflow'udur
  (her teknik agent'ı paralel node, sonra aggregate).
- LangGraph state: `Postgres checkpoint saver` (`PostgresSaver`),
  Supabase Postgres'te (ayrı schema: `langgraph`).

#### C.3 — OpenRouter LLM adaptörü

- `OpenRouterLLM(LLMProvider)` — `openai` SDK uyumlu base_url
  override.
- Per-agent model override (`agent.default_llm = "anthropic/claude-sonnet-4.5"`).
- Cost tracking: her çağrı sonrası `agent_executions.llm_cost` güncelle.
- Token budget guard: prompt + max output > 32k ise auto-summarize.
- Fallback chain (örn. Claude rate-limit → GPT-4o → Gemini Flash).

**Default model matrix (öneri, değiştirilebilir):**

| Agent kindi                           | Default model                 | Alternatif                |
| ------------------------------------- | ----------------------------- | ------------------------- |
| Crawl summary / classification        | `openai/gpt-4o-mini`          | `google/gemini-2.0-flash` |
| Entity extraction                     | `openai/gpt-4o-mini`          | spaCy `tr_core_news_lg`   |
| Question-intent analyzer              | `anthropic/claude-sonnet-4.5` | `openai/gpt-5`            |
| FAQ generator                         | `anthropic/claude-sonnet-4.5` | `openai/gpt-5`            |
| Citation research                     | `perplexity/sonar-large`      | —                         |
| Structured knowledge gen              | `anthropic/claude-sonnet-4.5` | `openai/gpt-5`            |
| AI-readable formatter                 | `openai/gpt-4o-mini`          | `google/gemini-2.0-flash` |
| Heavy reasoning (Orchestrator critic) | `anthropic/claude-opus-4`     | `openai/o3`               |
| Multimodal (chart parse) v2           | `google/gemini-2.5-pro`       | —                         |

#### C.4 — Memory backend (langchain-master patternının genelleştirilmesi)

İki katman:

- **Cache memory** (`scope=cache`): TTL'li, MCP/LLM çağrı sonuçları,
  Supabase `agent_memory` tablosu. Promotion mekaniği opsiyonel
  (langchain-master skill'inden devralındı).
- **Long-term memory** (`scope=long_term`): vektörel, pgvector
  üzerinde, agent başına ayrı namespace. Konuşma özetleri, müşteri
  tercihleri, geçmiş içerik desenleri.

Backend swap'lanabilir: `PostgresMemoryBackend`, `RedisMemoryBackend`
(test). Default: Postgres.

#### C.5 — Skill registry

- Her agent'ın `skills/` klasörü: `system_prompt.md`, `examples.md`,
  `playbook_*.md`, `policy.md`.
- Skill provider önce DB (`agent_skills` tablosu — runtime override),
  sonra filesystem'den okur.
- `langchain-master` skill bu sistemin **özel bir agent skill'idir**
  (kendi `references/`, `memory/` cache mekaniği zaten tasarlanmış —
  `docs/superpowers/specs/2026-05-13-langchain-master-skill-design.md`).

#### C.6 — Telemetry

- LangSmith trace decorator her agent.run'a.
- OpenTelemetry span; FastAPI middleware.
- Sentry exception capture.
- `agent_executions` tablosuna her run için: input hash, output hash,
  token in/out, cost USD, duration ms, success/fail.

#### C.7 — Tests

- `pytest` + `pytest-asyncio`
- Her agent için: happy path + LLM mock + 1 edge case + 1 fail case
- LangGraph workflow için: state transition unit test
- Testcontainers: Postgres + Redis için integration test

**Kritik dosyalar (C alt-projesi):**

- `apps/api/src/aeogen/agents/core/protocols.py`
- `apps/api/src/aeogen/agents/core/base.py`
- `apps/api/src/aeogen/agents/core/llm.py` (OpenRouter)
- `apps/api/src/aeogen/agents/core/memory.py`
- `apps/api/src/aeogen/agents/core/skills.py`
- `apps/api/src/aeogen/agents/core/orchestrator.py`
- `apps/api/src/aeogen/agents/core/telemetry.py`
- `apps/api/src/aeogen/agents/skills/<agent_name>/system_prompt.md`
- `apps/api/tests/agents/...`

### D. Crawl & Ingestion pipeline (1 hafta)

- `crawl_site(site_id)` Celery task → Crawl4AI ile sitemap.xml + robots
- Top-N page öncelik (homepage, kategori, ürün, blog)
- Per-page: HTML snapshot → Supabase Storage `crawls/<site_id>/<hash>.html`,
  parsed content (markdown) + extracted schema.org + meta + canonical
  → Postgres `pages` tablosu
- Content chunking (semantic, ~512 token) → Modal embed batch →
  pgvector insert (`embeddings`)
- Rate-limit per domain (Redis lock, 1 req/s default, robots.txt
  Crawl-Delay'e saygı)
- Bot detection / fail handling: retry with backoff, sonra failure
  marker
- **Kritik dosyalar:**
  - `apps/api/src/aeogen/crawl/spider.py` (Crawl4AI wrapper)
  - `apps/api/src/aeogen/crawl/parser.py` (schema.org + meta extract)
  - `apps/api/src/aeogen/crawl/chunker.py` (semantic chunk)
  - `apps/api/src/aeogen/crawl/embedder.py` (Modal client)
  - Modal app: `infra/modal/embedding_service.py` (BGE-M3 FastAPI
    endpoint)

### E. v1 GEO Agent Suite — 5 teknik × Analyzer+Generator (3 hafta)

Her teknik için aynı şablon:

- `<Technique>Analyzer(Agent)` — sayfayı al, skoru üret, gap listesi
- `<Technique>Generator(Agent)` — gap listesinden öneri/diff üret

#### v1 ajanları:

| #   | Teknik                 | Analyzer çıktı                                                       | Generator çıktı                                                            |
| --- | ---------------------- | -------------------------------------------------------------------- | -------------------------------------------------------------------------- |
| 5   | Question-Intent        | Soru-cevap kapsamı skor + missing Q listesi (LLM ile prompt-matched) | FAQ schema JSON-LD + HTML FAQ block (40-word rule)                         |
| 2   | Structured Knowledge   | Table/list/snippable block skoru                                     | Markdown table + bulleted list + 40-word summary block                     |
| 11  | AI-Readable Formatting | H1/H2/H3 hiyerarşi skoru, paragraf uzunluğu, list-vs-prose oranı     | Yeniden yapılandırılmış başlık ağacı + paragraph chunk                     |
| 3   | Entity-Based SEO       | Sayfada eksik entity skoru (BGE-M3 + spaCy NER + LLM cross-ref)      | Önerilen entity insertion + internal-link önerisi                          |
| 4   | Citation Optimization  | Mevcut citation density skoru                                        | Perplexity Sonar ile bulunan akademik + güvenilir kaynak insertion önerisi |

Bunlara ek:

- `AnalysisOrchestrator` — LangGraph workflow, 5 Analyzer'ı paralel
  çalıştırır, sonuçları aggregate eder, score card üretir.
- `RecommendationPrioritizer` (lightweight LLM) — Gap'leri impact ×
  effort matrisinde sıralar.

**Kritik dosyalar:**

- `apps/api/src/aeogen/agents/question_intent/analyzer.py`
- `apps/api/src/aeogen/agents/question_intent/generator.py`
- `apps/api/src/aeogen/agents/question_intent/skills/system_prompt.md`
- ... (her 5 teknik için)
- `apps/api/src/aeogen/agents/orchestrator/workflow.py`

### F. Management Panel (Next.js dashboard) (2 hafta)

- App Router, RSC default, `"use client"` leaf
- Routes:
  - `(marketing)/` — landing
  - `(auth)/login`, `(auth)/signup`, `(auth)/accept-invite`
  - `(app)/dashboard` — org overview
  - `(app)/workspaces/[id]` — workspace dashboard
  - `(app)/workspaces/[id]/sites/[siteId]` — site detail
  - `(app)/workspaces/[id]/sites/[siteId]/runs/[runId]` — analysis report
  - `(app)/workspaces/[id]/sites/[siteId]/pages/[pageId]` — page detail
  - `(app)/agents` — agent registry + status
  - `(app)/settings/team`, `(app)/settings/billing`,
    `(app)/settings/branding` (white-label)
- Server Actions: `addSite`, `triggerAnalysis`, `inviteMember`,
  `applyRecommendation` (Pydantic→Zod parity ile validation)
- Supabase SSR: `@supabase/ssr`, `getClaims()`, cookies HttpOnly
- Real-time progress: Supabase Realtime kanalı (`analysis_runs:run_id`)
- PDF rapor generation: Next.js Route Handler + `@react-pdf/renderer`
  veya Playwright print-to-PDF (Celery worker'da)
- White-label: workspace.branding (logo, brand color, custom domain v2)
- shadcn/ui + Tailwind
- TanStack Table for bulk site list
- E2E (Playwright): 10-golden-rules

### G. Auth & Org provisioning + Roles (1 hafta — F'yle paralel)

- Supabase Auth: email+password, magic link, OAuth (Google) opsiyonel
- Edge Function: `provision-org-on-signup`
  - Yeni user → `organizations` insert → user'ı `org_members` owner
    olarak ekle → `app_metadata.org_id, role, workspace_ids` set
- Invite flow: org admin → email invite → invited user signup → claim
- Role enforcement:
  - DB seviyesi: RLS predicates
  - API seviyesi: FastAPI dependency `require_role(["owner","admin"])`
  - UI seviyesi: hide buttons (cosmetic only — DB authoritative)
- 2FA opsiyonel (`auth.mfa`)
- Billing: Stripe entegrasyonu (v1.5'e bırakılabilir; v1'de manual
  trial)

### H. Observability + Ops (sürekli, 1 hafta initial)

- LangSmith: tüm agent run'ları trace
- Sentry: web + api error tracking
- OpenTelemetry: FastAPI auto-instrument, custom span per agent
- Logging: structured JSON, `structlog` (Python), `pino` (Node)
- Metrics: `/metrics` Prometheus endpoint, Grafana Cloud free tier
- Health: `/health/live`, `/health/ready`
- Backup: Supabase Cloud otomatik daily backup + haftalık
  `pg_dump` Supabase Storage'a kopyası
- Runbook: `docs/runbooks/` (incident, restore, scaling)

---

## 5. Veri modeli (özet, detay B alt-projesinde)

```
organizations (id, name, slug, branding jsonb, created_at)
  └── org_members (org_id, user_id, role enum)
  └── workspaces (id, org_id, name, slug, created_at)
        └── workspace_members (workspace_id, user_id, role)
        └── sites (id, workspace_id, url, sector, default_language)
              └── pages (id, site_id, url, html_path, parsed_content,
                         last_crawled_at, content_hash)
                    └── embeddings (id, page_id, chunk_id, content,
                                    embedding vector(1024),
                                    embedding_sparse jsonb)
                    └── scores (id, page_id, technique_id, score,
                                prev_score, recommendations jsonb,
                                run_id)
              └── analysis_runs (id, workspace_id, site_id, status,
                                 kicked_by, started_at, finished_at,
                                 total_cost_usd)
                    └── agent_executions (id, run_id, agent_name,
                                          technique_id, status, input,
                                          output, score, llm_cost,
                                          duration_ms, trace_id)
agent_memory (id, agent_name, scope, key, value jsonb, cached_at,
              expires_at, hit_count, promoted bool)
agent_skills (id, agent_name, skill_key, content, source, version,
              updated_at)
audit_log (id, org_id, actor, action, resource, ts, metadata jsonb)
```

Her tabloda RLS açık, `TO authenticated` + `with check`. Her FK ve RLS
sütununa index.

---

## 6. Çapraz kesen konseptler

### 6.1 Skills + Memory pattern (agent başına)

- `langchain-master` skill'in `references/` + `memory/` + `_index.json`
  modeli genelleştirildi: her agent için DB tabanlı eşdeğeri.
- Skills: `agent_skills` tablosu + filesystem (`skills/<agent>/`).
  Filesystem version-controlled (git), DB runtime override.
- Memory: `agent_memory` tablosu, `scope ∈ {global, org, workspace,
cache, long_term}`.
- Long-term memory: pgvector retrieval. Konuşma özetleri, müşteri
  tercih kalıpları, geçmiş başarılı içerik şablonları.

### 6.2 Cron jadveli (Celery Beat)

| Job                    | Sıklık             | Görev                                                |
| ---------------------- | ------------------ | ---------------------------------------------------- |
| `recrawl_due_sites`    | Saatte 1           | `last_crawled_at` > `recrawl_interval` olan siteler  |
| `refresh_scores_daily` | Günlük 03:00 UTC   | Stale skor olan sayfaları yeniden analiz             |
| `evict_expired_memory` | Günlük 04:00 UTC   | TTL geçmiş `agent_memory` siler                      |
| `prune_old_executions` | Haftalık Pzr 05:00 | 90 günden eski `agent_executions` arşivler           |
| `weekly_digest_email`  | Haftalık Pzt 09:00 | Workspace owner'lara skor değişim raporu             |
| `freshness_check`      | Günlük 06:00 UTC   | "2 yıldan eski" sayfa raporu (AEO/freshness sinyali) |

### 6.3 LLM cost guard

- Her workspace için `monthly_llm_budget_usd` (default $X). %80'e
  varınca admin email, %100'de yeni analiz durdurulur (manual override).
- Per-agent `max_tokens_per_run` hard cap.
- Cache aggressively: aynı page content hash + aynı agent + aynı model
  → cache hit (24 saat TTL).

### 6.4 Multi-tenancy izolasyon testi

- Integration test: User A workspace verisini User B'nin token'ıyla
  okunamaz. Hem DB seviyesinde (RLS) hem API seviyesinde test edilir.
- BOLA defense: `ownership_required` decorator FastAPI'de her endpoint'te.

### 6.5 i18n

- v1 UI dili: TR
- v1.5: i18n soyutlama (`next-intl`) + EN
- Content generation her zaman site'ın `default_language`'ına göre
  (LLM prompt'unda explicit).

### 6.6 langchain-master skill entegrasyonu

- Bu skill, **geliştirici (Claude Code) için** bir advisor. Production
  agent değil.
- Implementation öncesi/sırasında LangGraph/LangChain/LangSmith
  konularında Claude Code bu skill'i `Skill(skill="langchain-master")`
  ile çağırır.
- Spec: `docs/superpowers/specs/2026-05-13-langchain-master-skill-design.md`
- Plan: `docs/superpowers/plans/2026-05-13-langchain-master-skill.md`
- Bu skill'in **kendi implement'i** A alt-projesinden bağımsız ve
  bağımsız zaten plan edilmiş; A'dan önce de bitirilebilir.

---

## 7. Roadmap (high-level zaman çizelgesi)

| Faz         | Süre            | İçerik                                                             |
| ----------- | --------------- | ------------------------------------------------------------------ |
| Faz 0       | 1 gün           | langchain-master skill'i implement et (zaten planlı)               |
| Faz 1 (A)   | 1 hafta         | Foundation, repo, Docker Compose, Supabase init                    |
| Faz 2 (B)   | 1 hafta         | Data layer, migration'lar, RLS, types                              |
| Faz 3 (C)   | 2 hafta         | Agent Core SDK (en kritik)                                         |
| Faz 4 (D)   | 1 hafta         | Crawl + ingestion pipeline + Modal embed                           |
| Faz 5 (E)   | 3 hafta         | v1 5 teknik agent'ı + Orchestrator                                 |
| Faz 6 (F+G) | 2 hafta paralel | Next.js dashboard + Auth/Org                                       |
| Faz 7 (H)   | 1 hafta         | Observability + ops setup                                          |
| Faz 8       | 1 hafta         | E2E test + closed beta (3-5 ajans)                                 |
| **Toplam**  | **~12 hafta**   | v1 production-ready                                                |
| v1.5        | +4 hafta        | 3 yeni teknik (Semantic Auth, Data-Rich, KG Align) + Stripe + i18n |
| v2          | +8 hafta        | Kalan 4 teknik + white-label + Author Authority                    |

---

## 8. Implementation order (alt-projeler arası dependency)

```
Faz 0: langchain-master skill (bağımsız)
  ↓
A (foundation)
  ↓
B (data layer)
  ├──→ G (auth + org)  ─┐
  ↓                      │
C (agent core)           │
  ↓                      ↓
D (crawl) ──→ E (5 agent suite) ──→ F (dashboard)
                                       ↓
                                  H (observability)
                                       ↓
                                  Closed beta
```

---

## 9. Verification (kabul kriterleri — v1)

### Fonksiyonel

1. Yeni ajans hesabı açılabilir, ajansa 2 workspace eklenebilir.
2. Bir workspace içinde 3 site eklenip "analyze now" tetiklenir.
3. ~5 dk içinde 3 sitenin de homepage'i için 5 teknikten skor üretilir.
4. Her teknik için en az 1 öneri (recommendation) üretilir.
5. FAQ Generator çıktısı geçerli JSON-LD üretir (schema.org validator).
6. Citation Generator en az 3 farklı kaynak önerir (Perplexity Sonar'dan).
7. Celery Beat haftalık recrawl tetikler, içerik değiştiyse skor güncellenir.
8. Ajans owner kullanıcı başka workspace'in verisini API'den okuyamaz (BOLA test).
9. PDF rapor white-label brandle indirilebilir.

### Operasyonel

10. KVM2'de v1 dashboard + 2 Celery worker + Redis + nginx hepsi aynı
    anda < 7GB RAM kullanır.
11. Tek site analizi maliyeti < $0.20 (5 teknik × ortalama LLM call).
12. p95 analiz süresi < 90 saniye / sayfa.
13. LangSmith'te her agent run trace edilebilir.
14. Sentry'de tüm hata 1 dk içinde görünür.

### Güvenlik

15. RLS açık her tabloda; service-role key sadece sunucuda (`NEXT_PUBLIC_`
    prefix yok).
16. JWT validation issuer/audience/lifetime; `ClockSkew=0`.
17. Rate limit (per workspace, token bucket) — `/agents/run` 60/hr.
18. CORS explicit allow-list, `AllowAnyOrigin().AllowCredentials()` yok.
19. `gitleaks` CI'de geçer.
20. Webhook'lar imza doğrular (Stripe v1.5).

---

## 10. Kritik dosyalar / dizinler (özet)

```
C:\aeogenerator\
├── apps/
│   ├── web/                     # Next.js 15 + TS + Tailwind + shadcn
│   │   ├── src/app/(marketing)/
│   │   ├── src/app/(auth)/
│   │   ├── src/app/(app)/
│   │   ├── src/components/ui/
│   │   ├── src/lib/dal/         # server-only DAL
│   │   ├── src/lib/env.ts       # t3-env
│   │   └── src/lib/database.types.ts  # Supabase gen
│   └── api/                     # Python 3.12 + FastAPI
│       ├── src/aeogen/
│       │   ├── agents/
│       │   │   ├── core/        # base, protocols, llm, memory, skills
│       │   │   ├── orchestrator/
│       │   │   ├── question_intent/
│       │   │   ├── structured_knowledge/
│       │   │   ├── ai_readable_formatting/
│       │   │   ├── entity_based_seo/
│       │   │   ├── citation_optimization/
│       │   │   └── skills/      # filesystem skill files per agent
│       │   ├── crawl/
│       │   ├── db/
│       │   ├── api/             # FastAPI routes
│       │   ├── tasks/           # Celery tasks + Beat schedule
│       │   └── settings.py
│       └── tests/
├── packages/
│   └── shared/                  # zod + pydantic parity schemas
├── infra/
│   ├── docker-compose.dev.yml
│   ├── docker-compose.prod.yml  # KVM2 deploy
│   ├── caddy/Caddyfile          # reverse proxy + LE SSL
│   └── modal/
│       └── embedding_service.py # BGE-M3 endpoint
├── supabase/
│   ├── migrations/
│   └── config.toml
├── docs/
│   ├── specs/                   # her alt-proje için spec
│   ├── plans/                   # her alt-proje için plan
│   ├── superpowers/specs/2026-05-13-langchain-master-skill-design.md
│   ├── superpowers/plans/2026-05-13-langchain-master-skill.md
│   └── runbooks/
├── .claude/
│   └── skills/langchain-master/ # Faz 0'da kurulur
├── .github/workflows/ci.yml
├── .editorconfig
├── pyproject.toml
└── pnpm-workspace.yaml
```

---

## 11. Açık konular (next-cycle'da netleştirilecek)

1. **Embedding model upgrade path:** BGE-M3 yeterli kalmazsa Voyage AI
   veya OpenAI text-embedding-3-large fallback nasıl olur?
2. **Sektör-spesifik agent davranışı:** Kozmetik vs. moda vs. elektronik
   e-ticaret için Analyzer skillerinde sektör prompt'u ne kadar
   önemli? (v1.5 öğrenilecek)
3. **Stripe pricing model:** Per-workspace flat fee mi, per-analysis
   kredi mi, hybrid mi? (Faz G'den sonra)
4. **White-label custom domain:** v1'de subpath (`/agency/<slug>`)
   yeterli, v2'de custom domain (CNAME + Caddy on-demand TLS)?
5. **Crawling proxy ihtiyacı:** Cloudflare Bot Management'lı siteler
   için residential proxy (Bright Data vs. self-host) gerekecek mi?
   (D alt-projesi öğrenilecek)
6. **OpenRouter spend cap:** Workspace başına aylık limit UI'da
   yönetilebilir mi yoksa sadece global mi? (F alt-projesi)
7. **Audit log retention:** GDPR/KVKK için ne kadar tutulacak? 1 yıl
   varsayılan?

---

## 12. Bir sonraki adımlar (Plan-mode çıkışı sonrası)

1. **ExitPlanMode** çağrılır — kullanıcı bu high-level plan'ı onaylar.
2. **Memory yazımı** (kullanıcı isteği) — proje context'i
   `C:\Users\iso\.claude\projects\C--aeogenerator\memory\`'e şu
   memory'ler olarak yazılır:
   - `project_aeogenerator_overview.md` (project type)
   - `feedback_planning_approach.md` (top-down + step-by-step + ultrathink)
   - `reference_geo_techniques.md` (12 teknik tablosu + research bulgular)
3. **Faz 0 başlat:** langchain-master skill'i implement et (zaten
   planlı, sadece file write).
4. **Faz 1 (A) brainstorm:** `superpowers:brainstorming` ile A
   alt-projesinin spec'ini yaz (`docs/specs/2026-05-XX-foundation-bootstrap-spec.md`).
5. **Sonra writing-plans:** her spec'ten plan üret.
6. **Sonra subagent-driven-development:** plan'ı task-task implement et.

---

**Yazar:** Claude (Opus 4.7) — kullanıcı `ismailmardin10@gmail.com`
ile birlikte, 2026-05-13.
