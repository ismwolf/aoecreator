"""D.2 PageParser unit tests — pure HTML, no network."""

from aeogen.crawl.parser import PageParser

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
