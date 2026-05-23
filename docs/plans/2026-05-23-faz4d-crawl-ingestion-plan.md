# Faz 4 D — Crawl & Ingestion Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a full crawl + embedding ingestion pipeline: Crawl4AI spider → schema.org parser → semantic chunker → Modal BGE-M3 embedder → pgvector insert, wired via a Celery task backed by Upstash Redis, with HTML snapshots in Supabase Storage.

**Architecture:** Seven focused modules under `apps/api/src/aeogen/crawl/` + `apps/api/src/aeogen/tasks/`, a Modal app in `infra/modal/`, and Celery config in `apps/api/src/aeogen/celery_app.py`. All modules use TDD (RED → GREEN). Full spec: `docs/specs/2026-05-23-faz4d-crawl-ingestion-spec.md`.

**Tech Stack:** Python 3.12, Crawl4AI, Celery + Upstash Redis, tiktoken, httpx, FlagEmbedding (Modal GPU), psycopg3, supabase-py (Storage), pytest-asyncio.

---

## File map

| File                                    | Action | Purpose                                       |
| --------------------------------------- | ------ | --------------------------------------------- |
| `apps/api/src/aeogen/settings.py`       | MODIFY | Add REDIS_URL, MODAL_EMBED_URL, crawl knobs   |
| `apps/api/src/aeogen/celery_app.py`     | CREATE | Celery app + Upstash broker/backend config    |
| `apps/api/src/aeogen/crawl/__init__.py` | CREATE | Module marker                                 |
| `apps/api/src/aeogen/crawl/spider.py`   | CREATE | SiteSpider (Crawl4AI + rate-limit)            |
| `apps/api/src/aeogen/crawl/parser.py`   | CREATE | PageParser (schema.org + meta)                |
| `apps/api/src/aeogen/crawl/chunker.py`  | CREATE | SemanticChunker (tiktoken, heading-aware)     |
| `apps/api/src/aeogen/crawl/embedder.py` | CREATE | ModalEmbedder (httpx batch)                   |
| `apps/api/src/aeogen/tasks/__init__.py` | CREATE | Module marker                                 |
| `apps/api/src/aeogen/tasks/crawl.py`    | CREATE | crawl_site Celery task                        |
| `apps/api/tests/test_spider.py`         | CREATE | 8 unit tests                                  |
| `apps/api/tests/test_parser.py`         | CREATE | 6 unit tests                                  |
| `apps/api/tests/test_chunker.py`        | CREATE | 5 unit tests                                  |
| `apps/api/tests/test_embedder.py`       | CREATE | 4 unit tests                                  |
| `apps/api/tests/test_crawl_task.py`     | CREATE | 5 unit tests                                  |
| `infra/modal/embedding_service.py`      | CREATE | BGE-M3 Modal endpoint                         |
| `apps/api/pyproject.toml`               | MODIFY | Add crawl4ai, celery, tiktoken; promote httpx |
| `apps/api/.env.example`                 | MODIFY | REDIS_URL + MODAL_EMBED_URL                   |
| `.github/workflows/ci.yml`              | MODIFY | Playwright install + CI env vars              |

---

## Task 1: Add dependencies + env vars

**Files:** `apps/api/pyproject.toml`, `apps/api/src/aeogen/settings.py`, `apps/api/.env.example`, `apps/api/tests/conftest.py`

- [ ] **Step 1.1: Add production deps to pyproject.toml**

  In `[project] dependencies`, add:

  ```toml
  "crawl4ai>=0.4,<0.6",
  "celery[redis]>=5.3,<6",
  "tiktoken>=0.7,<1",
  ```

  AND move `httpx>=0.27,<0.28` from `[project.optional-dependencies] dev` to `[project] dependencies`.

- [ ] **Step 1.2: Run uv sync to resolve**

  ```
  cd apps/api && uv sync
  ```

  Expected: resolves without conflict. `uv lock --check` exit 0.

- [ ] **Step 1.3: Add env vars to settings.py**

  After the `openrouter_default_model` field, add:

  ```python
  # Redis / Celery (D.6). Upstash TLS URL.
  redis_url: RedisDsn = Field(
      ...,
      validation_alias=AliasChoices("REDIS_URL"),
      description="Upstash Redis TLS URL (rediss://:password@host:6380).",
      repr=False,
  )

  # Modal BGE-M3 embedding service (D.4).
  modal_embed_url: HttpUrl = Field(
      ...,
      description="Modal BGE-M3 /embed endpoint URL.",
  )

  # Crawl knobs
  crawl_top_pages: int = Field(default=50, ge=1, le=500)
  crawl_rate_limit_rps: float = Field(default=1.0, ge=0.1, le=10.0)
  ```

  Also add `RedisDsn` to the pydantic imports at the top.

- [ ] **Step 1.4: Add placeholders to .env.example**

  Add after existing OpenRouter lines:

  ```
  # Redis / Celery (D.6)
  REDIS_URL=rediss://:your-upstash-password@your-host.upstash.io:6380

  # Modal BGE-M3 (D.4) — get after `modal deploy infra/modal/embedding_service.py`
  MODAL_EMBED_URL=https://your-username--aeogen-embed.modal.run
  ```

- [ ] **Step 1.5: Update conftest.py with new required env vars**

  In `apps/api/tests/conftest.py`, add at the top (after existing `os.environ.setdefault` lines):

  ```python
  os.environ.setdefault("REDIS_URL", "rediss://:test@localhost:6380")
  os.environ.setdefault("MODAL_EMBED_URL", "https://test--aeogen-embed.modal.run")
  ```

- [ ] **Step 1.6: Verify mypy still passes**

  ```
  cd apps/api && uv run mypy src --strict
  ```

  Expected: `Success: no issues found in N source files`

- [ ] **Step 1.7: Verify full test suite still passes**
  ```
  cd apps/api && uv run pytest tests/ -v
  ```
  Expected: 44 passed (same as before, no regressions).

---

## Task 2: Crawl module skeleton + types

**Files:** `apps/api/src/aeogen/crawl/__init__.py`, (types defined inline in each module)

- [ ] **Step 2.1: Create crawl/**init**.py**

  ```python
  """Crawl & ingestion pipeline — D-cycle modules."""
  ```

- [ ] **Step 2.2: Verify mypy on the new empty module**
  ```
  cd apps/api && uv run mypy src --strict
  ```
  Expected: Success.

---

## Task 3: PageParser (D.2)

**Files:** `apps/api/src/aeogen/crawl/parser.py`, `apps/api/tests/test_parser.py`

- [ ] **Step 3.1 (TDD RED): Write failing tests**

  Create `apps/api/tests/test_parser.py`:

  ```python
  """D.2 PageParser unit tests — pure HTML, no network."""

  import json
  from aeogen.crawl.parser import PageParser, ParsedContent

  _HTML_WITH_JSONLD = """
  <html>
  <head>
    <script type="application/ld+json">{"@type": "Product", "name": "Test"}</script>
    <meta property="og:title" content="Test Title" />
    <meta property="og:description" content="Test Desc" />
    <meta property="og:type" content="website" />
    <link rel="canonical" href="https://example.com/page" />
  </head>
  <body><p>Hello world</p></body>
  </html>
  """

  _HTML_NO_META = "<html><body><p>Just text.</p></body></html>"

  _HTML_TWO_JSONLD = """
  <html><head>
    <script type="application/ld+json">{"@type": "WebPage"}</script>
    <script type="application/ld+json">{"@type": "BreadcrumbList"}</script>
  </head><body></body></html>
  """


  def test_parse_extracts_jsonld() -> None:
      parser = PageParser()
      result = parser.parse(_HTML_WITH_JSONLD, url="https://example.com/page", markdown="Hello world")
      assert len(result["json_ld"]) == 1
      assert result["json_ld"][0]["@type"] == "Product"


  def test_parse_extracts_og_meta() -> None:
      parser = PageParser()
      result = parser.parse(_HTML_WITH_JSONLD, url="https://example.com/page", markdown="Hello world")
      assert result["og_title"] == "Test Title"
      assert result["og_description"] == "Test Desc"
      assert result["og_type"] == "website"


  def test_parse_extracts_canonical() -> None:
      parser = PageParser()
      result = parser.parse(_HTML_WITH_JSONLD, url="https://example.com/page", markdown="Hello world")
      assert result["canonical_url"] == "https://example.com/page"


  def test_parse_no_meta_returns_none_fields() -> None:
      parser = PageParser()
      result = parser.parse(_HTML_NO_META, url="https://example.com", markdown="Just text.")
      assert result["og_title"] is None
      assert result["canonical_url"] is None
      assert result["json_ld"] == []


  def test_parse_multiple_jsonld_blocks() -> None:
      parser = PageParser()
      result = parser.parse(_HTML_TWO_JSONLD, url="https://example.com", markdown="")
      assert len(result["json_ld"]) == 2
      types = {d["@type"] for d in result["json_ld"]}
      assert types == {"WebPage", "BreadcrumbList"}


  def test_parse_word_count() -> None:
      parser = PageParser()
      result = parser.parse(_HTML_NO_META, url="https://x.com", markdown="one two three")
      assert result["word_count"] == 3
  ```

- [ ] **Step 3.2: Run tests to verify RED**

  ```
  cd apps/api && uv run pytest tests/test_parser.py -v
  ```

  Expected: `ModuleNotFoundError` or `ImportError`.

- [ ] **Step 3.3: Implement parser.py**

  Create `apps/api/src/aeogen/crawl/parser.py`:

  ```python
  """D.2 — PageParser: schema.org JSON-LD + Open Graph meta + canonical extraction."""

  from __future__ import annotations

  import json
  import logging
  from html.parser import HTMLParser
  from typing import Any, TypedDict

  logger = logging.getLogger(__name__)


  class ParsedContent(TypedDict):
      url: str
      canonical_url: str | None
      og_title: str | None
      og_description: str | None
      og_type: str | None
      json_ld: list[dict[str, object]]
      markdown: str
      word_count: int


  class _MetaExtractor(HTMLParser):
      """Pull JSON-LD blocks, OG meta, and canonical link from raw HTML."""

      def __init__(self) -> None:
          super().__init__()
          self.json_ld: list[dict[str, object]] = []
          self.og: dict[str, str] = {}
          self.canonical: str | None = None
          self._in_jsonld = False
          self._jsonld_buf = ""

      def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
          attrs_dict = dict(attrs)
          if tag == "script" and attrs_dict.get("type") == "application/ld+json":
              self._in_jsonld = True
              self._jsonld_buf = ""
          elif tag == "meta":
              prop = attrs_dict.get("property", "")
              name = attrs_dict.get("name", "")
              content = attrs_dict.get("content") or ""
              if prop.startswith("og:"):
                  self.og[prop[3:]] = content
              elif name.startswith("og:"):
                  self.og[name[3:]] = content
          elif tag == "link" and attrs_dict.get("rel") == "canonical":
              self.canonical = attrs_dict.get("href")

      def handle_endtag(self, tag: str) -> None:
          if tag == "script" and self._in_jsonld:
              self._in_jsonld = False
              try:
                  parsed = json.loads(self._jsonld_buf)
                  if isinstance(parsed, list):
                      self.json_ld.extend(parsed)
                  elif isinstance(parsed, dict):
                      self.json_ld.append(parsed)
              except json.JSONDecodeError:
                  logger.warning("Failed to parse JSON-LD block")

      def handle_data(self, data: str) -> None:
          if self._in_jsonld:
              self._jsonld_buf += data


  class PageParser:
      """Extracts structured metadata from a crawled HTML page."""

      def parse(self, html: str, *, url: str, markdown: str) -> ParsedContent:
          """Parse HTML and return structured content dict."""
          extractor = _MetaExtractor()
          extractor.feed(html)

          word_count = len(markdown.split()) if markdown.strip() else 0

          return ParsedContent(
              url=url,
              canonical_url=extractor.canonical,
              og_title=extractor.og.get("title"),
              og_description=extractor.og.get("description"),
              og_type=extractor.og.get("type"),
              json_ld=extractor.json_ld,
              markdown=markdown,
              word_count=word_count,
          )
  ```

- [ ] **Step 3.4 (TDD GREEN): Run tests**

  ```
  cd apps/api && uv run pytest tests/test_parser.py -v
  ```

  Expected: 6 passed.

- [ ] **Step 3.5: ruff + mypy**

  ```
  cd apps/api && uv run ruff check src/aeogen/crawl/parser.py && uv run ruff format --check src/aeogen/crawl/parser.py && uv run mypy src --strict
  ```

  Expected: 0 errors, Success.

- [ ] **Step 3.6: Commit**

  ```
  git add apps/api/src/aeogen/crawl/ apps/api/tests/test_parser.py
  git commit -m "feat(crawl/parser): add PageParser for schema.org + OG meta extraction (D.2)

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 4: SemanticChunker (D.3)

**Files:** `apps/api/src/aeogen/crawl/chunker.py`, `apps/api/tests/test_chunker.py`

- [ ] **Step 4.1 (TDD RED): Write failing tests**

  Create `apps/api/tests/test_chunker.py`:

  ```python
  """D.3 SemanticChunker unit tests."""

  from aeogen.crawl.chunker import SemanticChunker, TextChunk


  _SHORT_MD = "Hello world."

  _HEADING_MD = """# Section A

  Alpha beta gamma delta.

  ## Section B

  Epsilon zeta eta theta iota kappa.
  """

  _LONG_SECTION = "word " * 600  # 600 tokens > 512


  def test_chunk_empty_returns_empty() -> None:
      chunker = SemanticChunker()
      assert chunker.chunk("") == []


  def test_chunk_short_text_single_chunk() -> None:
      chunker = SemanticChunker()
      chunks = chunker.chunk(_SHORT_MD)
      assert len(chunks) == 1
      assert chunks[0]["text"] == _SHORT_MD
      assert chunks[0]["chunk_index"] == 0


  def test_chunk_heading_context_propagates() -> None:
      chunker = SemanticChunker()
      chunks = chunker.chunk(_HEADING_MD)
      # At least one chunk should have heading context from "Section A" or "Section B"
      texts = [c["heading_context"] for c in chunks]
      assert any("Section" in t for t in texts)


  def test_chunk_indices_sequential() -> None:
      chunker = SemanticChunker()
      chunks = chunker.chunk(_HEADING_MD)
      for i, chunk in enumerate(chunks):
          assert chunk["chunk_index"] == i


  def test_chunk_long_section_splits() -> None:
      chunker = SemanticChunker(max_tokens=512, overlap_tokens=50)
      chunks = chunker.chunk(_LONG_SECTION)
      assert len(chunks) >= 2
      for chunk in chunks:
          assert chunk["token_count"] <= 562  # 512 + 50 overlap max
  ```

- [ ] **Step 4.2: Run tests to verify RED**

  ```
  cd apps/api && uv run pytest tests/test_chunker.py -v
  ```

  Expected: `ImportError`.

- [ ] **Step 4.3: Implement chunker.py**

  Create `apps/api/src/aeogen/crawl/chunker.py`:

  ```python
  """D.3 — SemanticChunker: heading-aware markdown chunking with tiktoken."""

  from __future__ import annotations

  import re
  from typing import TypedDict

  import tiktoken


  class TextChunk(TypedDict):
      text: str
      chunk_index: int
      heading_context: str
      token_count: int
      start_char: int
      end_char: int


  class SemanticChunker:
      """Split markdown into ~512-token chunks, respecting heading boundaries."""

      _HEADING_RE = re.compile(r"^(#{1,3})\s+(.+)$", re.MULTILINE)

      def __init__(self, max_tokens: int = 512, overlap_tokens: int = 50) -> None:
          self._max = max_tokens
          self._overlap = overlap_tokens
          self._enc = tiktoken.get_encoding("cl100k_base")

      def _tokenize(self, text: str) -> list[int]:
          return self._enc.encode(text)

      def _count(self, text: str) -> int:
          return len(self._tokenize(text))

      def chunk(self, markdown: str) -> list[TextChunk]:
          if not markdown.strip():
              return []

          sections = self._split_by_heading(markdown)
          chunks: list[TextChunk] = []
          idx = 0

          for heading_ctx, section_text in sections:
              sub = self._split_section(section_text, heading_ctx)
              for text, start, end in sub:
                  chunks.append(
                      TextChunk(
                          text=text,
                          chunk_index=idx,
                          heading_context=heading_ctx,
                          token_count=self._count(text),
                          start_char=start,
                          end_char=end,
                      )
                  )
                  idx += 1

          return chunks

      def _split_by_heading(self, text: str) -> list[tuple[str, str]]:
          """Split text at H1/H2/H3 boundaries. Returns (heading_ctx, section_text)."""
          parts: list[tuple[str, str]] = []
          positions = [m.start() for m in self._HEADING_RE.finditer(text)]

          if not positions:
              return [("", text)]

          # Text before first heading
          if positions[0] > 0:
              parts.append(("", text[: positions[0]].strip()))

          for i, pos in enumerate(positions):
              end = positions[i + 1] if i + 1 < len(positions) else len(text)
              section = text[pos:end]
              first_line_end = section.index("\n") if "\n" in section else len(section)
              heading = section[:first_line_end].lstrip("#").strip()
              body = section[first_line_end:].strip()
              if body:
                  parts.append((heading, body))

          return [(h, b) for h, b in parts if b.strip()]

      def _split_section(
          self, text: str, heading_ctx: str
      ) -> list[tuple[str, int, int]]:
          """Split a section into token-limited chunks with overlap."""
          tokens = self._tokenize(text)
          if len(tokens) <= self._max:
              return [(text, 0, len(text))]

          results: list[tuple[str, int, int]] = []
          step = self._max - self._overlap
          start_tok = 0

          while start_tok < len(tokens):
              end_tok = min(start_tok + self._max, len(tokens))
              chunk_tokens = tokens[start_tok:end_tok]
              chunk_text = self._enc.decode(chunk_tokens)
              # Approximate char offsets (best-effort)
              char_start = len(self._enc.decode(tokens[:start_tok]))
              char_end = char_start + len(chunk_text)
              results.append((chunk_text, char_start, char_end))
              if end_tok >= len(tokens):
                  break
              start_tok += step

          return results
  ```

- [ ] **Step 4.4 (TDD GREEN): Run tests**

  ```
  cd apps/api && uv run pytest tests/test_chunker.py -v
  ```

  Expected: 5 passed.

- [ ] **Step 4.5: ruff + mypy**

  ```
  cd apps/api && uv run ruff check src/aeogen/crawl/chunker.py && uv run mypy src --strict
  ```

  Expected: 0 errors, Success.

- [ ] **Step 4.6: Commit**

  ```
  git commit -m "feat(crawl/chunker): add SemanticChunker with tiktoken + heading-aware splitting (D.3)

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 5: ModalEmbedder client (D.4)

**Files:** `apps/api/src/aeogen/crawl/embedder.py`, `apps/api/tests/test_embedder.py`

- [ ] **Step 5.1 (TDD RED): Write failing tests**

  Create `apps/api/tests/test_embedder.py`:

  ```python
  """D.4 ModalEmbedder unit tests — mocked httpx."""

  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest

  import os
  os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
  os.environ.setdefault("OPENROUTER_API_KEY", "test-key-" + "x" * 20)
  os.environ.setdefault("REDIS_URL", "rediss://:test@localhost:6380")
  os.environ.setdefault("MODAL_EMBED_URL", "https://test--aeogen-embed.modal.run")

  from aeogen.crawl.embedder import ModalEmbedder


  @pytest.mark.asyncio
  async def test_embed_batch_returns_embeddings() -> None:
      embedder = ModalEmbedder("https://test.modal.run")
      fake_response = MagicMock()
      fake_response.raise_for_status = MagicMock()
      fake_response.json.return_value = {"embeddings": [[0.1] * 1024]}

      with patch("aeogen.crawl.embedder.httpx.AsyncClient") as mock_client_cls:
          mock_client = AsyncMock()
          mock_client.__aenter__ = AsyncMock(return_value=mock_client)
          mock_client.__aexit__ = AsyncMock(return_value=None)
          mock_client.post = AsyncMock(return_value=fake_response)
          mock_client_cls.return_value = mock_client

          result = await embedder.embed_batch(["hello"])

      assert len(result) == 1
      assert len(result[0]) == 1024


  @pytest.mark.asyncio
  async def test_embed_batch_batches_large_inputs() -> None:
      """Large input is split into batches of batch_size=32."""
      embedder = ModalEmbedder("https://test.modal.run", batch_size=2)
      texts = ["a", "b", "c"]
      fake_response = MagicMock()
      fake_response.raise_for_status = MagicMock()
      fake_response.json.side_effect = [
          {"embeddings": [[0.1] * 1024, [0.2] * 1024]},
          {"embeddings": [[0.3] * 1024]},
      ]

      with patch("aeogen.crawl.embedder.httpx.AsyncClient") as mock_client_cls:
          mock_client = AsyncMock()
          mock_client.__aenter__ = AsyncMock(return_value=mock_client)
          mock_client.__aexit__ = AsyncMock(return_value=None)
          mock_client.post = AsyncMock(return_value=fake_response)
          mock_client_cls.return_value = mock_client

          result = await embedder.embed_batch(texts)

      assert len(result) == 3
      assert mock_client.post.call_count == 2


  @pytest.mark.asyncio
  async def test_embed_batch_empty_returns_empty() -> None:
      embedder = ModalEmbedder("https://test.modal.run")
      result = await embedder.embed_batch([])
      assert result == []


  @pytest.mark.asyncio
  async def test_embed_batch_http_error_propagates() -> None:
      import httpx
      embedder = ModalEmbedder("https://test.modal.run")
      with patch("aeogen.crawl.embedder.httpx.AsyncClient") as mock_client_cls:
          mock_client = AsyncMock()
          mock_client.__aenter__ = AsyncMock(return_value=mock_client)
          mock_client.__aexit__ = AsyncMock(return_value=None)
          mock_client.post = AsyncMock(side_effect=httpx.ConnectError("timeout"))
          mock_client_cls.return_value = mock_client

          with pytest.raises(httpx.ConnectError):
              await embedder.embed_batch(["test"])
  ```

- [ ] **Step 5.2: Run tests to verify RED**

  ```
  cd apps/api && uv run pytest tests/test_embedder.py -v
  ```

  Expected: `ImportError`.

- [ ] **Step 5.3: Implement embedder.py**

  Create `apps/api/src/aeogen/crawl/embedder.py`:

  ```python
  """D.4 — ModalEmbedder: HTTP client for Modal BGE-M3 embedding endpoint."""

  from __future__ import annotations

  import logging

  import httpx

  logger = logging.getLogger(__name__)

  _DEFAULT_BATCH_SIZE = 32
  _DEFAULT_TIMEOUT = 120.0


  class ModalEmbedder:
      """Calls the Modal BGE-M3 /embed endpoint in batches.

      Args:
          embed_url: Modal endpoint URL (e.g. https://user--app-embed.modal.run)
          batch_size: Max texts per HTTP request (BGE-M3 fits ~32 on L4)
          timeout: Per-request timeout in seconds
      """

      def __init__(
          self,
          embed_url: str,
          *,
          batch_size: int = _DEFAULT_BATCH_SIZE,
          timeout: float = _DEFAULT_TIMEOUT,
      ) -> None:
          self._url = embed_url.rstrip("/") + "/embed"
          self._batch_size = batch_size
          self._timeout = timeout

      async def embed_batch(self, texts: list[str]) -> list[list[float]]:
          """Embed a list of texts. Returns list of 1024-dim float vectors."""
          if not texts:
              return []

          results: list[list[float]] = []
          for i in range(0, len(texts), self._batch_size):
              batch = texts[i : i + self._batch_size]
              embeddings = await self._call(batch)
              results.extend(embeddings)

          return results

      async def _call(self, texts: list[str]) -> list[list[float]]:
          async with httpx.AsyncClient(timeout=self._timeout) as client:
              response = await client.post(self._url, json={"texts": texts})
              response.raise_for_status()
              data: dict[str, list[list[float]]] = response.json()
              return data["embeddings"]
  ```

- [ ] **Step 5.4 (TDD GREEN): Run tests**

  ```
  cd apps/api && uv run pytest tests/test_embedder.py -v
  ```

  Expected: 4 passed.

- [ ] **Step 5.5: ruff + mypy**

  ```
  cd apps/api && uv run ruff check src/aeogen/crawl/embedder.py && uv run mypy src --strict
  ```

  Expected: 0 errors, Success.

- [ ] **Step 5.6: Commit**

  ```
  git commit -m "feat(crawl/embedder): add ModalEmbedder HTTP client for BGE-M3 batch embedding (D.4)

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 6: SiteSpider (D.1 + D.7)

**Files:** `apps/api/src/aeogen/crawl/spider.py`, `apps/api/tests/test_spider.py`

- [ ] **Step 6.1 (TDD RED): Write failing tests**

  Create `apps/api/tests/test_spider.py`:

  ```python
  """D.1/D.7 SiteSpider unit tests — mocked Crawl4AI + httpx."""

  import hashlib
  from unittest.mock import AsyncMock, MagicMock, patch

  import pytest

  import os
  os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
  os.environ.setdefault("OPENROUTER_API_KEY", "test-key-" + "x" * 20)
  os.environ.setdefault("REDIS_URL", "rediss://:test@localhost:6380")
  os.environ.setdefault("MODAL_EMBED_URL", "https://test--aeogen-embed.modal.run")

  from aeogen.crawl.spider import CrawledPage, SiteSpider, _url_hash


  def test_url_hash_is_16_chars() -> None:
      h = _url_hash("https://example.com/page")
      assert len(h) == 16
      assert h.isalnum() or all(c in "0123456789abcdef" for c in h)


  def test_url_hash_deterministic() -> None:
      assert _url_hash("https://example.com") == _url_hash("https://example.com")


  @pytest.mark.asyncio
  async def test_spider_crawl_returns_pages() -> None:
      fake_result = MagicMock()
      fake_result.success = True
      fake_result.status_code = 200
      fake_result.html = "<html><body>Hello</body></html>"
      fake_result.markdown = "Hello"

      fake_crawler = AsyncMock()
      fake_crawler.__aenter__ = AsyncMock(return_value=fake_crawler)
      fake_crawler.__aexit__ = AsyncMock(return_value=None)
      fake_crawler.arun = AsyncMock(return_value=fake_result)

      with patch("aeogen.crawl.spider.AsyncWebCrawler", return_value=fake_crawler):
          with patch("aeogen.crawl.spider.SiteSpider._fetch_urls", return_value=["https://example.com/"]):
              spider = SiteSpider(rate_limit_rps=100.0)
              pages = await spider.crawl("https://example.com", max_pages=1)

      assert len(pages) == 1
      assert pages[0]["url"] == "https://example.com/"
      assert pages[0]["html"] == "<html><body>Hello</body></html>"
      assert pages[0]["status_code"] == 200


  @pytest.mark.asyncio
  async def test_spider_skips_failed_pages() -> None:
      fake_result = MagicMock()
      fake_result.success = False
      fake_result.status_code = 404
      fake_result.html = ""
      fake_result.markdown = ""

      fake_crawler = AsyncMock()
      fake_crawler.__aenter__ = AsyncMock(return_value=fake_crawler)
      fake_crawler.__aexit__ = AsyncMock(return_value=None)
      fake_crawler.arun = AsyncMock(return_value=fake_result)

      with patch("aeogen.crawl.spider.AsyncWebCrawler", return_value=fake_crawler):
          with patch("aeogen.crawl.spider.SiteSpider._fetch_urls", return_value=["https://example.com/404"]):
              spider = SiteSpider(rate_limit_rps=100.0)
              pages = await spider.crawl("https://example.com", max_pages=1)

      assert pages == []


  @pytest.mark.asyncio
  async def test_spider_respects_max_pages() -> None:
      fake_result = MagicMock()
      fake_result.success = True
      fake_result.status_code = 200
      fake_result.html = "<html></html>"
      fake_result.markdown = ""

      fake_crawler = AsyncMock()
      fake_crawler.__aenter__ = AsyncMock(return_value=fake_crawler)
      fake_crawler.__aexit__ = AsyncMock(return_value=None)
      fake_crawler.arun = AsyncMock(return_value=fake_result)

      urls = [f"https://example.com/page/{i}" for i in range(10)]
      with patch("aeogen.crawl.spider.AsyncWebCrawler", return_value=fake_crawler):
          with patch("aeogen.crawl.spider.SiteSpider._fetch_urls", return_value=urls):
              spider = SiteSpider(rate_limit_rps=100.0)
              pages = await spider.crawl("https://example.com", max_pages=3)

      assert len(pages) == 3


  @pytest.mark.asyncio
  async def test_fetch_sitemap_xml_parses_urls() -> None:
      sitemap_xml = """<?xml version="1.0"?>
  <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
    <url><loc>https://example.com/</loc></url>
    <url><loc>https://example.com/about</loc></url>
  </urlset>"""

      with patch("aeogen.crawl.spider.httpx.AsyncClient") as mock_client_cls:
          mock_client = AsyncMock()
          mock_client.__aenter__ = AsyncMock(return_value=mock_client)
          mock_client.__aexit__ = AsyncMock(return_value=None)
          mock_response = MagicMock()
          mock_response.status_code = 200
          mock_response.text = sitemap_xml
          mock_client.get = AsyncMock(return_value=mock_response)
          mock_client_cls.return_value = mock_client

          spider = SiteSpider(rate_limit_rps=100.0)
          urls = await spider._fetch_urls("https://example.com")

      assert "https://example.com/" in urls
      assert "https://example.com/about" in urls


  @pytest.mark.asyncio
  async def test_fetch_sitemap_xml_fallback_to_root() -> None:
      """If /sitemap.xml returns 404, fall back to root URL."""
      with patch("aeogen.crawl.spider.httpx.AsyncClient") as mock_client_cls:
          mock_client = AsyncMock()
          mock_client.__aenter__ = AsyncMock(return_value=mock_client)
          mock_client.__aexit__ = AsyncMock(return_value=None)
          mock_response = MagicMock()
          mock_response.status_code = 404
          mock_response.text = ""
          mock_client.get = AsyncMock(return_value=mock_response)
          mock_client_cls.return_value = mock_client

          spider = SiteSpider(rate_limit_rps=100.0)
          urls = await spider._fetch_urls("https://example.com")

      assert urls == ["https://example.com"]


  def test_crawled_page_storage_path() -> None:
      from aeogen.crawl.spider import storage_path
      path = storage_path("site-123", "https://example.com/page")
      assert path.startswith("crawls/site-123/")
      assert path.endswith(".html")
      assert len(path.split("/")[-1]) == 16 + 5  # hash(16) + ".html"(5)
  ```

- [ ] **Step 6.2: Run tests to verify RED**

  ```
  cd apps/api && uv run pytest tests/test_spider.py -v
  ```

  Expected: `ImportError`.

- [ ] **Step 6.3: Implement spider.py**

  Create `apps/api/src/aeogen/crawl/spider.py`:

  ```python
  """D.1/D.7 — SiteSpider: sitemap-driven async crawler + storage path helpers."""

  from __future__ import annotations

  import asyncio
  import hashlib
  import logging
  import xml.etree.ElementTree as ET
  from datetime import datetime, timezone
  from typing import TypedDict
  from urllib.parse import urljoin

  import httpx

  try:
      from crawl4ai import AsyncWebCrawler  # type: ignore[import-untyped]
  except ImportError:  # pragma: no cover
      AsyncWebCrawler = None  # type: ignore[assignment,misc]

  logger = logging.getLogger(__name__)

  _SITEMAP_NS = "http://www.sitemaps.org/schemas/sitemap/0.9"


  class CrawledPage(TypedDict):
      url: str
      html: str
      markdown: str
      status_code: int
      crawled_at: str  # ISO-8601 UTC


  def _url_hash(url: str) -> str:
      """Deterministic 16-char hex hash of a URL."""
      return hashlib.sha256(url.encode()).hexdigest()[:16]


  def storage_path(site_id: str, url: str) -> str:
      """Return Supabase Storage path for an HTML snapshot."""
      return f"crawls/{site_id}/{_url_hash(url)}.html"


  class SiteSpider:
      """Async spider: sitemap → crawl top-N pages with rate-limiting.

      Rate-limiting is enforced via asyncio.sleep (no Redis in unit tests).
      Production Celery task passes rate_limit_rps from settings.
      """

      def __init__(self, *, rate_limit_rps: float = 1.0) -> None:
          self._delay = 1.0 / rate_limit_rps if rate_limit_rps > 0 else 0.0

      async def crawl(
          self,
          site_url: str,
          *,
          max_pages: int = 50,
      ) -> list[CrawledPage]:
          """Crawl up to max_pages pages from site_url."""
          urls = await self._fetch_urls(site_url)
          urls = urls[:max_pages]

          pages: list[CrawledPage] = []
          async with AsyncWebCrawler() as crawler:
              for url in urls:
                  try:
                      result = await crawler.arun(url=url)
                      if not result.success:
                          logger.warning("Crawl failed for %s (status %s)", url, result.status_code)
                          continue
                      pages.append(
                          CrawledPage(
                              url=url,
                              html=result.html or "",
                              markdown=result.markdown or "",
                              status_code=result.status_code or 0,
                              crawled_at=datetime.now(timezone.utc).isoformat(),
                          )
                      )
                  except Exception:
                      logger.exception("Unexpected error crawling %s", url)

                  if self._delay > 0:
                      await asyncio.sleep(self._delay)

          return pages

      async def _fetch_urls(self, site_url: str) -> list[str]:
          """Fetch sitemap.xml and return URL list. Falls back to [site_url]."""
          sitemap_url = urljoin(site_url.rstrip("/") + "/", "sitemap.xml")
          try:
              async with httpx.AsyncClient(timeout=15.0) as client:
                  resp = await client.get(sitemap_url)
                  if resp.status_code != 200 or not resp.text.strip():
                      return [site_url]
                  return self._parse_sitemap(resp.text) or [site_url]
          except Exception:
              logger.exception("Failed to fetch sitemap from %s", sitemap_url)
              return [site_url]

      def _parse_sitemap(self, xml_text: str) -> list[str]:
          """Extract <loc> URLs from sitemap XML."""
          try:
              root = ET.fromstring(xml_text)
              tag = root.tag.split("}")[-1] if "}" in root.tag else root.tag
              ns = {"sm": _SITEMAP_NS}
              urls: list[str] = []
              for loc in root.findall(".//sm:loc", ns):
                  if loc.text:
                      urls.append(loc.text.strip())
              return urls
          except ET.ParseError:
              logger.warning("Sitemap XML parse error")
              return []
  ```

- [ ] **Step 6.4 (TDD GREEN): Run tests**

  ```
  cd apps/api && uv run pytest tests/test_spider.py -v
  ```

  Expected: 8 passed.

- [ ] **Step 6.5: ruff + mypy**

  ```
  cd apps/api && uv run ruff check src/aeogen/crawl/spider.py && uv run mypy src --strict
  ```

  Expected: 0 errors, Success. (Note: `crawl4ai` may need `# type: ignore[import-untyped]`)

- [ ] **Step 6.6: Commit**

  ```
  git commit -m "feat(crawl/spider): add SiteSpider with sitemap parsing and rate-limiting (D.1+D.7)

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 7: Celery app + crawl_site task (D.6) + tasks module

**Files:** `apps/api/src/aeogen/celery_app.py`, `apps/api/src/aeogen/tasks/__init__.py`, `apps/api/src/aeogen/tasks/crawl.py`, `apps/api/tests/test_crawl_task.py`

- [ ] **Step 7.1 (TDD RED): Write failing tests**

  Create `apps/api/tests/test_crawl_task.py`:

  ```python
  """D.6 crawl_site Celery task unit tests — mocked everything."""

  import os
  from unittest.mock import AsyncMock, MagicMock, patch
  from uuid import uuid4

  import pytest

  os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
  os.environ.setdefault("OPENROUTER_API_KEY", "test-key-" + "x" * 20)
  os.environ.setdefault("REDIS_URL", "rediss://:test@localhost:6380")
  os.environ.setdefault("MODAL_EMBED_URL", "https://test--aeogen-embed.modal.run")

  from aeogen.tasks.crawl import _run_crawl_pipeline


  @pytest.mark.asyncio
  async def test_run_crawl_pipeline_calls_spider() -> None:
      """Pipeline calls spider.crawl with correct site_url."""
      site_id = str(uuid4())
      run_id = str(uuid4())

      mock_spider = MagicMock()
      mock_spider.crawl = AsyncMock(return_value=[])
      mock_embedder = MagicMock()
      mock_embedder.embed_batch = AsyncMock(return_value=[])

      with patch("aeogen.tasks.crawl.SiteSpider", return_value=mock_spider):
          with patch("aeogen.tasks.crawl.ModalEmbedder", return_value=mock_embedder):
              with patch("aeogen.tasks.crawl._update_run_status", new_callable=AsyncMock):
                  with patch("aeogen.tasks.crawl._ingest_pages", new_callable=AsyncMock):
                      await _run_crawl_pipeline(
                          site_id=site_id,
                          site_url="https://example.com",
                          run_id=run_id,
                          max_pages=5,
                      )

      mock_spider.crawl.assert_awaited_once_with("https://example.com", max_pages=5)


  @pytest.mark.asyncio
  async def test_run_crawl_pipeline_updates_status_running() -> None:
      """Pipeline sets status=running before crawling."""
      site_id = str(uuid4())
      run_id = str(uuid4())

      mock_spider = MagicMock()
      mock_spider.crawl = AsyncMock(return_value=[])
      mock_embedder = MagicMock()
      mock_embedder.embed_batch = AsyncMock(return_value=[])

      status_calls: list[str] = []

      async def fake_update_status(run_id: str, status: str) -> None:
          status_calls.append(status)

      with patch("aeogen.tasks.crawl.SiteSpider", return_value=mock_spider):
          with patch("aeogen.tasks.crawl.ModalEmbedder", return_value=mock_embedder):
              with patch("aeogen.tasks.crawl._update_run_status", side_effect=fake_update_status):
                  with patch("aeogen.tasks.crawl._ingest_pages", new_callable=AsyncMock):
                      await _run_crawl_pipeline(
                          site_id=site_id,
                          site_url="https://example.com",
                          run_id=run_id,
                          max_pages=5,
                      )

      assert "running" in status_calls
      assert "completed" in status_calls


  @pytest.mark.asyncio
  async def test_run_crawl_pipeline_sets_failed_on_error() -> None:
      """Pipeline catches spider errors and sets status=failed."""
      site_id = str(uuid4())
      run_id = str(uuid4())

      mock_spider = MagicMock()
      mock_spider.crawl = AsyncMock(side_effect=RuntimeError("network down"))

      status_calls: list[str] = []

      async def fake_update_status(run_id: str, status: str) -> None:
          status_calls.append(status)

      with patch("aeogen.tasks.crawl.SiteSpider", return_value=mock_spider):
          with patch("aeogen.tasks.crawl.ModalEmbedder"):
              with patch("aeogen.tasks.crawl._update_run_status", side_effect=fake_update_status):
                  await _run_crawl_pipeline(
                      site_id=site_id,
                      site_url="https://example.com",
                      run_id=run_id,
                      max_pages=5,
                  )

      assert "failed" in status_calls


  @pytest.mark.asyncio
  async def test_ingest_pages_calls_embedder_and_writes_db() -> None:
      """_ingest_pages calls embedder.embed_batch and writes to DB."""
      from aeogen.crawl.spider import CrawledPage
      from aeogen.tasks.crawl import _ingest_pages

      page = CrawledPage(
          url="https://example.com/",
          html="<html></html>",
          markdown="Hello world",
          status_code=200,
          crawled_at="2026-05-23T00:00:00+00:00",
      )

      mock_embedder = MagicMock()
      mock_embedder.embed_batch = AsyncMock(return_value=[[0.1] * 1024])

      mock_db = AsyncMock()

      with patch("aeogen.tasks.crawl.PageParser") as mock_parser_cls:
          mock_parser = MagicMock()
          mock_parser.parse.return_value = {
              "url": "https://example.com/",
              "canonical_url": None,
              "og_title": None,
              "og_description": None,
              "og_type": None,
              "json_ld": [],
              "markdown": "Hello world",
              "word_count": 2,
          }
          mock_parser_cls.return_value = mock_parser

          with patch("aeogen.tasks.crawl.SemanticChunker") as mock_chunker_cls:
              mock_chunker = MagicMock()
              mock_chunker.chunk.return_value = [
                  {"text": "Hello world", "chunk_index": 0, "heading_context": "", "token_count": 2, "start_char": 0, "end_char": 11}
              ]
              mock_chunker_cls.return_value = mock_chunker

              await _ingest_pages(
                  pages=[page],
                  site_id="site-123",
                  workspace_id="ws-456",
                  run_id="run-789",
                  embedder=mock_embedder,
                  db_url="postgresql://test:test@localhost/db",
              )

      mock_embedder.embed_batch.assert_awaited_once_with(["Hello world"])


  def test_celery_app_is_importable() -> None:
      """Celery app can be imported without a running broker."""
      from aeogen.celery_app import celery_app
      assert celery_app.main == "aeogen"
  ```

- [ ] **Step 7.2: Run tests to verify RED**

  ```
  cd apps/api && uv run pytest tests/test_crawl_task.py -v
  ```

  Expected: `ImportError`.

- [ ] **Step 7.3: Create celery_app.py**

  Create `apps/api/src/aeogen/celery_app.py`:

  ```python
  """Celery application — Upstash Redis broker + result backend."""

  from __future__ import annotations

  from celery import Celery

  from aeogen.settings import get_settings

  _settings = get_settings()
  _redis_url = str(_settings.redis_url)

  celery_app = Celery(
      "aeogen",
      broker=_redis_url,
      backend=_redis_url,
      include=["aeogen.tasks.crawl"],
  )

  celery_app.conf.update(
      task_serializer="json",
      accept_content=["json"],
      result_serializer="json",
      timezone="UTC",
      enable_utc=True,
      broker_connection_retry_on_startup=True,
      task_track_started=True,
      task_acks_late=True,
      worker_prefetch_multiplier=1,
  )
  ```

- [ ] **Step 7.4: Create tasks/**init**.py**

  ```python
  """Celery task modules."""
  ```

- [ ] **Step 7.5: Create tasks/crawl.py**

  Create `apps/api/src/aeogen/tasks/crawl.py`:

  ```python
  """D.6 — crawl_site Celery task + async pipeline helpers."""

  from __future__ import annotations

  import asyncio
  import json
  import logging
  from typing import Any

  import psycopg

  from aeogen.celery_app import celery_app
  from aeogen.crawl.chunker import SemanticChunker
  from aeogen.crawl.embedder import ModalEmbedder
  from aeogen.crawl.parser import PageParser
  from aeogen.crawl.spider import CrawledPage, PageParser as _PageParserAlias, SiteSpider, storage_path
  from aeogen.settings import get_settings

  logger = logging.getLogger(__name__)


  @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[misc]
  def crawl_site(self: Any, site_id: str, run_id: str) -> None:  # noqa: ANN401
      """Celery entry point — wraps async pipeline in asyncio.run()."""
      settings = get_settings()
      # Fetch site URL from DB (stub: use site_id as placeholder until Faz 5 wires it)
      site_url = f"https://example.com"  # TODO: load from public.sites via site_id (Faz 5)
      try:
          asyncio.run(
              _run_crawl_pipeline(
                  site_id=site_id,
                  site_url=site_url,
                  run_id=run_id,
                  max_pages=settings.crawl_top_pages,
              )
          )
      except Exception as exc:
          logger.exception("crawl_site task failed for site_id=%s", site_id)
          raise self.retry(exc=exc, countdown=60 * (2 ** self.request.retries))


  async def _run_crawl_pipeline(
      *,
      site_id: str,
      site_url: str,
      run_id: str,
      max_pages: int,
  ) -> None:
      """Async pipeline: spider → parse → chunk → embed → ingest."""
      settings = get_settings()
      spider = SiteSpider(rate_limit_rps=settings.crawl_rate_limit_rps)
      embedder = ModalEmbedder(str(settings.modal_embed_url))

      await _update_run_status(run_id, "running")
      try:
          pages = await spider.crawl(site_url, max_pages=max_pages)
          logger.info("Crawled %d pages for site_id=%s", len(pages), site_id)

          await _ingest_pages(
              pages=pages,
              site_id=site_id,
              workspace_id="",  # TODO: load from public.sites (Faz 5)
              run_id=run_id,
              embedder=embedder,
              db_url=str(settings.database_url),
          )
          await _update_run_status(run_id, "completed")
      except Exception:
          logger.exception("Pipeline failed for run_id=%s", run_id)
          await _update_run_status(run_id, "failed")


  async def _update_run_status(run_id: str, status: str) -> None:
      """Update analysis_runs.status in Postgres."""
      settings = get_settings()
      try:
          conn = await psycopg.AsyncConnection.connect(str(settings.database_url))
          async with conn, conn.cursor() as cur:
              await cur.execute(
                  "UPDATE public.analysis_runs SET status = %s WHERE id = %s AND deleted_at IS NULL",
                  (status, run_id),
              )
              await conn.commit()
      except Exception:
          logger.exception("Failed to update run status run_id=%s status=%s", run_id, status)


  async def _ingest_pages(
      *,
      pages: list[CrawledPage],
      site_id: str,
      workspace_id: str,
      run_id: str,
      embedder: ModalEmbedder,
      db_url: str,
  ) -> None:
      """Parse, chunk, embed, and write pages to DB."""
      parser = PageParser()
      chunker = SemanticChunker()

      for page in pages:
          parsed = parser.parse(page["html"], url=page["url"], markdown=page["markdown"])
          chunks = chunker.chunk(parsed["markdown"])

          if not chunks:
              continue

          texts = [c["text"] for c in chunks]
          embeddings = await embedder.embed_batch(texts)

          conn = await psycopg.AsyncConnection.connect(db_url)
          async with conn, conn.cursor() as cur:
              for chunk, embedding in zip(chunks, embeddings, strict=True):
                  await cur.execute(
                      """
                      INSERT INTO public.embeddings
                        (page_id, workspace_id, chunk_text, embedding, chunk_index, model_name)
                      VALUES (%s, %s, %s, %s::vector, %s, %s)
                      ON CONFLICT (page_id, chunk_index)
                      DO UPDATE SET
                        chunk_text = EXCLUDED.chunk_text,
                        embedding = EXCLUDED.embedding,
                        model_name = EXCLUDED.model_name
                      """,
                      (
                          None,  # page_id — TODO: upsert page record first (Faz 5)
                          workspace_id or None,
                          chunk["text"],
                          json.dumps(embedding),
                          chunk["chunk_index"],
                          "bge-m3",
                      ),
                  )
              await conn.commit()
          logger.info("Ingested %d chunks for url=%s", len(chunks), page["url"])
  ```

- [ ] **Step 7.6 (TDD GREEN): Run tests**

  ```
  cd apps/api && uv run pytest tests/test_crawl_task.py -v
  ```

  Expected: 5 passed.

- [ ] **Step 7.7: ruff + mypy on new files**

  ```
  cd apps/api && uv run ruff check src/aeogen/celery_app.py src/aeogen/tasks/ && uv run mypy src --strict
  ```

  Expected: 0 errors, Success. (Fix any ANN/RUF issues before moving on.)

- [ ] **Step 7.8: Full suite**

  ```
  cd apps/api && uv run pytest tests/ -v
  ```

  Expected: 44 + 28 = 72 tests passed.

- [ ] **Step 7.9: Commit**

  ```
  git add apps/api/src/aeogen/celery_app.py apps/api/src/aeogen/tasks/ apps/api/tests/test_crawl_task.py
  git commit -m "feat(tasks/crawl): add crawl_site Celery task + async pipeline (D.6)

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 8: Modal BGE-M3 service (D.4 server)

**Files:** `infra/modal/embedding_service.py`

> **Note:** This file runs in the Modal cloud environment, NOT in `apps/api`. It has
> its own deps (modal, FlagEmbedding, torch). No uv/pytest integration — deployment
> is via `modal deploy infra/modal/embedding_service.py`.

- [ ] **Step 8.1: Create infra/modal/ directory**

  ```
  mkdir -p infra/modal
  ```

- [ ] **Step 8.2: Write embedding_service.py**

  Create `infra/modal/embedding_service.py`:

  ```python
  """Modal BGE-M3 embedding service — serverless GPU endpoint.

  Deploy: modal deploy infra/modal/embedding_service.py
  Endpoint: POST /embed {"texts": [...]} → {"embeddings": [[...]]}
  GPU: L4 (1024-dim BGE-M3, multilingual)
  """

  from __future__ import annotations

  import modal

  app = modal.App("aeogen-embed")

  _image = (
      modal.Image.debian_slim(python_version="3.12")
      .pip_install(
          "FlagEmbedding>=1.4",
          "torch>=2.3",
          "transformers>=4.40",
          "numpy>=1.26",
      )
  )

  MODEL_NAME = "BAAI/bge-m3"
  _BATCH_SIZE = 32


  @app.cls(
      gpu="L4",
      image=_image,
      timeout=300,
      scaledown_window=60,  # Keep warm for 60s after last request
  )
  class EmbeddingService:
      """BGE-M3 model loaded once per container, batches requests."""

      @modal.enter()
      def load_model(self) -> None:
          from FlagEmbedding import BGEM3FlagModel  # type: ignore[import-untyped]
          self._model = BGEM3FlagModel(MODEL_NAME, use_fp16=True)

      @modal.web_endpoint(method="POST")
      def embed(self, request: dict) -> dict:  # type: ignore[type-arg]
          texts: list[str] = request.get("texts", [])
          if not texts:
              return {"embeddings": []}

          results: list[list[float]] = []
          for i in range(0, len(texts), _BATCH_SIZE):
              batch = texts[i : i + _BATCH_SIZE]
              output = self._model.encode(
                  batch,
                  batch_size=_BATCH_SIZE,
                  max_length=512,
                  return_dense=True,
                  return_sparse=False,
                  return_colbert_vecs=False,
              )
              dense: list[list[float]] = output["dense_vecs"].tolist()
              results.extend(dense)

          return {"embeddings": results}
  ```

- [ ] **Step 8.3: Add infra/modal/requirements.txt (for documentation)**

  ```
  # Requirements for infra/modal/embedding_service.py (Modal cloud, NOT apps/api)
  # Installed via modal.Image.pip_install() in the script.
  # modal>=0.73
  # FlagEmbedding>=1.4
  # torch>=2.3
  # transformers>=4.40
  ```

- [ ] **Step 8.4: Add infra/modal/.gitignore**

  ```
  __pycache__/
  *.pyc
  .modal/
  ```

- [ ] **Step 8.5: Deploy (user action)**

  Run from repo root:

  ```
  pip install modal  # if not installed globally
  modal deploy infra/modal/embedding_service.py
  ```

  Expected output:

  ```
  ✓ Created objects.
  ✓ EmbeddingService.embed => https://<username>--aeogen-embed-embed.modal.run
  ```

  Copy the URL → set `MODAL_EMBED_URL=https://...` in your env.

- [ ] **Step 8.6: Commit infra/modal**

  ```
  git add infra/modal/
  git commit -m "feat(infra/modal): add BGE-M3 embedding service for Modal serverless GPU (D.4)

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 9: Settings update commit + CI update

**Files:** `apps/api/src/aeogen/settings.py`, `apps/api/.env.example`, `.github/workflows/ci.yml`

- [ ] **Step 9.1: Commit settings + env changes (from Task 1)**
      These were already done in Task 1 but should be staged with the feature branch:

  ```
  git add apps/api/src/aeogen/settings.py apps/api/.env.example apps/api/tests/conftest.py apps/api/pyproject.toml
  git commit -m "feat(api/settings): add REDIS_URL, MODAL_EMBED_URL, crawl knobs (D.1+D.6)

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

- [ ] **Step 9.2: Update CI**

  In `.github/workflows/ci.yml`, in the `python-checks` job `env:` block, add:

  ```yaml
  REDIS_URL: rediss://:test@localhost:6380
  MODAL_EMBED_URL: https://test--aeogen-embed.modal.run
  ```

  Also add a Playwright install step before pytest:

  ```yaml
  - name: Install Playwright browsers
    run: uv run playwright install --with-deps chromium
    working-directory: apps/api
  ```

- [ ] **Step 9.3: Full verification**

  ```
  cd apps/api && uv run pytest tests/ -v --tb=short
  ```

  Expected: all new + existing tests pass.

  ```
  cd apps/api && uv run mypy src --strict
  ```

  Expected: Success.

  ```
  cd apps/api && uv run ruff check src/ && uv run ruff format --check src/
  ```

  Expected: 0 errors.

- [ ] **Step 9.4: Commit CI changes**

  ```
  git add .github/workflows/ci.yml
  git commit -m "ci: add REDIS_URL, MODAL_EMBED_URL, Playwright install to python-checks (D)

  Co-Authored-By: Claude Sonnet 4.6 <noreply@anthropic.com>"
  ```

---

## Task 10: Push feature branch + open PR

- [ ] **Step 10.1: Push feature branch**

  ```
  git push -u origin feature/D-crawl-ingestion
  ```

- [ ] **Step 10.2: Open PR to dev**

  ```
  gh pr create --base dev --head feature/D-crawl-ingestion \
    --title "feat(crawl): Faz 4 D — crawl & ingestion pipeline (spider + parser + chunker + embedder + Celery)" \
    --body "..."
  ```

- [ ] **Step 10.3: Wait for CI + merge**
  ```
  gh pr merge --merge --delete-branch --admin
  ```

---

## Self-review checklist

- [ ] All 5 test files created (test_parser, test_chunker, test_embedder, test_spider, test_crawl_task)
- [ ] TDD RED → GREEN verified for each module
- [ ] ruff + mypy strict on every new file
- [ ] No real network calls in tests (all mocked)
- [ ] coverage ≥80% on aeogen.crawl + aeogen.tasks
- [ ] No secrets hardcoded (REDIS_URL, MODAL_EMBED_URL only via env)
- [ ] `crawl4ai` import guarded with `try/except ImportError` in spider.py (for import without Playwright in test env)
- [ ] `.env.example` updated
- [ ] CI updated (env vars + Playwright install)
- [ ] Modal service written and deployer instructions documented
