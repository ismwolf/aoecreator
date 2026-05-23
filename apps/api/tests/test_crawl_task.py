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

    with (
        patch("aeogen.tasks.crawl.SiteSpider", return_value=mock_spider),
        patch("aeogen.tasks.crawl.ModalEmbedder", return_value=mock_embedder),
        patch("aeogen.tasks.crawl._update_run_status", new_callable=AsyncMock),
        patch("aeogen.tasks.crawl._ingest_pages", new_callable=AsyncMock),
    ):
        await _run_crawl_pipeline(
            site_id=site_id,
            site_url="https://example.com",
            run_id=run_id,
            max_pages=5,
        )

    mock_spider.crawl.assert_awaited_once_with("https://example.com", max_pages=5)


@pytest.mark.asyncio
async def test_run_crawl_pipeline_updates_status_running() -> None:
    """Pipeline sets status=running before crawling and completed after."""
    site_id = str(uuid4())
    run_id = str(uuid4())

    mock_spider = MagicMock()
    mock_spider.crawl = AsyncMock(return_value=[])
    mock_embedder = MagicMock()
    mock_embedder.embed_batch = AsyncMock(return_value=[])

    status_calls: list[str] = []

    async def fake_update_status(run_id: str, status: str) -> None:
        status_calls.append(status)

    with (
        patch("aeogen.tasks.crawl.SiteSpider", return_value=mock_spider),
        patch("aeogen.tasks.crawl.ModalEmbedder", return_value=mock_embedder),
        patch("aeogen.tasks.crawl._update_run_status", side_effect=fake_update_status),
        patch("aeogen.tasks.crawl._ingest_pages", new_callable=AsyncMock),
    ):
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

    with (
        patch("aeogen.tasks.crawl.SiteSpider", return_value=mock_spider),
        patch("aeogen.tasks.crawl.ModalEmbedder"),
        patch("aeogen.tasks.crawl._update_run_status", side_effect=fake_update_status),
    ):
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

    # Stub psycopg.AsyncConnection.connect so no real DB call happens.
    mock_cursor = AsyncMock()
    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cursor)
    mock_cursor.__aenter__ = AsyncMock(return_value=mock_cursor)
    mock_cursor.__aexit__ = AsyncMock(return_value=None)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)

    with (
        patch("aeogen.tasks.crawl.PageParser") as mock_parser_cls,
        patch("aeogen.tasks.crawl.SemanticChunker") as mock_chunker_cls,
        patch(
            "aeogen.tasks.crawl.psycopg.AsyncConnection.connect",
            new=AsyncMock(return_value=mock_conn),
        ),
    ):
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

        mock_chunker = MagicMock()
        mock_chunker.chunk.return_value = [
            {
                "text": "Hello world",
                "chunk_index": 0,
                "heading_context": "",
                "token_count": 2,
                "start_char": 0,
                "end_char": 11,
            }
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
