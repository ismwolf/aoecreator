"""D.3 SemanticChunker unit tests."""

from aeogen.crawl.chunker import SemanticChunker

_SHORT_MD = "Hello world."

_HEADING_MD = """# Section A

Alpha beta gamma delta.

## Section B

Epsilon zeta eta theta iota kappa.
"""

_LONG_SECTION = "word " * 600  # ~600 tokens > 512


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
