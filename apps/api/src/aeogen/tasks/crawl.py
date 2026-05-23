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
from aeogen.crawl.spider import CrawledPage, SiteSpider
from aeogen.settings import get_settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def crawl_site(self: Any, site_id: str, run_id: str) -> None:  # noqa: ANN401
    """Celery entry point — wraps async pipeline in asyncio.run()."""
    settings = get_settings()
    # TODO(Faz 5): load site_url from public.sites via site_id.
    site_url = "https://example.com"
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
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries)) from exc


async def _run_crawl_pipeline(
    *,
    site_id: str,
    site_url: str,
    run_id: str,
    max_pages: int,
) -> None:
    """Async pipeline: spider -> parse -> chunk -> embed -> ingest."""
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
            workspace_id="",  # TODO(Faz 5): load from public.sites.
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
                "UPDATE public.analysis_runs SET status = %s "
                "WHERE id = %s AND deleted_at IS NULL",
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
                        None,  # page_id — TODO(Faz 5): upsert page record first.
                        workspace_id or None,
                        chunk["text"],
                        json.dumps(embedding),
                        chunk["chunk_index"],
                        "bge-m3",
                    ),
                )
            await conn.commit()
        logger.info(
            "Ingested %d chunks for url=%s (site_id=%s, run_id=%s)",
            len(chunks),
            page["url"],
            site_id,
            run_id,
        )
