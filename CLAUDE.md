# aeogenerator — Project CLAUDE.md

> Bu dosya **global** `C:\Users\iso\.claude\CLAUDE.md` ile birlikte
> otomatik yüklenir; ezmez, EKLER. Proje-özel kurallar burada.

## Proje tanım (1-bakış)

**aeogenerator** — Dijital ajanslar için AEO/GEO multi-agent SaaS.
12 GEO/AEO tekniğini Analyzer + Generator agent çiftleriyle uygulayan,
LangGraph orchestrated, Celery-backed, OpenRouter-driven sistem.

- **v1 scope:** 5 yüksek-ROI teknik (Question-Intent, Structured
  Knowledge, AI-Readable Formatting, Entity-Based SEO, Citation Opt)
- **Hedef kitle:** Dijital ajanslar (org → workspace → site hiyerarşi)
- **Durum:** Plan onaylı, implementation Faz 0'a hazır

## ⚡ Her session'a başlarken — ZORUNLU

Implementation, planlama, status sorgusu veya proje üzerinde herhangi
bir iş için aşağıdaki **ilk adımı uygula**:

```
Skill(skill="aeogen-orchestrator", args="status")
```

Orkestratör mevcut durumu (`docs/PROGRESS.md`), master plan'ı
(`docs/plans/2026-05-13-master-plan.md`) ve memory'i (`MEMORY.md`)
okur, bir sonraki adımı belirler. `args="continue"` ile devam et;
`args="status"` ile salt-okunur durum raporu al; boş bırakırsan
otomatik mod (tam otonom).

**İstisna:** Salt-araştırma veya "şu dosya ne yapar?" gibi izolealı
sorular için orkestratörü atlayabilirsin — ama mevcut master plan
authoritative, çelişen öneri yapma.

## Üç temel kaynak (kanonik)

| Kaynak | Path | Amaç |
|---|---|---|
| Master plan | `docs/plans/2026-05-13-master-plan.md` | Lock-in mimari kararlar, 8 alt-proje, roadmap |
| Progress takipçi | `docs/PROGRESS.md` | Her task'ın durumu, son güncelleme, sıradaki adım |
| Memory index | `C:\Users\iso\.claude\projects\C--aeogenerator\memory\MEMORY.md` | Kalıcı proje hafızası (her session otomatik yüklü) |

## Otonomi modu

**Tam otonom** (kullanıcı tercihi):
- Orkestratör milestone'lar arası ONAY beklemeden ilerler
- Skill yoksa OTOMATİK yaratır (template + frontmatter)
- Sub-agent dispatch (Explore/Plan/general-purpose/code-reviewer)
  OTOMATİK
- **AMA**: aşağıdaki ops her zaman EXPLICIT KULLANICI ONAYI gerek:
  - `git push --force`, `git reset --hard`, `git branch -D`
  - `rm -rf` build/cache dışı
  - DB destructive op (drop table, truncate)
  - Auto-commit (CLAUDE.md global kuralı — kullanıcı söylemeden commit
    yok)
  - Prod deploy / secret rotation / `npm publish`
  - Plan dışı mimari sapma (>1 alt-proje etkileyen) — drift recovery:
    re-enter Plan Mode

## Tech stack lock-in (master plan §2)

| Katman | Karar |
|---|---|
| Web | Next.js 15 + TS strict + Tailwind + shadcn/ui |
| Auth + DB + Storage | Supabase Cloud (Postgres + pgvector + Auth + Storage + RLS) |
| Backend | Python 3.12 + FastAPI + LangChain + LangGraph + LangSmith |
| LLM | OpenRouter |
| Queue + cron | Celery + Redis + Celery Beat |
| Crawler | Crawl4AI |
| Vector + embed | pgvector + BGE-M3 self-host (Modal) |
| Hosting | Hostinger KVM2 + Supabase Cloud + Modal |
| Branş dili | UI: TR, kod/log/commit: EN |

## Repo konvansiyonları (proje-özel)

- **Monorepo (pnpm workspace):** `apps/web/` (Next.js), `apps/api/`
  (FastAPI), `packages/shared/` (Zod+Pydantic parity), `infra/`,
  `supabase/`, `docs/`
- **Conventional Commits** + Husky pre-commit + lint-staged
- **NEVER** commit secrets — `gitleaks` pre-commit gate
- **NEVER** auto-run EF/Alembic migration in prod startup

## Git workflow (3 environment branch + feature/*)

**Repo:** https://github.com/ismwolf/aoecreator
**Default branch:** `dev`

### Branch yapısı

| Branch | Ortam | Koruma | Push politikası |
|---|---|---|---|
| `dev` | Development (active) | Direct push İZİNLİ (auto-commit ile) | Her feature/<n> merge edilince |
| `test` | Staging / QA | PR REQUIRED | Manuel: dev → test PR + onay |
| `main` | Production | PR REQUIRED + 1 review | Manuel: test → main PR + onay |
| `feature/<n>-<kebab>` | Per-task | Direct push İZİNLİ | Otonom |

### Promotion akışı (otonom + manuel hibrit)

```
feature/<n>-<task>  ─── auto commit + push ────► origin/feature/<n>
        │
        └─ auto open PR ──────────────────────► dev
                                                  │
                                                  ├─ MANUEL onay ─► test
                                                  │
                                                  └─ MANUEL onay ─► main (PROD)
```

### Otonom commit + push politikası (bu sessionda netleştirildi)

Tam otonom orkestratör şunları **OTOMATIK** yapar:
- `feature/<n>` branch'inde her task complete → Conventional commit + push
- Alt-proje complete → PR open: `feature/<n>` → `dev`
- Faz complete → PROGRESS.md güncelle + commit + push to dev
- Co-Authored-By footer her commit'te zorunlu

Şunlar için **KULLANICI ONAYI** zorunlu (bypass etmez):
- PR `dev` → `test` (staging deploy tetikler)
- PR `test` → `main` (prod deploy tetikler)
- `git push --force`, `git reset --hard`, `git branch -D`
- `rm -rf` (build/cache dışı)
- Branch protection rule değişikliği
- main veya test branch'e direct push (PR atlamak)
- Tag oluşturma (release tagleri)
- Stripe / OpenRouter / Supabase secret rotation

### Conventional Commits örnekleri

```
feat(agents): add Question-Intent Analyzer for FAQ schema
fix(crawl): handle Cloudflare 403 with proxy fallback
chore(infra): add docker-compose.dev.yml with Postgres+Redis
docs(progress): mark Faz 0 task 3 complete
refactor(api/db): consolidate org+workspace query builders
test(agents/core): add LLM mock tests for OpenRouter adapter
```

### İlk kurulum durumu (2026-05-13)

- ✅ Local repo `git init -b dev`
- ✅ Remote: `origin = https://github.com/ismwolf/aoecreator.git`
- ✅ 3 branch oluşturuldu ve push'landı (dev, test, main)
- ✅ Default branch GitHub'da `dev` olarak ayarlandı
- ⏳ Branch protection rules (kullanıcı GitHub UI'de yapacak):
  - `main`: PR required, 1 approval, dismiss stale, require CI
  - `test`: PR required, require CI
  - `dev`: required CI checks (henüz CI yok, Faz 1'de gelecek)

## v1 implementation sırası (master plan §8)

```
Faz 0 (langchain-master skill, bağımsız) →
Faz 1 (A: foundation) → Faz 2 (B: data layer) →
Faz 3 (C: agent core SDK) → Faz 4 (D: crawl) →
Faz 5 (E: 5 GEO agent) → Faz 6 (F+G: dashboard + auth) →
Faz 7 (H: observability) → Faz 8 (closed beta)
```

## Skill çağrı önceliği (global kuraldan miras + proje-özel)

- BEFORE code/design/scaffold → `superpowers:brainstorming`
- AFTER design approved → `superpowers:writing-plans`
- AFTER plan approved → `superpowers:subagent-driven-development`
- ON bug / failing test → `superpowers:systematic-debugging`
- BEFORE declaring "done" → `superpowers:verification-before-completion`
- BEFORE commit → `superpowers:requesting-code-review`
- ON LangChain / LangGraph / LangSmith soru → `Skill(skill="langchain-master")`
  (Faz 0'da kurulacak)
- ON proje implementasyonu (genel) → `Skill(skill="aeogen-orchestrator")`

## MUST (proje-özel — global'a ek)

- Plan dosyasındaki Q1-Q8 lock-in'lerini değiştirmeden önce drift
  recovery: Plan Mode'a gir, revised plan + kullanıcı onayı
- Her major task sonrası `docs/PROGRESS.md` güncelle
- Her major milestone sonrası proje memory'e (`reference_*.md` veya
  `project_*.md`) yansıt
- 12 GEO tekniğinin v1 / v2 ayrımına sadık kal (master plan §1 tablosu)
- Multi-tenancy testi: her yeni endpoint için BOLA + RLS testi
- Token/cost guard: per-agent `max_tokens_per_run` ve workspace
  `monthly_llm_budget_usd` (master plan §6.3)

## MUST NOT (proje-özel — global'a ek)

- `app_metadata` (server-set) yerine `user_metadata` (user-writable)
  ile yetki kararı verme
- v1 scope'una v2 tekniklerini sızdırma (kararı görüşülmeden)
- Plan §11 "Açık konular" listesindeki kararları varsayım yaparak
  netleştirme — kullanıcıyla görüş
- Master plan'ı `docs/plans/2026-05-13-master-plan.md` dışında bir
  yerden referans verme (yaşayan kaynak burası; `C:\Users\iso\.claude\plans\...`
  snapshot)

## Detay dosyalar (her zaman erişilebilir)

```
docs/
├── plans/2026-05-13-master-plan.md       # Master plan (kanonik)
├── plans/<tarih>-<altproje>-plan.md       # Her alt-proje plan'ı
├── specs/<tarih>-<altproje>-spec.md       # Her alt-proje spec'i
├── PROGRESS.md                           # Adım adım takipçi
├── superpowers/specs/2026-05-13-langchain-master-skill-design.md
├── superpowers/plans/2026-05-13-langchain-master-skill.md
└── runbooks/                              # Ops runbook'lar (Faz 7+)

.claude/
└── skills/
    ├── aeogen-orchestrator/               # Proje orkestratörü (bu session'da kuruldu)
    └── langchain-master/                  # Faz 0'da implement edilecek
```
