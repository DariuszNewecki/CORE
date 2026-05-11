"""Unit tests for FallbackAwareLLMClient — issue #293 fallback chain on 402/429."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from shared.exceptions import ProviderQuotaExhausted
from shared.infrastructure.llm.fallback_client import FallbackAwareLLMClient


def _make_status_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://example.test/v1/chat/completions")
    response = httpx.Response(status_code=status, request=request)
    return httpx.HTTPStatusError("error", request=request, response=response)


def _mock_client(model_name: str = "stub-model") -> MagicMock:
    client = MagicMock()
    client.model_name = model_name
    client.provider = MagicMock()
    client.make_request_async = AsyncMock()
    client.make_request_with_system_async = AsyncMock()
    client.get_embedding = AsyncMock()
    return client


async def test_falls_back_to_next_client_on_402() -> None:
    primary = _mock_client()
    primary.make_request_async.side_effect = _make_status_error(402)
    secondary = _mock_client()
    secondary.make_request_async.return_value = "ok"

    wrapper = FallbackAwareLLMClient(
        clients=[primary, secondary],
        resource_names=["primary_resource", "secondary_resource"],
    )

    result = await wrapper.make_request_async("prompt")

    assert result == "ok"
    primary.make_request_async.assert_awaited_once_with("prompt")
    secondary.make_request_async.assert_awaited_once_with("prompt")


async def test_falls_back_to_next_client_on_429() -> None:
    primary = _mock_client()
    primary.make_request_async.side_effect = _make_status_error(429)
    secondary = _mock_client()
    secondary.make_request_async.return_value = "ok"

    wrapper = FallbackAwareLLMClient(
        clients=[primary, secondary],
        resource_names=["a", "b"],
    )

    assert await wrapper.make_request_async("prompt") == "ok"


async def test_raises_provider_quota_exhausted_when_only_resource_402() -> None:
    only = _mock_client()
    only.make_request_async.side_effect = _make_status_error(402)

    wrapper = FallbackAwareLLMClient(
        clients=[only], resource_names=["lone_resource"]
    )

    with pytest.raises(ProviderQuotaExhausted) as exc_info:
        await wrapper.make_request_async("prompt")

    assert exc_info.value.tried_resources == [("lone_resource", 402)]
    assert "lone_resource" in str(exc_info.value)
    assert "402" in str(exc_info.value)


async def test_raises_when_all_clients_402_with_full_tried_list() -> None:
    a = _mock_client()
    a.make_request_async.side_effect = _make_status_error(402)
    b = _mock_client()
    b.make_request_async.side_effect = _make_status_error(429)

    wrapper = FallbackAwareLLMClient(clients=[a, b], resource_names=["a", "b"])

    with pytest.raises(ProviderQuotaExhausted) as exc_info:
        await wrapper.make_request_async("prompt")

    assert exc_info.value.tried_resources == [("a", 402), ("b", 429)]


async def test_non_retryable_status_propagates_unchanged() -> None:
    only = _mock_client()
    only.make_request_async.side_effect = _make_status_error(500)

    wrapper = FallbackAwareLLMClient(
        clients=[only], resource_names=["lone_resource"]
    )

    with pytest.raises(httpx.HTTPStatusError):
        await wrapper.make_request_async("prompt")


async def test_unavailable_client_skipped_on_subsequent_call() -> None:
    primary = _mock_client()
    primary.make_request_async.side_effect = _make_status_error(402)
    secondary = _mock_client()
    secondary.make_request_async.return_value = "ok"

    wrapper = FallbackAwareLLMClient(
        clients=[primary, secondary],
        resource_names=["primary", "secondary"],
    )

    await wrapper.make_request_async("first")
    await wrapper.make_request_async("second")

    assert primary.make_request_async.await_count == 1
    assert secondary.make_request_async.await_count == 2


async def test_embedding_and_system_prompt_methods_also_fall_back() -> None:
    primary = _mock_client()
    primary.make_request_with_system_async.side_effect = _make_status_error(402)
    primary.get_embedding.side_effect = _make_status_error(402)
    secondary = _mock_client()
    secondary.make_request_with_system_async.return_value = "sys-ok"
    secondary.get_embedding.return_value = [0.1, 0.2]

    wrapper = FallbackAwareLLMClient(
        clients=[primary, secondary],
        resource_names=["p", "s"],
    )

    assert (
        await wrapper.make_request_with_system_async("prompt", "system") == "sys-ok"
    )
    assert await wrapper.get_embedding("text") == [0.1, 0.2]


def test_rejects_empty_client_list() -> None:
    with pytest.raises(ValueError, match="at least one client"):
        FallbackAwareLLMClient(clients=[], resource_names=[])


def test_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError, match="same length"):
        FallbackAwareLLMClient(
            clients=[_mock_client()], resource_names=["a", "b"]
        )
