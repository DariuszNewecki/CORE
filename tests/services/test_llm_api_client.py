# tests/services/test_llm_api_client.py
from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from services.clients.llm_api_client import BaseLLMClient


def test_init_requires_api_url_and_model() -> None:
    """BaseLLMClient should validate required constructor arguments."""
    with pytest.raises(ValueError):
        BaseLLMClient(api_url="", model_name="gpt-4")

    with pytest.raises(ValueError):
        BaseLLMClient(api_url="https://api.openai.com", model_name="")

    # Valid init should set basic attributes
    client = BaseLLMClient(
        api_url="https://api.openai.com", model_name="gpt-4", api_key="secret"
    )
    assert client.base_url == "https://api.openai.com"
    assert client.model_name == "gpt-4"
    # Default path should map to OpenAI chat by URL
    assert client.api_type == "openai"


@pytest.mark.anyio
async def test_make_request_async_chat_and_embedding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Async client should handle chat and embedding responses correctly."""
    client = BaseLLMClient(
        api_url="https://api.openai.com", model_name="gpt-4", api_key="secret"
    )

    # Prepare a reusable mock response
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None

    # First call: chat completion style response
    mock_response.json.return_value = {
        "choices": [
            {
                "message": {"content": "Hello from LLM"},
            }
        ]
    }

    async_client_mock = MagicMock()
    async_client_mock.post = AsyncMock(return_value=mock_response)
    client.async_client = async_client_mock

    result = await client.make_request_async(prompt="Hi")
    assert result == "Hello from LLM"

    # Second call: embedding-style response
    mock_response.json.return_value = {
        "data": [
            {
                "embedding": [0.1, 0.2, 0.3],
            }
        ]
    }

    # get_embedding wraps make_request_async with task_type="embedding"
    embedding = await client.get_embedding("vectorize me")
    assert embedding == [0.1, 0.2, 0.3]

    # Ensure we actually hit the HTTP client twice
    assert async_client_mock.post.await_count == 2


@pytest.mark.anyio
async def test_make_request_async_retries_and_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    When requests fail initially, make_request_async should back off and retry
    before eventually succeeding.
    """
    client = BaseLLMClient(
        api_url="https://api.openai.com", model_name="gpt-4", api_key="secret"
    )

    # Avoid real sleeps and random jitter
    async def dummy_sleep(_: float) -> None:
        return None

    monkeypatch.setattr(
        "services.clients.llm_api_client.asyncio.sleep",
        dummy_sleep,
    )
    monkeypatch.setattr(
        "services.clients.llm_api_client.random.uniform",
        lambda _a, _b: 0.0,
    )

    # Prepare failing then succeeding responses
    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "choices": [{"message": {"content": "Recovered"}}]
    }

    errors_and_response: list[object] = [
        httpx.ConnectError("boom", request=None),
        httpx.ConnectError("boom again", request=None),
        mock_response,
    ]

    async def post_side_effect(*_args, **_kwargs):
        item = errors_and_response.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    async_client_mock = MagicMock()
    async_client_mock.post = AsyncMock(side_effect=post_side_effect)
    client.async_client = async_client_mock

    result = await client.make_request_async(prompt="Hi after failures")
    assert result == "Recovered"

    # We expect 3 attempts: 2 failures + 1 success
    assert async_client_mock.post.await_count == 3


def test_make_request_sync_chat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Sync request path should also use backoff logic on errors and succeed."""
    client = BaseLLMClient(
        api_url="https://api.openai.com", model_name="gpt-4", api_key="secret"
    )

    # Avoid real sleeping and jitter
    monkeypatch.setattr(
        "services.clients.llm_api_client.time.sleep",
        lambda _seconds: None,
    )
    monkeypatch.setattr(
        "services.clients.llm_api_client.random.uniform",
        lambda _a, _b: 0.0,
    )

    mock_response = MagicMock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"choices": [{"message": {"content": "Sync OK"}}]}

    errors_and_response: list[object] = [
        httpx.ConnectError("boom", request=None),
        mock_response,
    ]

    def post_side_effect(*_args, **_kwargs):
        item = errors_and_response.pop(0)
        if isinstance(item, Exception):
            raise item
        return item

    sync_client_mock = MagicMock()
    sync_client_mock.post = MagicMock(side_effect=post_side_effect)
    client.sync_client = sync_client_mock

    result = client.make_request_sync(prompt="Hello")
    assert result == "Sync OK"

    # We expect 2 attempts: 1 failure + 1 success
    assert sync_client_mock.post.call_count == 2
