"""C.4 SupabaseMemoryBackend tests (mocked — no real DB calls)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")

from aeogen.agents.core.memory import SupabaseMemoryBackend
from aeogen.agents.core.types import MemoryHit

_DSN = "postgresql://test:test@localhost:5432/testdb"


def _make_mock_conn(
    fetchone_result: object = None,
    fetchall_result: list[object] | None = None,
) -> tuple[AsyncMock, AsyncMock]:
    """Return (mock_conn, mock_cursor) wired for async context manager use."""
    mock_cur = AsyncMock()
    mock_cur.fetchone = AsyncMock(return_value=fetchone_result)
    mock_cur.fetchall = AsyncMock(return_value=fetchall_result or [])
    mock_cur.__aenter__ = AsyncMock(return_value=mock_cur)
    mock_cur.__aexit__ = AsyncMock(return_value=None)

    mock_conn = AsyncMock()
    mock_conn.cursor = MagicMock(return_value=mock_cur)
    mock_conn.__aenter__ = AsyncMock(return_value=mock_conn)
    mock_conn.__aexit__ = AsyncMock(return_value=None)
    mock_conn.commit = AsyncMock()

    return mock_conn, mock_cur


# ---------------------------------------------------------------------------
# get() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_happy_path() -> None:
    """get() returns value dict when row exists and is not expired."""
    row = {"id": "abc-123", "value": {"answer": 42}, "hit_count": 0, "expires_at": None}
    mock_conn, mock_cur = _make_mock_conn(fetchone_result=row)

    with patch(
        "aeogen.agents.core.memory.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        backend = SupabaseMemoryBackend(_DSN)
        result = await backend.get("agt", "global", "k1")

    assert result == {"answer": 42}
    mock_conn.commit.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_returns_none_when_missing() -> None:
    """get() returns None when no matching row is found."""
    mock_conn, _ = _make_mock_conn(fetchone_result=None)

    with patch(
        "aeogen.agents.core.memory.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        backend = SupabaseMemoryBackend(_DSN)
        result = await backend.get("agt", "global", "missing-key")

    assert result is None
    mock_conn.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_increments_hit_count_and_promotes() -> None:
    """get() executes two SQL statements: SELECT + hit_count UPDATE."""
    row = {"id": "abc-123", "value": {"x": 1}, "hit_count": 2, "expires_at": None}
    mock_conn, mock_cur = _make_mock_conn(fetchone_result=row)

    with patch(
        "aeogen.agents.core.memory.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        backend = SupabaseMemoryBackend(_DSN)
        await backend.get("agt", "global", "k1")

    # Two execute calls: SELECT then UPDATE
    assert mock_cur.execute.await_count == 2
    # Second call args contain new hit_count=3 and promoted=True
    update_args = mock_cur.execute.call_args_list[1]
    params = update_args[0][1]  # positional args tuple
    assert params[0] == 3  # new_hit_count
    assert params[1] is True  # promoted


@pytest.mark.asyncio
async def test_get_workspace_scope() -> None:
    """get() passes workspace_id in the query for workspace-scoped entries."""
    row = {"id": "abc-123", "value": {"data": "ok"}, "hit_count": 0, "expires_at": None}
    mock_conn, mock_cur = _make_mock_conn(fetchone_result=row)

    with patch(
        "aeogen.agents.core.memory.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        backend = SupabaseMemoryBackend(_DSN)
        result = await backend.get("agt", "workspace", "k1", workspace_id="ws-uuid")

    assert result == {"data": "ok"}
    # Verify workspace_id was passed in SELECT params
    select_params = mock_cur.execute.call_args_list[0][0][1]
    assert "ws-uuid" in select_params


# ---------------------------------------------------------------------------
# set() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_set_happy_path_no_ttl() -> None:
    """set() executes an UPSERT and commits."""
    mock_conn, mock_cur = _make_mock_conn()

    with patch(
        "aeogen.agents.core.memory.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        backend = SupabaseMemoryBackend(_DSN)
        await backend.set("agt", "global", "k1", {"result": "stored"})

    mock_cur.execute.assert_awaited_once()
    mock_conn.commit.assert_awaited_once()
    # SQL should contain INSERT ... ON CONFLICT
    sql = mock_cur.execute.call_args[0][0]
    assert "INSERT" in sql
    assert "ON CONFLICT" in sql


@pytest.mark.asyncio
async def test_set_with_ttl_passes_seconds() -> None:
    """set() with ttl_seconds includes make_interval in SQL."""
    mock_conn, mock_cur = _make_mock_conn()

    with patch(
        "aeogen.agents.core.memory.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        backend = SupabaseMemoryBackend(_DSN)
        await backend.set("agt", "global", "k1", {"x": 1}, ttl_seconds=3600)

    sql = mock_cur.execute.call_args[0][0]
    assert "make_interval" in sql
    # ttl_seconds must appear in params
    params = mock_cur.execute.call_args[0][1]
    assert 3600 in params


# ---------------------------------------------------------------------------
# search() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_memory_hits() -> None:
    """search() returns MemoryHit list with score=1.0."""
    rows = [
        {"key": "topic:python", "value": {"summary": "Python tips"}},
        {"key": "topic:langchain", "value": {"summary": "LangChain docs"}},
    ]
    mock_conn, mock_cur = _make_mock_conn(fetchall_result=rows)

    with patch(
        "aeogen.agents.core.memory.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        backend = SupabaseMemoryBackend(_DSN)
        results = await backend.search("agt", "global", "python")

    assert len(results) == 2
    assert all(isinstance(r, MemoryHit) for r in results)
    assert results[0].key == "topic:python"
    assert results[0].score == 1.0
    assert results[1].value == {"summary": "LangChain docs"}


@pytest.mark.asyncio
async def test_search_empty_results() -> None:
    """search() returns empty list when no rows match."""
    mock_conn, _ = _make_mock_conn(fetchall_result=[])

    with patch(
        "aeogen.agents.core.memory.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        backend = SupabaseMemoryBackend(_DSN)
        results = await backend.search("agt", "global", "no-match-xyz")

    assert results == []


@pytest.mark.asyncio
async def test_search_respects_k_limit() -> None:
    """search() passes k as LIMIT parameter to SQL."""
    mock_conn, mock_cur = _make_mock_conn(fetchall_result=[])

    with patch(
        "aeogen.agents.core.memory.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        backend = SupabaseMemoryBackend(_DSN)
        await backend.search("agt", "global", "query", k=10)

    params = mock_cur.execute.call_args[0][1]
    assert 10 in params
