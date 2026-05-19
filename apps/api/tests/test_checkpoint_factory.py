"""C.2 checkpoint factory — type/contract assertions, no real DB.

These tests do not open a Postgres connection; they only verify the helper's
public shape. Real-DB integration (entering the context, .setup() side effects,
checkpoint write/read) is deferred to C.7 via Testcontainers.
"""

import inspect
from contextlib import AbstractAsyncContextManager

from aeogen.agents.core.checkpoint import build_postgres_saver


def test_build_postgres_saver_is_async_context_manager() -> None:
    """The factory must return an async context manager (not a saver directly)."""
    cm = build_postgres_saver("postgresql://fake:fake@localhost/test")
    assert isinstance(cm, AbstractAsyncContextManager)


def test_build_postgres_saver_signature() -> None:
    """Factory takes a single ``db_url: str`` parameter.

    ``checkpoint.py`` uses ``from __future__ import annotations`` so annotations
    are kept as strings at runtime. Compare via ``get_type_hints`` to resolve.
    """
    from typing import get_type_hints

    sig = inspect.signature(build_postgres_saver)
    params = list(sig.parameters.values())
    assert len(params) == 1
    assert params[0].name == "db_url"

    hints = get_type_hints(build_postgres_saver)
    assert hints["db_url"] is str
