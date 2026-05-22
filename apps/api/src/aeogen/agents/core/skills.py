"""SupabaseSkillProvider — implements SkillProvider protocol (C.5).

Uses psycopg3 (async) with direct SQL against the B.3 agent_skills table.
The agent_skills table is a global registry (no workspace_id) — all skills
are visible to all authenticated users per the B.3 RLS policy.

get_skill() with no version returns the highest-version row (latest).
get_skill() with version specified returns exactly that version.
"""

from __future__ import annotations

import logging

import psycopg
import psycopg.rows

from aeogen.agents.core.types import Skill

logger = logging.getLogger(__name__)


class SupabaseSkillProvider:
    """SkillProvider backed by Supabase Postgres agent_skills table (B.3).

    Conforms to the SkillProvider Protocol in aeogen.agents.core.protocols —
    structural typing, no inheritance required. mypy --strict enforces this.

    Args:
        db_url: Direct Postgres DSN (Session pooler port 5432).
                Pass str(settings.database_url).
    """

    def __init__(self, db_url: str) -> None:
        self._db_url = db_url

    # ------------------------------------------------------------------
    # SkillProvider implementation
    # ------------------------------------------------------------------

    async def get_skill(
        self,
        agent_name: str,
        skill_key: str,
        *,
        version: int | None = None,
    ) -> Skill | None:
        """Fetch a single skill record.

        If version is None, returns the highest-version active row.
        Returns None if no matching skill exists.
        """
        conn = await psycopg.AsyncConnection.connect(
            self._db_url, row_factory=psycopg.rows.dict_row
        )
        async with conn, conn.cursor() as cur:
            if version is not None:
                await cur.execute(
                    """
                    SELECT agent_name, skill_key, content, version, source
                    FROM public.agent_skills
                    WHERE agent_name = %s
                      AND skill_key = %s
                      AND version = %s
                      AND deleted_at IS NULL
                    LIMIT 1
                    """,
                    (agent_name, skill_key, version),
                )
            else:
                await cur.execute(
                    """
                    SELECT agent_name, skill_key, content, version, source
                    FROM public.agent_skills
                    WHERE agent_name = %s
                      AND skill_key = %s
                      AND deleted_at IS NULL
                    ORDER BY version DESC
                    LIMIT 1
                    """,
                    (agent_name, skill_key),
                )
            row = await cur.fetchone()

        if row is None:
            return None
        return Skill(
            agent_name=str(row["agent_name"]),
            skill_key=str(row["skill_key"]),
            content=str(row["content"]),
            version=int(row["version"]),
            source=str(row["source"]),  # type: ignore[arg-type]
        )

    async def list_skills(self, agent_name: str) -> list[Skill]:
        """Return all active skills for the given agent, ordered by skill_key.

        Returns the latest version of each skill_key.
        """
        conn = await psycopg.AsyncConnection.connect(
            self._db_url, row_factory=psycopg.rows.dict_row
        )
        async with conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT DISTINCT ON (skill_key)
                  agent_name, skill_key, content, version, source
                FROM public.agent_skills
                WHERE agent_name = %s
                  AND deleted_at IS NULL
                ORDER BY skill_key, version DESC
                """,
                (agent_name,),
            )
            rows = await cur.fetchall()

        return [
            Skill(
                agent_name=str(row["agent_name"]),
                skill_key=str(row["skill_key"]),
                content=str(row["content"]),
                version=int(row["version"]),
                source=str(row["source"]),  # type: ignore[arg-type]
            )
            for row in rows
        ]
