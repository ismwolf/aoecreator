"""C.6 telemetry callback tests (mocked — no real DB or LangSmith)."""

import os
from unittest.mock import AsyncMock, MagicMock
from uuid import UUID

import pytest

os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost:5432/testdb")

from aeogen.agents.core.callbacks import CostTracker, LangSmithTraceHandler

_EXEC_ID = UUID("12345678-1234-5678-1234-567812345678")


def _fake_llm_result(
    model: str = "anthropic/claude-sonnet-4.5",
    prompt_tokens: int = 100,
    completion_tokens: int = 200,
) -> object:
    """Build a minimal LLMResult-like mock."""
    result = MagicMock()
    result.llm_output = {
        "token_usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
        "model_name": model,
    }
    return result


# ---------------------------------------------------------------------------
# CostTracker tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cost_tracker_writes_cost_to_db() -> None:
    """on_llm_end() updates agent_executions.llm_cost and commits."""
    mock_db = AsyncMock()
    tracker = CostTracker(execution_id=_EXEC_ID, db_session=mock_db)
    result = _fake_llm_result(prompt_tokens=1000, completion_tokens=500)

    await tracker.on_llm_end(result)  # type: ignore[arg-type]

    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()
    # SQL must update llm_cost
    sql = mock_db.execute.call_args[0][0]
    assert "llm_cost" in sql
    assert "agent_executions" in sql


@pytest.mark.asyncio
async def test_cost_tracker_logs_token_info(caplog: pytest.LogCaptureFixture) -> None:
    """on_llm_end() logs model, token counts, and estimated cost."""
    import logging

    mock_db = AsyncMock()
    tracker = CostTracker(execution_id=_EXEC_ID, db_session=mock_db)
    result = _fake_llm_result(
        model="anthropic/claude-sonnet-4.5",
        prompt_tokens=1000,
        completion_tokens=500,
    )

    with caplog.at_level(logging.INFO, logger="aeogen.agents.core.callbacks"):
        await tracker.on_llm_end(result)  # type: ignore[arg-type]

    assert any("1000" in r.message or "token" in r.message.lower() for r in caplog.records)


@pytest.mark.asyncio
async def test_cost_tracker_db_error_does_not_raise() -> None:
    """on_llm_end() swallows DB errors to avoid breaking the LLM call chain."""
    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("db error"))
    tracker = CostTracker(execution_id=_EXEC_ID, db_session=mock_db)
    result = _fake_llm_result()

    # Must NOT raise
    await tracker.on_llm_end(result)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_cost_tracker_known_model_pricing() -> None:
    """on_llm_end() uses known model pricing when available."""
    mock_db = AsyncMock()
    tracker = CostTracker(execution_id=_EXEC_ID, db_session=mock_db)
    # gpt-4o-mini: $0.00015/1k input + $0.0006/1k output
    # 10k input + 5k output = $0.0015 + $0.003 = $0.0045
    result = _fake_llm_result(
        model="openai/gpt-4o-mini",
        prompt_tokens=10_000,
        completion_tokens=5_000,
    )
    await tracker.on_llm_end(result)  # type: ignore[arg-type]

    params = mock_db.execute.call_args[0][1]
    estimated = float(params[0])
    assert abs(estimated - 0.0045) < 0.0001


# ---------------------------------------------------------------------------
# LangSmithTraceHandler tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_trace_handler_writes_trace_id_to_db() -> None:
    """on_llm_start() writes run_id as trace_id to agent_executions."""
    from uuid import uuid4

    mock_db = AsyncMock()
    handler = LangSmithTraceHandler(execution_id=_EXEC_ID, db_session=mock_db)
    run_id = uuid4()

    await handler.on_llm_start({}, ["prompt text"], run_id=run_id)

    mock_db.execute.assert_awaited_once()
    mock_db.commit.assert_awaited_once()
    sql = mock_db.execute.call_args[0][0]
    assert "trace_id" in sql
    assert "agent_executions" in sql
    # run_id value must appear in params
    params = mock_db.execute.call_args[0][1]
    assert str(run_id) in params


@pytest.mark.asyncio
async def test_trace_handler_no_run_id_is_noop() -> None:
    """on_llm_start() without run_id skips the DB write."""
    mock_db = AsyncMock()
    handler = LangSmithTraceHandler(execution_id=_EXEC_ID, db_session=mock_db)

    await handler.on_llm_start({}, ["prompt"], run_id=None)

    mock_db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_trace_handler_db_error_does_not_raise() -> None:
    """on_llm_start() swallows DB errors to avoid breaking the LLM call chain."""
    from uuid import uuid4

    mock_db = AsyncMock()
    mock_db.execute = AsyncMock(side_effect=Exception("db gone"))
    handler = LangSmithTraceHandler(execution_id=_EXEC_ID, db_session=mock_db)

    await handler.on_llm_start({}, ["prompt"], run_id=uuid4())
