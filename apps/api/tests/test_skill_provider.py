"""C.5 SupabaseSkillProvider tests (mocked — no real DB calls)."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")

from aeogen.agents.core.skills import SupabaseSkillProvider
from aeogen.agents.core.types import Skill

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

    return mock_conn, mock_cur


def _skill_row(
    agent_name: str = "my-agent",
    skill_key: str = "summarise",
    content: str = "You summarise text.",
    version: int = 1,
    source: str = "builtin",
) -> dict[str, object]:
    return {
        "agent_name": agent_name,
        "skill_key": skill_key,
        "content": content,
        "version": version,
        "source": source,
    }


# ---------------------------------------------------------------------------
# get_skill() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_skill_happy_path() -> None:
    """get_skill() returns Skill when row exists."""
    row = _skill_row()
    mock_conn, _ = _make_mock_conn(fetchone_result=row)

    with patch(
        "aeogen.agents.core.skills.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        provider = SupabaseSkillProvider(_DSN)
        skill = await provider.get_skill("my-agent", "summarise")

    assert isinstance(skill, Skill)
    assert skill.agent_name == "my-agent"
    assert skill.skill_key == "summarise"
    assert skill.content == "You summarise text."
    assert skill.version == 1
    assert skill.source == "builtin"


@pytest.mark.asyncio
async def test_get_skill_returns_none_when_missing() -> None:
    """get_skill() returns None when no matching row exists."""
    mock_conn, _ = _make_mock_conn(fetchone_result=None)

    with patch(
        "aeogen.agents.core.skills.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        provider = SupabaseSkillProvider(_DSN)
        result = await provider.get_skill("my-agent", "nonexistent")

    assert result is None


@pytest.mark.asyncio
async def test_get_skill_with_version_filter() -> None:
    """get_skill() passes version to SQL when specified."""
    row = _skill_row(version=3)
    mock_conn, mock_cur = _make_mock_conn(fetchone_result=row)

    with patch(
        "aeogen.agents.core.skills.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        provider = SupabaseSkillProvider(_DSN)
        skill = await provider.get_skill("my-agent", "summarise", version=3)

    assert skill is not None
    assert skill.version == 3
    # version must appear in query params
    params = mock_cur.execute.call_args[0][1]
    assert 3 in params


@pytest.mark.asyncio
async def test_get_skill_without_version_uses_latest() -> None:
    """get_skill() without version returns the highest-version row (ORDER BY version DESC)."""
    row = _skill_row(version=5)
    mock_conn, mock_cur = _make_mock_conn(fetchone_result=row)

    with patch(
        "aeogen.agents.core.skills.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        provider = SupabaseSkillProvider(_DSN)
        skill = await provider.get_skill("my-agent", "summarise")

    assert skill is not None
    assert skill.version == 5
    # SQL must order by version DESC to get latest
    sql = mock_cur.execute.call_args[0][0]
    assert "version DESC" in sql


# ---------------------------------------------------------------------------
# list_skills() tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_skills_returns_all_for_agent() -> None:
    """list_skills() returns all active skills for the given agent."""
    rows = [
        _skill_row(skill_key="summarise", version=1),
        _skill_row(skill_key="extract-entities", version=2, source="promoted"),
    ]
    mock_conn, _ = _make_mock_conn(fetchall_result=rows)

    with patch(
        "aeogen.agents.core.skills.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        provider = SupabaseSkillProvider(_DSN)
        skills = await provider.list_skills("my-agent")

    assert len(skills) == 2
    assert all(isinstance(s, Skill) for s in skills)
    assert skills[0].skill_key == "summarise"
    assert skills[1].source == "promoted"


@pytest.mark.asyncio
async def test_list_skills_empty() -> None:
    """list_skills() returns empty list when agent has no skills."""
    mock_conn, _ = _make_mock_conn(fetchall_result=[])

    with patch(
        "aeogen.agents.core.skills.psycopg.AsyncConnection.connect",
        new_callable=AsyncMock,
    ) as mock_connect:
        mock_connect.return_value = mock_conn

        provider = SupabaseSkillProvider(_DSN)
        skills = await provider.list_skills("unknown-agent")

    assert skills == []
