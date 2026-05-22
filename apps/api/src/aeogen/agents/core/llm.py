"""OpenRouter LLM adapter — implements LLMProvider protocol (C.3).

Uses langchain-openai ChatOpenAI pointed at OpenRouter's OpenAI-compatible
endpoint. Supports per-call model override, fallback chain routing, token
budget warnings, and streaming.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any, cast

from langchain_core.messages import AIMessage
from langchain_openai import ChatOpenAI

from aeogen.agents.core.types import LLMChunk, LLMResponse, Message
from aeogen.settings import get_settings

logger = logging.getLogger(__name__)

_TOKEN_BUDGET_WARN_THRESHOLD = 32_000
_CHARS_PER_TOKEN_ESTIMATE = 4


class OpenRouterLLM:
    """LLMProvider backed by OpenRouter's OpenAI-compatible API.

    Conforms to the LLMProvider Protocol defined in
    aeogen.agents.core.protocols — mypy --strict enforces this at check time.

    Args:
        model: Default model ID (OpenRouter format: "anthropic/claude-sonnet-4.5").
               Falls back to settings.openrouter_default_model if None.
        fallback_models: Ordered fallback list. When set, OpenRouter will try
               each model in sequence on rate-limit or unavailability.
               Passed via extra_body={"route": "fallback", "models": [...]}.
        temperature: Default temperature; overridable per call.
    """

    def __init__(
        self,
        *,
        model: str | None = None,
        fallback_models: list[str] | None = None,
        temperature: float = 0.2,
    ) -> None:
        settings = get_settings()
        self._default_model: str = model or settings.openrouter_default_model
        self._fallback_models: list[str] = fallback_models or []
        self._default_temperature: float = temperature
        self._api_key: str = settings.openrouter_api_key.get_secret_value()
        self._base_url: str = str(settings.openrouter_base_url)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _make_lc_client(
        self,
        model: str,
        temperature: float,
        extra_body: dict[str, Any] | None = None,
    ) -> ChatOpenAI:
        kwargs: dict[str, Any] = {
            "model": model,
            "openai_api_key": self._api_key,
            "base_url": self._base_url,
            "temperature": temperature,
        }
        if extra_body:
            kwargs["model_kwargs"] = {"extra_body": extra_body}
        return ChatOpenAI(**kwargs)

    def _build_extra_body(self, primary_model: str) -> dict[str, Any] | None:
        if not self._fallback_models:
            return None
        return {"route": "fallback", "models": [primary_model, *self._fallback_models]}

    def _warn_if_over_budget(self, messages: list[Message], max_tokens: int | None) -> None:
        total_chars = sum(len(m.content) for m in messages)
        estimated_input_tokens = total_chars // _CHARS_PER_TOKEN_ESTIMATE
        max_out = max_tokens if max_tokens is not None else 4096
        total_estimated = estimated_input_tokens + max_out
        if total_estimated > _TOKEN_BUDGET_WARN_THRESHOLD:
            logger.warning(
                "Token budget warning: ~%d input + %d max_output = %d > %d limit",
                estimated_input_tokens,
                max_out,
                total_estimated,
                _TOKEN_BUDGET_WARN_THRESHOLD,
            )
            # TODO(C.4+): auto-summarize conversation history when over budget.
            # Master plan §C.3 specifies auto-summarize; deferred to after
            # MemoryBackend (C.4) is available so history can be retrieved.

    @staticmethod
    def _flatten_content(content: str | list[Any]) -> str:
        if isinstance(content, str):
            return content
        return "".join(
            part["text"] if isinstance(part, dict) and "text" in part else str(part)
            for part in content
        )

    @staticmethod
    def _lc_messages(messages: list[Message]) -> list[tuple[str, str]]:
        return [(m.role, m.content) for m in messages]

    # ------------------------------------------------------------------
    # LLMProvider implementation
    # ------------------------------------------------------------------

    async def chat(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_tokens: int | None = None,
    ) -> LLMResponse:
        self._warn_if_over_budget(messages, max_tokens)
        effective_model = model or self._default_model
        extra_body = self._build_extra_body(effective_model)
        client = self._make_lc_client(effective_model, temperature, extra_body)

        invoke_kwargs: dict[str, Any] = {}
        if max_tokens is not None:
            invoke_kwargs["max_tokens"] = max_tokens

        ai_msg = cast(AIMessage, await client.ainvoke(self._lc_messages(messages), **invoke_kwargs))

        meta = ai_msg.usage_metadata
        return LLMResponse(
            content=self._flatten_content(ai_msg.content),
            model=ai_msg.response_metadata.get("model_name", effective_model),
            input_tokens=int(meta["input_tokens"]) if meta else 0,
            output_tokens=int(meta["output_tokens"]) if meta else 0,
            cost_usd=None,  # filled by C.6 LangSmith telemetry
        )

    async def stream(
        self,
        messages: list[Message],
        *,
        model: str | None = None,
        temperature: float = 0.2,
    ) -> AsyncIterator[LLMChunk]:
        effective_model = model or self._default_model
        extra_body = self._build_extra_body(effective_model)
        client = self._make_lc_client(effective_model, temperature, extra_body)

        async def _gen() -> AsyncIterator[LLMChunk]:
            async for chunk in client.astream(self._lc_messages(messages)):
                yield LLMChunk(
                    delta=self._flatten_content(chunk.content),
                    finish_reason=chunk.response_metadata.get("finish_reason"),
                )

        return _gen()
