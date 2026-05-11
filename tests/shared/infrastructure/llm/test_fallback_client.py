"""Unit tests for FallbackAwareLLMClient — #293 + lazy-construction follow-up."""

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


def _mock_client() -> MagicMock:
    client = MagicMock()
    client.make_request_async = AsyncMock()
    client.make_request_with_system_async = AsyncMock()
    client.get_embedding = AsyncMock()
    return client


def _factory_for(client: MagicMock):
    async def _build():
        return client

    return _build


def _factory_raises(exc: BaseException):
    async def _build():
        raise exc

    return _build


async def test_falls_back_to_next_client_on_402() -> None:
    primary = _mock_client()
    primary.make_request_async.side_effect = _make_status_error(402)
    secondary = _mock_client()
    secondary.make_request_async.return_value = "ok"

    wrapper = FallbackAwareLLMClient(
        client_factories=[_factory_for(primary), _factory_for(secondary)],
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
        client_factories=[_factory_for(primary), _factory_for(secondary)],
        resource_names=["a", "b"],
    )

    assert await wrapper.make_request_async("prompt") == "ok"


async def test_raises_provider_quota_exhausted_when_only_resource_402() -> None:
    only = _mock_client()
    only.make_request_async.side_effect = _make_status_error(402)

    wrapper = FallbackAwareLLMClient(
        client_factories=[_factory_for(only)],
        resource_names=["lone_resource"],
    )

    with pytest.raises(ProviderQuotaExhausted) as exc_info:
        await wrapper.make_request_async("prompt")

    assert exc_info.value.tried_resources == [("lone_resource", "402")]
    assert "lone_resource" in str(exc_info.value)
    assert "402" in str(exc_info.value)


async def test_raises_when_all_clients_402_with_full_tried_list() -> None:
    a = _mock_client()
    a.make_request_async.side_effect = _make_status_error(402)
    b = _mock_client()
    b.make_request_async.side_effect = _make_status_error(429)

    wrapper = FallbackAwareLLMClient(
        client_factories=[_factory_for(a), _factory_for(b)],
        resource_names=["a", "b"],
    )

    with pytest.raises(ProviderQuotaExhausted) as exc_info:
        await wrapper.make_request_async("prompt")

    assert exc_info.value.tried_resources == [("a", "402"), ("b", "429")]


async def test_non_retryable_status_propagates_unchanged() -> None:
    only = _mock_client()
    only.make_request_async.side_effect = _make_status_error(500)

    wrapper = FallbackAwareLLMClient(
        client_factories=[_factory_for(only)],
        resource_names=["lone_resource"],
    )

    with pytest.raises(httpx.HTTPStatusError):
        await wrapper.make_request_async("prompt")


async def test_unavailable_client_skipped_on_subsequent_call() -> None:
    primary = _mock_client()
    primary.make_request_async.side_effect = _make_status_error(402)
    secondary = _mock_client()
    secondary.make_request_async.return_value = "ok"

    wrapper = FallbackAwareLLMClient(
        client_factories=[_factory_for(primary), _factory_for(secondary)],
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
        client_factories=[_factory_for(primary), _factory_for(secondary)],
        resource_names=["p", "s"],
    )

    assert await wrapper.make_request_with_system_async("prompt", "system") == "sys-ok"
    assert await wrapper.get_embedding("text") == [0.1, 0.2]


def test_rejects_empty_factory_list() -> None:
    with pytest.raises(ValueError, match="at least one client factory"):
        FallbackAwareLLMClient(client_factories=[], resource_names=[])


def test_rejects_length_mismatch() -> None:
    with pytest.raises(ValueError, match="same length"):
        FallbackAwareLLMClient(
            client_factories=[_factory_for(_mock_client())],
            resource_names=["a", "b"],
        )


# ----- Lazy-construction regression tests (#293 follow-up) ---------------


async def test_provisioning_error_does_not_poison_the_chain() -> None:
    """
    Regression: an earlier resource served the call without ever
    constructing the later, broken-config resource. Mirrors the
    Architect role chain
    ``[assigned_ok, deepseek_ok, anthropic_ok, ollama_broken_config]``.
    """
    healthy = _mock_client()
    healthy.make_request_async.return_value = "served"
    broken_factory_calls: list[int] = []

    def _broken_factory_tracking():
        async def _build():
            broken_factory_calls.append(1)
            raise ValueError("Missing config for resource 'ollama_qwen_general_7b'.")

        return _build

    wrapper = FallbackAwareLLMClient(
        client_factories=[_factory_for(healthy), _broken_factory_tracking()],
        resource_names=["assigned_ok", "ollama_qwen_general_7b"],
    )

    assert await wrapper.make_request_async("prompt") == "served"
    # The broken factory must never be invoked — the call was served by index 0.
    assert broken_factory_calls == []


async def test_provisioning_error_skipped_when_first_in_chain() -> None:
    healthy = _mock_client()
    healthy.make_request_async.return_value = "served"

    wrapper = FallbackAwareLLMClient(
        client_factories=[
            _factory_raises(ValueError("Missing config for resource 'broken'.")),
            _factory_for(healthy),
        ],
        resource_names=["broken", "healthy"],
    )

    assert await wrapper.make_request_async("prompt") == "served"
    healthy.make_request_async.assert_awaited_once_with("prompt")


async def test_all_provisioning_errors_yield_exhausted_with_tag() -> None:
    wrapper = FallbackAwareLLMClient(
        client_factories=[
            _factory_raises(ValueError("Missing config for resource 'a'.")),
            _factory_raises(ValueError("Missing env_prefix for resource 'b'.")),
        ],
        resource_names=["a", "b"],
    )

    with pytest.raises(ProviderQuotaExhausted) as exc_info:
        await wrapper.make_request_async("prompt")

    assert exc_info.value.tried_resources == [
        ("a", "provisioning_error"),
        ("b", "provisioning_error"),
    ]


async def test_mixed_402_and_provisioning_errors_all_recorded() -> None:
    a = _mock_client()
    a.make_request_async.side_effect = _make_status_error(402)

    wrapper = FallbackAwareLLMClient(
        client_factories=[
            _factory_for(a),
            _factory_raises(ValueError("Missing config for resource 'b'.")),
        ],
        resource_names=["a", "b"],
    )

    with pytest.raises(ProviderQuotaExhausted) as exc_info:
        await wrapper.make_request_async("prompt")

    assert exc_info.value.tried_resources == [
        ("a", "402"),
        ("b", "provisioning_error"),
    ]


async def test_client_built_once_and_cached_for_subsequent_calls() -> None:
    healthy = _mock_client()
    healthy.make_request_async.return_value = "ok"
    factory_calls: list[int] = []

    async def _factory():
        factory_calls.append(1)
        return healthy

    wrapper = FallbackAwareLLMClient(
        client_factories=[_factory],
        resource_names=["healthy"],
    )

    await wrapper.make_request_async("first")
    await wrapper.make_request_async("second")

    assert len(factory_calls) == 1
    assert healthy.make_request_async.await_count == 2


async def test_provisioning_error_remembered_across_calls() -> None:
    """Once a factory has been seen to fail, do not re-invoke it."""
    factory_calls: list[int] = []

    def _broken_factory():
        async def _build():
            factory_calls.append(1)
            raise ValueError("Missing config for resource 'broken'.")

        return _build

    healthy = _mock_client()
    healthy.make_request_async.return_value = "ok"

    wrapper = FallbackAwareLLMClient(
        client_factories=[_broken_factory(), _factory_for(healthy)],
        resource_names=["broken", "healthy"],
    )

    await wrapper.make_request_async("first")
    await wrapper.make_request_async("second")

    assert len(factory_calls) == 1
    assert healthy.make_request_async.await_count == 2
