"""C.3 OpenRouterLLM tests (mocked — no real API calls)."""

import os
from collections.abc import AsyncIterator
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

os.environ.setdefault("OPENROUTER_API_KEY", "test-openrouter-key-" + "x" * 20)

from aeogen.agents.core.llm import OpenRouterLLM
from aeogen.agents.core.types import LLMChunk, LLMResponse, Message


def _msgs(*contents: str) -> list[Message]:
    return [Message(role="user", content=c) for c in contents]


def _fake_ai_message(
    content: str = "hello",
    model: str = "anthropic/claude-sonnet-4.5",
    input_tokens: int = 10,
    output_tokens: int = 20,
) -> MagicMock:
    msg = MagicMock()
    msg.content = content
    msg.usage_metadata = {"input_tokens": input_tokens, "output_tokens": output_tokens}
    msg.response_metadata = {"model_name": model, "finish_reason": "stop"}
    return msg


def _fake_chunk(delta: str, finish_reason: str | None = None) -> MagicMock:
    chunk = MagicMock()
    chunk.content = delta
    chunk.response_metadata = {"finish_reason": finish_reason}
    return chunk


@pytest.mark.asyncio
async def test_chat_happy_path() -> None:
    """chat() returns LLMResponse with correct content and token counts."""
    fake = _fake_ai_message("hello world", input_tokens=5, output_tokens=10)
    with patch("aeogen.agents.core.llm.ChatOpenAI") as MockChatOpenAI:
        mock_client = AsyncMock()
        mock_client.ainvoke = AsyncMock(return_value=fake)
        MockChatOpenAI.return_value = mock_client

        llm = OpenRouterLLM()
        result = await llm.chat(_msgs("say hello"))

    assert isinstance(result, LLMResponse)
    assert result.content == "hello world"
    assert result.input_tokens == 5
    assert result.output_tokens == 10
    assert result.model == "anthropic/claude-sonnet-4.5"
    assert result.cost_usd is None


@pytest.mark.asyncio
async def test_chat_model_override() -> None:
    """Per-call model kwarg overrides the instance default."""
    fake = _fake_ai_message(model="openai/gpt-4o-mini")
    with patch("aeogen.agents.core.llm.ChatOpenAI") as MockChatOpenAI:
        mock_client = AsyncMock()
        mock_client.ainvoke = AsyncMock(return_value=fake)
        MockChatOpenAI.return_value = mock_client

        llm = OpenRouterLLM()
        await llm.chat(_msgs("hi"), model="openai/gpt-4o-mini")

    call_kwargs = MockChatOpenAI.call_args.kwargs
    assert call_kwargs["model"] == "openai/gpt-4o-mini"
    # Verify OpenRouter base_url is always set — prevents silent fallback to OpenAI
    assert call_kwargs["base_url"] == "https://openrouter.ai/api/v1"


@pytest.mark.asyncio
async def test_chat_with_fallback_chain() -> None:
    """When fallback_models set, extra_body contains route=fallback + models list."""
    fake = _fake_ai_message()
    with patch("aeogen.agents.core.llm.ChatOpenAI") as MockChatOpenAI:
        mock_client = AsyncMock()
        mock_client.ainvoke = AsyncMock(return_value=fake)
        MockChatOpenAI.return_value = mock_client

        llm = OpenRouterLLM(
            model="anthropic/claude-sonnet-4.5",
            fallback_models=["openai/gpt-4o", "google/gemini-2.0-flash"],
        )
        await llm.chat(_msgs("hi"))

    call_kwargs = MockChatOpenAI.call_args.kwargs
    assert "model_kwargs" in call_kwargs
    extra_body = call_kwargs["model_kwargs"]["extra_body"]
    assert extra_body["route"] == "fallback"
    assert extra_body["models"][0] == "anthropic/claude-sonnet-4.5"
    assert "openai/gpt-4o" in extra_body["models"]


@pytest.mark.asyncio
async def test_chat_api_error_propagates() -> None:
    """OpenAI/OpenRouter API errors propagate as-is (not swallowed)."""
    from openai import APIError

    with patch("aeogen.agents.core.llm.ChatOpenAI") as MockChatOpenAI:
        mock_client = AsyncMock()
        mock_client.ainvoke = AsyncMock(
            side_effect=APIError("rate limited", MagicMock(), body=None)
        )
        MockChatOpenAI.return_value = mock_client

        llm = OpenRouterLLM()
        with pytest.raises(APIError):
            await llm.chat(_msgs("hi"))


@pytest.mark.asyncio
async def test_stream_yields_chunks() -> None:
    """stream() yields LLMChunk objects for each token."""
    chunks = [_fake_chunk("Hello"), _fake_chunk(" world"), _fake_chunk("", "stop")]

    async def _astream(*args: object, **kwargs: object) -> AsyncIterator[MagicMock]:
        for c in chunks:
            yield c

    with patch("aeogen.agents.core.llm.ChatOpenAI") as MockChatOpenAI:
        mock_client = MagicMock()
        mock_client.astream = _astream
        MockChatOpenAI.return_value = mock_client

        llm = OpenRouterLLM()
        result_chunks = []
        async for chunk in await llm.stream(_msgs("hi")):
            result_chunks.append(chunk)

    assert len(result_chunks) == 3
    assert all(isinstance(c, LLMChunk) for c in result_chunks)
    assert result_chunks[0].delta == "Hello"
    assert result_chunks[2].finish_reason == "stop"


@pytest.mark.asyncio
async def test_chat_max_tokens_forwarded() -> None:
    """max_tokens kwarg is forwarded to ChatOpenAI.ainvoke."""
    fake = _fake_ai_message()
    with patch("aeogen.agents.core.llm.ChatOpenAI") as MockChatOpenAI:
        mock_client = AsyncMock()
        mock_client.ainvoke = AsyncMock(return_value=fake)
        MockChatOpenAI.return_value = mock_client

        llm = OpenRouterLLM()
        await llm.chat(_msgs("hi"), max_tokens=512)

    _, ainvoke_kwargs = mock_client.ainvoke.call_args
    assert ainvoke_kwargs.get("max_tokens") == 512


@pytest.mark.asyncio
async def test_token_budget_warning_logged(caplog: pytest.LogCaptureFixture) -> None:
    """Logs a warning when estimated tokens exceed 32k budget."""
    import logging

    # ~35k chars ≈ ~8750 tokens input; with max_tokens=30000 that's 38750 > 32000
    long_content = "word " * 7000  # 35000 chars ≈ 8750 tokens
    fake = _fake_ai_message()
    with patch("aeogen.agents.core.llm.ChatOpenAI") as MockChatOpenAI:
        mock_client = AsyncMock()
        mock_client.ainvoke = AsyncMock(return_value=fake)
        MockChatOpenAI.return_value = mock_client

        llm = OpenRouterLLM()
        with caplog.at_level(logging.WARNING, logger="aeogen.agents.core.llm"):
            await llm.chat(_msgs(long_content), max_tokens=30000)

    assert any("Token budget" in r.message for r in caplog.records)
