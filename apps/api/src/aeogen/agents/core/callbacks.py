"""Agent telemetry callbacks (C.6).

CostTracker:  on_llm_end → estimate cost → UPDATE agent_executions.llm_cost
LangSmithTraceHandler: on_llm_start → capture run_id → UPDATE agent_executions.trace_id

Both use db_session as a psycopg3 AsyncConnection (consistent with C.4/C.5).
Errors are swallowed and logged so telemetry never breaks the LLM call chain.

Pricing table (input_per_1k_usd, output_per_1k_usd). OpenRouter models only —
add entries as new models are adopted. Unknown models fall back to _DEFAULT_PRICING.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult

logger = logging.getLogger(__name__)

# (input_cost_per_1k_tokens, output_cost_per_1k_tokens) in USD
_MODEL_PRICING: dict[str, tuple[float, float]] = {
    "anthropic/claude-sonnet-4.5": (0.003, 0.015),
    "anthropic/claude-haiku-4.5": (0.00025, 0.00125),
    "anthropic/claude-opus-4.7": (0.015, 0.075),
    "openai/gpt-4o": (0.005, 0.015),
    "openai/gpt-4o-mini": (0.00015, 0.0006),
    "google/gemini-2.0-flash": (0.000075, 0.0003),
    "google/gemini-2.5-pro": (0.00125, 0.005),
}
_DEFAULT_PRICING: tuple[float, float] = (0.003, 0.015)  # Claude-class fallback


def _estimate_cost(model: str, prompt_tokens: int, completion_tokens: int) -> float:
    """Estimate USD cost from token counts using the pricing table."""
    in_rate, out_rate = _MODEL_PRICING.get(model, _DEFAULT_PRICING)
    return (prompt_tokens * in_rate + completion_tokens * out_rate) / 1000.0


class CostTracker(AsyncCallbackHandler):
    """Per-execution LLM cost tracker.

    Reads token usage from LLMResult.llm_output, estimates cost via the
    module-level pricing table, logs it, and increments
    agent_executions.llm_cost via db_session (expected: psycopg3 AsyncConnection).

    Errors are caught and logged — telemetry never raises into the LLM chain.
    """

    def __init__(self, execution_id: UUID, db_session: Any) -> None:  # noqa: ANN401
        self.execution_id = execution_id
        self.db_session = db_session

    async def on_llm_end(self, response: LLMResult, **kwargs: object) -> None:
        llm_output = response.llm_output or {}
        usage = llm_output.get("token_usage") or {}
        prompt_tokens = int(usage.get("prompt_tokens", 0))
        completion_tokens = int(usage.get("completion_tokens", 0))
        model = str(llm_output.get("model_name", "unknown"))

        cost = _estimate_cost(model, prompt_tokens, completion_tokens)
        logger.info(
            "LLM call complete: model=%s in=%d out=%d cost_usd=%.6f exec=%s",
            model,
            prompt_tokens,
            completion_tokens,
            cost,
            self.execution_id,
        )

        try:
            await self.db_session.execute(
                """
                UPDATE public.agent_executions
                SET llm_cost = llm_cost + %s
                WHERE id = %s AND deleted_at IS NULL
                """,
                (cost, str(self.execution_id)),
            )
            await self.db_session.commit()
        except Exception:
            logger.exception(
                "Failed to write llm_cost to agent_executions id=%s", self.execution_id
            )


class LangSmithTraceHandler(AsyncCallbackHandler):
    """Captures LangSmith trace_id into agent_executions.trace_id.

    LangChain passes a run_id (UUID) in on_llm_start kwargs; when LangSmith
    tracing is enabled (LANGCHAIN_TRACING_V2=true), this becomes the trace ID.
    Writes to agent_executions.trace_id via db_session (psycopg3 AsyncConnection).

    Errors are caught and logged — telemetry never raises into the LLM chain.
    """

    def __init__(self, execution_id: UUID, db_session: Any) -> None:  # noqa: ANN401
        self.execution_id = execution_id
        self.db_session = db_session

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: object,
    ) -> None:
        run_id = kwargs.get("run_id")
        if run_id is None:
            return

        trace_id = str(run_id)
        try:
            await self.db_session.execute(
                """
                UPDATE public.agent_executions
                SET trace_id = %s
                WHERE id = %s AND deleted_at IS NULL
                """,
                (trace_id, str(self.execution_id)),
            )
            await self.db_session.commit()
        except Exception:
            logger.exception(
                "Failed to write trace_id to agent_executions id=%s", self.execution_id
            )
