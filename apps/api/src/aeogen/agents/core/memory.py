"""SupabaseMemoryBackend — implements MemoryBackend protocol (C.4).

Uses psycopg3 (async) with direct SQL against the B.3 agent_memory table.
psycopg3 is chosen over supabase-py PostgREST because the UPSERT requires
ON CONFLICT referencing the coalesce-based partial unique index
(agent_memory_unique_key_active_uq), which PostgREST cannot express.

Scope ↔ workspace_id invariant (enforced by B.3 DB CHECK):
  - 'workspace' scope requires workspace_id
  - 'global' / 'agent' scopes must have workspace_id = NULL

In the unique index coalesce(workspace_id::text, '') maps NULL → '' so that
global/agent entries also participate in the uniqueness constraint.
"""

from __future__ import annotations

import json
import logging

import psycopg
import psycopg.rows

from aeogen.agents.core.types import MemoryHit

logger = logging.getLogger(__name__)

_PROMOTE_THRESHOLD = 3  # hit_count reaches this → promoted = True


class SupabaseMemoryBackend:
    """MemoryBackend backed by Supabase Postgres agent_memory table (B.3).

    Conforms to the MemoryBackend Protocol in aeogen.agents.core.protocols —
    structural typing, no inheritance required. mypy --strict enforces this.

    Args:
        db_url: Direct Postgres DSN (Session pooler port 5432).
                Pass str(settings.database_url).
    """

    def __init__(self, db_url: str) -> None:
        self._db_url = db_url

    # ------------------------------------------------------------------
    # MemoryBackend implementation
    # ------------------------------------------------------------------

    async def get(
        self,
        agent_name: str,
        scope: str,
        key: str,
        *,
        workspace_id: str | None = None,
    ) -> dict[str, object] | None:
        """Fetch a memory entry.

        Filters out soft-deleted and TTL-expired rows. On a hit, increments
        hit_count and promotes (promoted=True) once count reaches
        _PROMOTE_THRESHOLD.

        Returns:
            The stored value dict, or None if not found / expired.
        """
        conn = await psycopg.AsyncConnection.connect(
            self._db_url, row_factory=psycopg.rows.dict_row
        )
        async with conn, conn.cursor() as cur:
            await cur.execute(
                """
                SELECT id, value, hit_count, expires_at
                FROM public.agent_memory
                WHERE agent_name = %s
                  AND scope = %s
                  AND key = %s
                  AND coalesce(workspace_id::text, '') = %s
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > now())
                """,
                (agent_name, scope, key, workspace_id or ""),
            )
            row = await cur.fetchone()
            if row is None:
                return None

            new_hit_count = row["hit_count"] + 1
            promoted = new_hit_count >= _PROMOTE_THRESHOLD
            await cur.execute(
                """
                UPDATE public.agent_memory
                SET hit_count = %s,
                    promoted = CASE WHEN %s THEN true ELSE promoted END
                WHERE id = %s
                """,
                (new_hit_count, promoted, row["id"]),
            )
            await conn.commit()

            raw = row["value"]
            return dict(raw) if raw is not None else {}

    async def set(
        self,
        agent_name: str,
        scope: str,
        key: str,
        value: dict[str, object],
        *,
        workspace_id: str | None = None,
        ttl_seconds: int | None = None,
    ) -> None:
        """Upsert a memory entry.

        Conflict target matches agent_memory_unique_key_active_uq partial index.
        hit_count is reset to 0 on every upsert (caller sets, not accumulates).
        """
        conn = await psycopg.AsyncConnection.connect(
            self._db_url, row_factory=psycopg.rows.dict_row
        )
        async with conn, conn.cursor() as cur:
            value_json = json.dumps(value)
            if ttl_seconds is not None:
                await cur.execute(
                    """
                    INSERT INTO public.agent_memory
                      (agent_name, scope, workspace_id, key, value, expires_at, hit_count)
                    VALUES (%s, %s, %s, %s, %s::jsonb,
                            now() + make_interval(secs => %s), 0)
                    ON CONFLICT (agent_name, scope, coalesce(workspace_id::text, ''), key)
                      WHERE deleted_at IS NULL
                    DO UPDATE SET
                      value      = EXCLUDED.value,
                      expires_at = EXCLUDED.expires_at,
                      hit_count  = 0,
                      cached_at  = now()
                    """,
                    (agent_name, scope, workspace_id, key, value_json, ttl_seconds),
                )
            else:
                await cur.execute(
                    """
                    INSERT INTO public.agent_memory
                      (agent_name, scope, workspace_id, key, value, expires_at, hit_count)
                    VALUES (%s, %s, %s, %s, %s::jsonb, NULL, 0)
                    ON CONFLICT (agent_name, scope, coalesce(workspace_id::text, ''), key)
                      WHERE deleted_at IS NULL
                    DO UPDATE SET
                      value      = EXCLUDED.value,
                      expires_at = NULL,
                      hit_count  = 0,
                      cached_at  = now()
                    """,
                    (agent_name, scope, workspace_id, key, value_json),
                )
            await conn.commit()

    async def search(
        self,
        agent_name: str,
        scope: str,
        query: str,
        k: int = 5,
        *,
        workspace_id: str | None = None,
    ) -> list[MemoryHit]:
        """Text search over agent memory keys and values.

        C.4 implements key/value ILIKE search with score=1.0 for all matches.
        Cosine vector search over agent_memory requires per-entry embeddings
        (deferred to D-cycle when BGE-M3 is available).

        Results are ordered by hit_count DESC (popularity signal).
        """
        conn = await psycopg.AsyncConnection.connect(
            self._db_url, row_factory=psycopg.rows.dict_row
        )
        async with conn, conn.cursor() as cur:
            pattern = f"%{query}%"
            await cur.execute(
                """
                SELECT key, value
                FROM public.agent_memory
                WHERE agent_name = %s
                  AND scope = %s
                  AND coalesce(workspace_id::text, '') = %s
                  AND deleted_at IS NULL
                  AND (expires_at IS NULL OR expires_at > now())
                  AND (
                    key ILIKE %s
                    OR value::text ILIKE %s
                  )
                ORDER BY hit_count DESC
                LIMIT %s
                """,
                (agent_name, scope, workspace_id or "", pattern, pattern, k),
            )
            rows = await cur.fetchall()

        return [
            MemoryHit(
                key=row["key"],
                value=dict(row["value"]) if row["value"] is not None else {},
                score=1.0,
            )
            for row in rows
        ]
