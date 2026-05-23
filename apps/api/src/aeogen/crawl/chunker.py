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
            sub = self._split_section(section_text)
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
            pre = text[: positions[0]].strip()
            if pre:
                parts.append(("", pre))

        for i, pos in enumerate(positions):
            end = positions[i + 1] if i + 1 < len(positions) else len(text)
            section = text[pos:end]
            first_line_end = section.index("\n") if "\n" in section else len(section)
            heading = section[:first_line_end].lstrip("#").strip()
            body = section[first_line_end:].strip()
            if body:
                parts.append((heading, body))

        return [(h, b) for h, b in parts if b.strip()]

    def _split_section(self, text: str) -> list[tuple[str, int, int]]:
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
