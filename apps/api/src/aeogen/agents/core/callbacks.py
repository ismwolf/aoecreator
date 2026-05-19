"""Agent telemetry callbacks.

C.6 fills in the bodies. C.1 only defines the class shape so Agent constructor
can accept `callbacks: list[AsyncCallbackHandler]`.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from langchain_core.callbacks import AsyncCallbackHandler
from langchain_core.outputs import LLMResult


class CostTracker(AsyncCallbackHandler):
    """Per-execution LLM cost tracker.

    Writes to agent_executions.llm_cost (B.2 column). C.6 implements.
    """

    def __init__(self, execution_id: UUID, db_session: Any) -> None:  # noqa: ANN401
        # db_session intentionally Any — opaque AsyncSession (spec decision 2026-05-19,
        # C.4 narrows to sqlalchemy.ext.asyncio.AsyncSession when imported).
        self.execution_id = execution_id
        self.db_session = db_session

    async def on_llm_end(self, response: LLMResult, **kwargs: object) -> None:
        raise NotImplementedError("Implemented in Faz 3 C.6 (telemetry)")


class LangSmithTraceHandler(AsyncCallbackHandler):
    """Captures LangSmith trace_id into agent_executions.trace_id (B.2 column).

    C.6 implements (likely via on_llm_start hook + run_id from kwargs).
    """

    def __init__(self, execution_id: UUID, db_session: Any) -> None:  # noqa: ANN401
        # db_session intentionally Any — see CostTracker note.
        self.execution_id = execution_id
        self.db_session = db_session

    async def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        **kwargs: object,
    ) -> None:
        raise NotImplementedError("Implemented in Faz 3 C.6 (telemetry)")
