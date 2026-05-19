"""LangGraph checkpoint helper.

Wraps :class:`AsyncPostgresSaver` so concrete agents do not repeat
``from_conn_string`` + ``setup()`` boilerplate and so all checkpoints land in
the dedicated ``langgraph`` schema (created by the C.2 migration) rather than
``public``.

v1 pattern: per-``Agent.run()`` context manager — no pool, no app-level reuse.
v1.5 may reconsider once Celery worker traffic is measured.

Schema selection (decision 2026-05-20):
    ``AsyncPostgresSaver.from_conn_string`` in langgraph-checkpoint-postgres
    0.6.x exposes signature ``(conn_string, *, pipeline, serde)`` — no
    ``schema`` / ``schema_name`` kwarg. We therefore inject Postgres'
    ``options=-csearch_path%3Dlanggraph`` into the DSN so that
    ``.setup()``'s ``CREATE TABLE`` statements (and all subsequent reads/
    writes) target the langgraph schema. Functionally equivalent to a
    native kwarg.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

_LANGGRAPH_SCHEMA = "langgraph"


def _with_search_path(db_url: str, schema: str) -> str:
    """Return ``db_url`` with ``options=-csearch_path=<schema>`` merged in.

    Preserves any pre-existing query parameters and merges with any caller-
    supplied ``options`` value so we do not clobber unrelated libpq options.
    """
    parts = urlsplit(db_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    existing_options = query.get("options", "").strip()
    new_option = f"-csearch_path={schema}"
    query["options"] = f"{existing_options} {new_option}".strip()
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


@asynccontextmanager
async def build_postgres_saver(db_url: str) -> AsyncIterator[AsyncPostgresSaver]:
    """Open an :class:`AsyncPostgresSaver` pointing at the ``langgraph`` schema.

    Calls ``.setup()`` on entry (idempotent — LangGraph applies its own
    internal migrations on first run; subsequent runs are no-ops). The yielded
    saver is ready to pass to ``graph.compile(checkpointer=...)``.

    Args:
        db_url: Direct Postgres connection string. Pass
            ``str(settings.database_url)``. Must be a session-mode connection
            (Transaction pooler breaks LangGraph's BEGIN/SAVEPOINT usage).

    Usage::

        async with build_postgres_saver(str(settings.database_url)) as saver:
            graph = builder.compile(checkpointer=saver)
            result = await graph.ainvoke(
                input,
                config={"configurable": {"thread_id": str(ctx.execution_id)}},
            )
    """
    dsn = _with_search_path(db_url, _LANGGRAPH_SCHEMA)
    async with AsyncPostgresSaver.from_conn_string(dsn) as saver:
        await saver.setup()
        yield saver
