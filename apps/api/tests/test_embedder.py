"""D.4 ModalEmbedder unit tests — mocked httpx."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")
os.environ.setdefault("OPENROUTER_API_KEY", "test-key-" + "x" * 20)
os.environ.setdefault("REDIS_URL", "rediss://:test@localhost:6380")
os.environ.setdefault("MODAL_EMBED_URL", "https://test--aeogen-embed.modal.run")

from aeogen.crawl.embedder import ModalEmbedder


@pytest.mark.asyncio
async def test_embed_batch_returns_embeddings() -> None:
    embedder = ModalEmbedder("https://test.modal.run")
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.return_value = {"embeddings": [[0.1] * 1024]}

    with patch("aeogen.crawl.embedder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=fake_response)
        mock_client_cls.return_value = mock_client

        result = await embedder.embed_batch(["hello"])

    assert len(result) == 1
    assert len(result[0]) == 1024


@pytest.mark.asyncio
async def test_embed_batch_batches_large_inputs() -> None:
    """Large input is split into batches of batch_size."""
    embedder = ModalEmbedder("https://test.modal.run", batch_size=2)
    texts = ["a", "b", "c"]
    fake_response = MagicMock()
    fake_response.raise_for_status = MagicMock()
    fake_response.json.side_effect = [
        {"embeddings": [[0.1] * 1024, [0.2] * 1024]},
        {"embeddings": [[0.3] * 1024]},
    ]

    with patch("aeogen.crawl.embedder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(return_value=fake_response)
        mock_client_cls.return_value = mock_client

        result = await embedder.embed_batch(texts)

    assert len(result) == 3
    assert mock_client.post.call_count == 2


@pytest.mark.asyncio
async def test_embed_batch_empty_returns_empty() -> None:
    embedder = ModalEmbedder("https://test.modal.run")
    result = await embedder.embed_batch([])
    assert result == []


@pytest.mark.asyncio
async def test_embed_batch_http_error_propagates() -> None:
    import httpx

    embedder = ModalEmbedder("https://test.modal.run")
    with patch("aeogen.crawl.embedder.httpx.AsyncClient") as mock_client_cls:
        mock_client = AsyncMock()
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)
        mock_client.post = AsyncMock(side_effect=httpx.ConnectError("timeout"))
        mock_client_cls.return_value = mock_client

        with pytest.raises(httpx.ConnectError):
            await embedder.embed_batch(["test"])
