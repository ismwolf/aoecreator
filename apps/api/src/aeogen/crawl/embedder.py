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
