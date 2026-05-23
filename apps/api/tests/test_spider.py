"""D.1/D.7 SiteSpider unit tests — mocked Crawl4AI + httpx."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-" + "x" * 20)
os.environ.setdefault("REDIS_URL", "rediss://:test@localhost:6380")
os.environ.setdefault("MODAL_EMBED_URL", "https://test--aeogen-embed.modal.run")

from aeogen.crawl.spider import SiteSpider, _url_hash


def test_url_hash_is_16_chars() -> None:
    h = _url_hash("https://example.com/page")
    assert len(h) == 16
    assert all(c in "0123456789abcdef" for c in h)


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

    with (
        patch("aeogen.crawl.spider.AsyncWebCrawler", return_value=fake_crawler),
        patch(
            "aeogen.crawl.spider.SiteSpider._fetch_urls",
            return_value=["https://example.com/"],
        ),
    ):
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

    with (
        patch("aeogen.crawl.spider.AsyncWebCrawler", return_value=fake_crawler),
        patch(
            "aeogen.crawl.spider.SiteSpider._fetch_urls",
            return_value=["https://example.com/404"],
        ),
    ):
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
    with (
        patch("aeogen.crawl.spider.AsyncWebCrawler", return_value=fake_crawler),
        patch("aeogen.crawl.spider.SiteSpider._fetch_urls", return_value=urls),
    ):
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
