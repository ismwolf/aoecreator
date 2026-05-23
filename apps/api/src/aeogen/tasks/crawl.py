"""D.6 — crawl_site Celery task + async pipeline helpers."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

import psycopg
import psycopg.rows
from supabase import create_client

from aeogen.celery_app import celery_app
from aeogen.crawl.chunker import SemanticChunker
from aeogen.crawl.embedder import ModalEmbedder
from aeogen.crawl.parser import PageParser
from aeogen.crawl.spider import CrawledPage, SiteSpider, storage_path
from aeogen.settings import get_settings

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, default_retry_delay=60)  # type: ignore[untyped-decorator]
def crawl_site(self: Any, site_id: str, run_id: str) -> None:  # noqa: ANN401
    """Celery entry point — wraps async pipeline in asyncio.run()."""
    settings = get_settings()
    try:
        asyncio.run(
            _run_crawl_pipeline(
                site_id=site_id,
                run_id=run_id,
                max_pages=settings.crawl_top_pages,
                db_url=str(settings.database_url),
                supabase_url=str(settings.supabase_url),
                supabase_key=settings.supabase_secret_key.get_secret_value(),
                modal_embed_url=str(settings.modal_embed_url),
                rate_limit_rps=settings.crawl_rate_limit_rps,
            )
        )
    except Exception as exc:
        logger.exception("crawl_site task failed for site_id=%s", site_id)
        raise self.retry(exc=exc, countdown=60 * (2**self.request.retries)) from exc


async def _get_site_info(site_id: str, db_url: str) -> tuple[str, str] | None:
    """Fetch (site_url, workspace_id) from public.sites. Returns None if not found."""
    conn = await psycopg.AsyncConnection.connect(db_url, row_factory=psycopg.rows.dict_row)
    async with conn, conn.cursor() as cur:
        await cur.execute(
            "SELECT url, workspace_id FROM public.sites WHERE id = %s AND deleted_at IS NULL",
            (site_id,),
        )
        row = await cur.fetchone()
    if row is None:
        return None
    return str(row["url"]), str(row["workspace_id"])


async def _run_crawl_pipeline(
    *,
    site_id: str,
    run_id: str,
    max_pages: int,
    db_url: str,
    supabase_url: str,
    supabase_key: str,
    modal_embed_url: str,
    rate_limit_rps: float,
) -> None:
    """Async pipeline: resolve site → spider → parse → chunk → embed → ingest."""
    site_info = await _get_site_info(site_id, db_url)
    if site_info is None:
        logger.error("Site not found: site_id=%s", site_id)
        await _update_run_status(run_id, "failed", db_url=db_url)
        raise ValueError(f"Site not found: {site_id}")

    site_url, workspace_id = site_info
    spider = SiteSpider(rate_limit_rps=rate_limit_rps)
    embedder = ModalEmbedder(modal_embed_url)

    await _update_run_status(run_id, "running", db_url=db_url)
    try:
        pages = await spider.crawl(site_url, max_pages=max_pages)
        logger.info("Crawled %d pages for site_id=%s", len(pages), site_id)

        await _ingest_pages(
            pages=pages,
            site_id=site_id,
            workspace_id=workspace_id,
            run_id=run_id,
            embedder=embedder,
            db_url=db_url,
            supabase_url=supabase_url,
            supabase_key=supabase_key,
        )
        await _update_run_status(run_id, "succeeded", db_url=db_url)
    except Exception:
        logger.exception("Pipeline failed for run_id=%s", run_id)
        await _update_run_status(run_id, "failed", db_url=db_url)
        raise  # re-raise so Celery self.retry() fires


async def _update_run_status(run_id: str, status: str, *, db_url: str) -> None:
    """Update analysis_runs.status + timestamps.

    Valid status values: 'queued' | 'running' | 'succeeded' | 'failed' | 'cancelled'
    """
    try:
        conn = await psycopg.AsyncConnection.connect(db_url)
        async with conn, conn.cursor() as cur:
            if status == "running":
                await cur.execute(
                    "UPDATE public.analysis_runs SET status=%s, started_at=now() "
                    "WHERE id=%s AND deleted_at IS NULL",
                    (status, run_id),
                )
            elif status in ("succeeded", "failed", "cancelled"):
                await cur.execute(
                    "UPDATE public.analysis_runs SET status=%s, finished_at=now() "
                    "WHERE id=%s AND deleted_at IS NULL",
                    (status, run_id),
                )
            else:
                await cur.execute(
                    "UPDATE public.analysis_runs SET status=%s "
                    "WHERE id=%s AND deleted_at IS NULL",
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
    supabase_url: str,
    supabase_key: str,
) -> None:
    """D.2+D.3+D.4+D.5+D.7 — Parse, chunk, embed, and persist pages."""
    parser = PageParser()
    chunker = SemanticChunker()

    for page in pages:
        # D.2: Parse HTML → structured metadata
        parsed = parser.parse(page["html"], url=page["url"], markdown=page["markdown"])

        # D.7: Upload HTML snapshot to Supabase Storage (private bucket 'crawls')
        html_path = storage_path(site_id, page["url"])
        try:
            sb = create_client(supabase_url, supabase_key)
            await asyncio.to_thread(
                sb.storage.from_("crawls").upload,
                html_path,
                page["html"].encode("utf-8"),
                {"content-type": "text/html; charset=utf-8", "upsert": "true"},
            )
        except Exception:
            logger.exception("HTML snapshot upload failed for %s", page["url"])

        # Compute content_hash (sha256 hex, 64 chars — matches pages.content_hash CHECK)
        content_hash = hashlib.sha256(page["html"].encode()).hexdigest()

        # Upsert page record → RETURNING id (prerequisite for embeddings.page_id FK)
        conn = await psycopg.AsyncConnection.connect(db_url, row_factory=psycopg.rows.dict_row)
        async with conn, conn.cursor() as cur:
            await cur.execute(
                """
                INSERT INTO public.pages
                  (workspace_id, site_id, url, html_path,
                   parsed_content, content_hash, last_crawled_at)
                VALUES (%s, %s, %s, %s, %s::jsonb, %s, now())
                ON CONFLICT (site_id, url) WHERE deleted_at IS NULL
                DO UPDATE SET
                  html_path       = EXCLUDED.html_path,
                  parsed_content  = EXCLUDED.parsed_content,
                  content_hash    = EXCLUDED.content_hash,
                  last_crawled_at = now()
                RETURNING id
                """,
                (
                    workspace_id,
                    site_id,
                    page["url"],
                    html_path,
                    json.dumps(dict(parsed)),
                    content_hash,
                ),
            )
            page_row = await cur.fetchone()
            await conn.commit()

        if page_row is None:
            logger.error("Failed to upsert page record for %s", page["url"])
            continue
        page_id = str(page_row["id"])

        # D.3: Semantic chunking
        chunks = chunker.chunk(parsed["markdown"])
        if not chunks:
            continue

        # D.4: Embed via Modal BGE-M3
        texts = [c["text"] for c in chunks]
        embeddings = await embedder.embed_batch(texts)

        # D.5: Upsert embeddings (correct schema: chunk_id/content/extensions.vector)
        conn2 = await psycopg.AsyncConnection.connect(db_url)
        async with conn2, conn2.cursor() as cur2:
            for chunk, embedding in zip(chunks, embeddings, strict=True):
                # PostgreSQL vector literal format: [x,y,z,...]
                vec_str = "[" + ",".join(str(v) for v in embedding) + "]"
                await cur2.execute(
                    """
                    INSERT INTO public.embeddings
                      (workspace_id, page_id, chunk_id, content, embedding, embedding_sparse)
                    VALUES (%s, %s, %s, %s, %s::extensions.vector, '{}'::jsonb)
                    ON CONFLICT (page_id, chunk_id) WHERE deleted_at IS NULL
                    DO UPDATE SET
                      content   = EXCLUDED.content,
                      embedding = EXCLUDED.embedding
                    """,
                    (
                        workspace_id,
                        page_id,
                        chunk["chunk_index"],
                        chunk["text"],
                        vec_str,
                    ),
                )
            await conn2.commit()

        logger.info(
            "Ingested %d chunks for url=%s (site_id=%s run_id=%s)",
            len(chunks),
            page["url"],
            site_id,
            run_id,
        )
