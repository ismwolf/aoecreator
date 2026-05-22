"""Shared pytest fixtures for apps/api tests.

Env injection runs at module import time (before any fixtures resolve) so that
the cached Settings instance is built from the test env, not from a stray
developer `.env.local`.
"""

import os
from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

# ----------------------------------------------------------------------
# Supabase env injection (A.T8)
# Settings declares 3 required Supabase fields. Inject test values BEFORE
# `aeogen.main` / `aeogen.settings` are imported below.
# ----------------------------------------------------------------------
os.environ.setdefault("SUPABASE_URL", "https://test.supabase.co")
os.environ.setdefault("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test_" + "x" * 20)
os.environ.setdefault("SUPABASE_SECRET_KEY", "sb_secret_test_" + "x" * 20)
# C.2: DATABASE_URL is required by Settings. Fake DSN — tests never connect.
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/test")
# C.3: OpenRouter API key — not a real key, tests mock ChatOpenAI anyway
os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key-" + "x" * 20)

from aeogen.main import create_app
from aeogen.settings import get_settings

# Drop any cached settings imported transitively before env was set.
get_settings.cache_clear()


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    """Yield an httpx AsyncClient bound to a fresh FastAPI app instance."""
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
