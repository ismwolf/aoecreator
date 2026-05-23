# Faz 4 D — Crawl & Ingestion Pipeline Spec

**Tarih:** 2026-05-23
**Durum:** Approved
**Alt-proje:** D — Crawl & Ingestion Pipeline
**Kaynak:** Master plan §4.D

---

## Problem

GEO/AEO agent'ları analiz edebilmek için bir sitenin içeriğine ihtiyaç duyar.
Bu içerik: HTML snapshot, parsed markdown, schema.org yapısı ve pgvector'e
yüklenmiş semantik embedding'lerden oluşur. Şu anda hiçbir crawl altyapısı yok.

## Goals

1. **D.1** — Crawl4AI ile sitemap-driven async spider (rate-limit, robots.txt)
2. **D.2** — Per-page schema.org JSON-LD + Open Graph meta extractor
3. **D.3** — Semantic chunker (~512 token, tiktoken tabanlı)
4. **D.4** — Modal BGE-M3 embedding client (HTTP, batch)
5. **D.5** — pgvector insert (`embeddings` tablosu, B.3)
6. **D.6** — Celery task `crawl_site(site_id)` + retry (Upstash Redis)
7. **D.7** — HTML snapshot → Supabase Storage `crawls/<site_id>/<url_hash>.html`

## Non-Goals

- Crawl scheduling / periodic refresh (Celery Beat — Faz 7+)
- Incremental diff crawl (v1.5+)
- Multi-language sitemap expansion (v2)
- Playwright JS rendering mode (Crawl4AI fetch mode only for v1)

## Approach

### Infrastructure decisions (user-confirmed)

| Concern | Decision                                                                                               |
| ------- | ------------------------------------------------------------------------------------------------------ |
| Redis   | Upstash Redis (serverless, TLS). User provides `REDIS_URL`                                             |
| BGE-M3  | Modal serverless GPU (L4). User deploys `infra/modal/embedding_service.py`, provides `MODAL_EMBED_URL` |
| Storage | Supabase Storage bucket `crawls` (service role — existing `supabase_secret_key`)                       |

### Spider strategy

- Entry: `sitemap.xml` → `sitemap-index.xml` (recursive) → URL list
- Fallback: `robots.txt` `Sitemap:` directive, then root `/sitemap.xml`
- Priority: homepage (score 3) > category page (score 2) > blog/product (score 1)
- `max_pages: int = 50` (configurable per run)
- Rate limit: 1 req/s per domain (Redis SETNX lock, 1s TTL)
- Retry: 2x with exponential backoff on 429/503
- Bot detection: rotate UA, respect `Crawl-Delay` from robots.txt
- Crawl4AI `AsyncWebCrawler` with `fetch` extraction mode (no Playwright JS)

### Parser

Per-page extraction from CrawledPage:

- JSON-LD: all `<script type="application/ld+json">` blocks → list
- Open Graph: `og:title`, `og:description`, `og:image`, `og:type`
- Canonical: `<link rel="canonical">`
- Markdown: Crawl4AI built-in markdown output (stripped nav/footer/ads)
- Word count, content length

Output → `ParsedContent` TypedDict → persisted to `public.pages` (B.2)

### Chunker

Strategy: heading-aware + token-limited

1. Split markdown by H1/H2/H3 boundaries → sections
2. Each section: split into ~512 token chunks (tiktoken `cl100k_base`)
3. Overlap: 50 tokens between consecutive chunks
4. Each chunk carries `heading_context: str` (nearest ancestor heading)
5. Return `list[TextChunk]`

### Modal embedding service

File: `infra/modal/embedding_service.py`

- Model: `BAAI/bge-m3` via `FlagEmbedding` (1024-dim, multilingual)
- GPU: `L4` (cheapest viable for batch BGE-M3)
- Input: `POST /embed` → `{"texts": ["...", ...]}` (batch up to 64)
- Output: `{"embeddings": [[...], ...]}` (1024-dim float lists)
- Auto-scale to 0 when idle (Modal serverless — no cost when not in use)
- Image: Python 3.12, FlagEmbedding + torch + transformers

### Embedder client

File: `apps/api/src/aeogen/crawl/embedder.py`

- `ModalEmbedder(embed_url: str)`
- `async def embed_batch(texts: list[str]) -> list[list[float]]`
- Internal batch size: 32 (prevents single Modal timeout on large pages)
- Uses httpx AsyncClient with 120s timeout

### pgvector insert

- Target: `public.embeddings` table (B.3: `page_id`, `workspace_id`, `chunk_text`, `embedding`, `chunk_index`, `model_name`)
- `model_name = "bge-m3"`
- Uses psycopg3 async (consistent with C.4/C.5)
- Upsert on `(page_id, chunk_index)` — safe re-crawl

### Celery task

File: `apps/api/src/aeogen/tasks/crawl.py`
Config: `apps/api/src/aeogen/celery_app.py`

```python
@app.task(bind=True, max_retries=3, default_retry_delay=60)
def crawl_site(self, site_id: str, run_id: str) -> None: ...
```

- Broker + backend: `REDIS_URL` (Upstash)
- Sync Celery task (Crawl4AI is async; wrap with `asyncio.run()`)
- Updates `analysis_runs.status` as: `queued → running → completed/failed`
- On exception: `self.retry(exc=exc, countdown=60 * 2**self.request.retries)`

### Supabase Storage

- Bucket: `crawls` (private, 10MB file limit)
- Path: `crawls/<site_id>/<sha256(url)[:16]>.html`
- Upload via `supabase-py` client (service role key)
- Bucket must exist: created via MCP or dashboard

## File structure

```
apps/api/src/aeogen/
├── celery_app.py              NEW — Celery app definition + Upstash config
├── crawl/
│   ├── __init__.py            NEW
│   ├── spider.py              NEW — SiteSpider (Crawl4AI wrapper)
│   ├── parser.py              NEW — PageParser (schema.org + meta)
│   ├── chunker.py             NEW — SemanticChunker (tiktoken)
│   └── embedder.py            NEW — ModalEmbedder (HTTP client)
├── tasks/
│   ├── __init__.py            NEW
│   └── crawl.py               NEW — crawl_site Celery task
└── settings.py                MODIFY — REDIS_URL + MODAL_EMBED_URL

infra/
└── modal/
    └── embedding_service.py   NEW — BGE-M3 Modal endpoint

apps/api/tests/
├── test_spider.py             NEW — 8 tests (mocked Crawl4AI + Redis)
├── test_parser.py             NEW — 6 tests (HTML fixtures)
├── test_chunker.py            NEW — 5 tests (token boundary, overlap, headings)
├── test_embedder.py           NEW — 4 tests (mocked httpx)
└── test_crawl_task.py         NEW — 5 tests (mocked Celery + all deps)

apps/api/pyproject.toml        MODIFY — new deps
apps/api/.env.example          MODIFY — REDIS_URL + MODAL_EMBED_URL
.github/workflows/ci.yml       MODIFY — REDIS_URL + MODAL_EMBED_URL CI placeholders
```

## New dependencies

```toml
# apps/api/pyproject.toml — [project] dependencies
"crawl4ai>=0.4,<0.6"           # async web crawler (Playwright-backed)
"celery[redis]>=5.3,<6"        # task queue
"tiktoken>=0.7,<1"             # token counting for chunker
"httpx>=0.27,<0.28"            # Modal HTTP client (promote from dev to main)
```

> Note: `httpx` is already in `[project.optional-dependencies] dev`. Must move
> to main deps since ModalEmbedder is production code.
>
> `supabase>=2.6,<3` already in deps — used for Storage upload (D.7).

## New env vars

```python
# settings.py additions
redis_url: RedisDsn = Field(
    validation_alias=AliasChoices("REDIS_URL"),
    description="Upstash Redis TLS URL (rediss://...)",
)
modal_embed_url: HttpUrl = Field(
    description="Modal BGE-M3 /embed endpoint URL",
)
crawl_top_pages: int = Field(default=50, ge=1, le=500)
crawl_rate_limit_rps: float = Field(default=1.0, ge=0.1, le=10.0)
```

## Data contracts

### CrawledPage

```python
class CrawledPage(TypedDict):
    url: str
    html: str
    markdown: str
    status_code: int
    crawled_at: datetime
```

### ParsedContent

```python
class ParsedContent(TypedDict):
    url: str
    canonical_url: str | None
    og_title: str | None
    og_description: str | None
    og_type: str | None
    json_ld: list[dict[str, object]]
    markdown: str
    word_count: int
```

### TextChunk

```python
class TextChunk(TypedDict):
    text: str
    chunk_index: int
    heading_context: str
    token_count: int
    start_char: int
    end_char: int
```

## Risks

| Risk                                                             | Mitigation                                                                      |
| ---------------------------------------------------------------- | ------------------------------------------------------------------------------- |
| Crawl4AI API surface instability between minor versions          | Pin `<0.6`, test against fixed HTML fixtures                                    |
| Modal cold start >30s on first request                           | Pre-warm via keepalive cron (v1.5); acceptable for v1                           |
| Upstash Redis rate limits (free: 10k req/day)                    | Rate-limit lock is 1 call/page — 50 pages/run = 50 calls; well within free tier |
| `crawls` bucket not created                                      | Document in Celery task startup: check/create bucket on first run               |
| tiktoken `cl100k_base` tokenizer different from BGE-M3 tokenizer | Acceptable approximation; chunks may be ±10% off — good enough for v1           |
| Playwright browser not installed (Crawl4AI dep)                  | CI installs via `playwright install --with-deps chromium` in python-checks job  |

## Verification gates (each sub-cycle)

- `ruff check + format`: 0 errors
- `mypy src --strict`: Success
- `pytest tests/test_<module>.py -v`: all green
- Full suite: `pytest tests/ -v` 44 + new tests all green
- Coverage: `fail_under=80` still met

## Acceptance criteria (full D)

- [ ] `crawl_site.delay(site_id, run_id)` enqueues to Upstash Redis
- [ ] Spider crawls ≥1 page from a test URL, returns `CrawledPage`
- [ ] Parser extracts JSON-LD + og:title from a real Wikipedia HTML fixture
- [ ] Chunker produces chunks ≤560 tokens each (512 + 50 overlap max), >0 chunks
- [ ] `embed_batch(["test"])` returns list of 1024-dim floats (mocked in unit tests)
- [ ] pgvector upsert works against `embeddings` table (mocked in unit tests)
- [ ] HTML snapshot stored at `crawls/<site_id>/<hash>.html` (mocked supabase in tests)
- [ ] Modal endpoint deployed (`modal deploy infra/modal/embedding_service.py` succeeds)
- [ ] All 28+ new tests pass, coverage ≥80% on aeogen.crawl + aeogen.tasks
