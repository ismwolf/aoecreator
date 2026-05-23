"""D.1/D.7 — SiteSpider: sitemap-driven async crawler + storage path helpers."""

from __future__ import annotations

import asyncio
import hashlib
import logging
import xml.etree.ElementTree as ET
from datetime import UTC, datetime
from typing import TypedDict
from urllib.parse import urljoin

import httpx

try:
    from crawl4ai import AsyncWebCrawler  # type: ignore[import-untyped]
except ImportError:  # pragma: no cover
    AsyncWebCrawler = None  # type: ignore[assignment,misc,unused-ignore]

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
    """Async spider: sitemap -> crawl top-N pages with rate-limiting.

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
                            crawled_at=datetime.now(UTC).isoformat(),
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
            ns = {"sm": _SITEMAP_NS}
            urls: list[str] = []
            for loc in root.findall(".//sm:loc", ns):
                if loc.text:
                    urls.append(loc.text.strip())
            return urls
        except ET.ParseError:
            logger.warning("Sitemap XML parse error")
            return []
