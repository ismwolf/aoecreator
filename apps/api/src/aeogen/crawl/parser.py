"""D.2 — PageParser: schema.org JSON-LD + Open Graph meta + canonical extraction."""

from __future__ import annotations

import json
import logging
from html.parser import HTMLParser
from typing import TypedDict

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
            prop = attrs_dict.get("property") or ""
            name = attrs_dict.get("name") or ""
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
                    for item in parsed:
                        if isinstance(item, dict):
                            self.json_ld.append(item)
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
