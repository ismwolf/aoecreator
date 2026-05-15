"""Shared pytest fixtures for apps/api tests."""

from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from aeogen.main import create_app


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Yield an httpx AsyncClient bound to a fresh FastAPI app instance."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
