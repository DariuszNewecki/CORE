# tests/unit/test_llm_client.py
"""
Tests for the LLMClient facade over AI providers.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from services.llm.client import LLMClient


@pytest.fixture
def mock_provider():
    """Create a mock AI provider."""
    provider = MagicMock()
    provider.model_name = "test-model"
    provider.chat_completion = AsyncMock(return_value="Test response")
    provider.get_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
    return provider


@pytest.fixture
def mock_resource_config():
    """Create a mock resource configuration."""
    config = AsyncMock()
    config.get_max_concurrent = AsyncMock(return_value=5)
    config.get_rate_limit = AsyncMock(return_value=0)  # No rate limiting by default
    return config


@pytest.fixture
def llm_client(mock_provider, mock_resource_config):
    """Create an LLMClient with mocked dependencies."""
    client = LLMClient(mock_provider, mock_resource_config)
    # Initialize semaphore (normally done in create())
    client._semaphore = asyncio.Semaphore(5)
    return client


@pytest.mark.asyncio
async def test_client_initialization(mock_provider, mock_resource_config):
    """Tests that LLMClient initializes with correct attributes."""
    client = LLMClient(mock_provider, mock_resource_config)

    assert client.provider is mock_provider
    assert client.resource_config is mock_resource_config
    assert client.model_name == "test-model"
    assert client._last_request_time == 0


@pytest.mark.asyncio
async def test_make_request_async_success(llm_client, mock_provider):
    """Tests successful chat completion request."""
    response = await llm_client.make_request_async("Test prompt")

    assert response == "Test response"
    mock_provider.chat_completion.assert_called_once_with("Test prompt", "core_system")


@pytest.mark.asyncio
async def test_make_request_async_with_custom_user_id(llm_client, mock_provider):
    """Tests chat completion with custom user_id."""
    response = await llm_client.make_request_async("Test prompt", user_id="test_user")

    assert response == "Test response"
    mock_provider.chat_completion.assert_called_once_with("Test prompt", "test_user")


@pytest.mark.asyncio
async def test_get_embedding_success(llm_client, mock_provider):
    """Tests successful embedding generation."""
    embedding = await llm_client.get_embedding("Test text")

    assert embedding == [0.1, 0.2, 0.3]
    mock_provider.get_embedding.assert_called_once_with("Test text")


@pytest.mark.asyncio
async def test_request_with_retry_success_first_attempt(llm_client):
    """Tests that successful requests don't retry."""
    mock_method = AsyncMock(return_value="success")

    result = await llm_client._request_with_retry(mock_method, "arg1", key="value")

    assert result == "success"
    mock_method.assert_called_once_with("arg1", key="value")


@pytest.mark.asyncio
async def test_request_with_retry_succeeds_after_failure(llm_client):
    """Tests that failed requests are retried and eventually succeed."""
    mock_method = AsyncMock(
        side_effect=[Exception("First failure"), Exception("Second failure"), "success"]
    )

    result = await llm_client._request_with_retry(mock_method)

    assert result == "success"
    assert mock_method.call_count == 3


@pytest.mark.asyncio
async def test_request_with_retry_fails_after_max_attempts(llm_client):
    """Tests that requests fail after max retry attempts."""
    mock_method = AsyncMock(side_effect=Exception("Persistent failure"))

    with pytest.raises(Exception, match="Persistent failure"):
        await llm_client._request_with_retry(mock_method)

    # Should try 4 times total (1 initial + 3 retries)
    assert mock_method.call_count == 4


@pytest.mark.asyncio
async def test_rate_limiting_enforced(llm_client, mock_resource_config):
    """Tests that rate limiting delays are enforced."""
    # Set rate limit to 1 second
    mock_resource_config.get_rate_limit = AsyncMock(return_value=1.0)

    # First request should succeed immediately
    start = asyncio.get_event_loop().time()
    await llm_client._enforce_rate_limit()
    first_duration = asyncio.get_event_loop().time() - start

    # Second request should be delayed
    start = asyncio.get_event_loop().time()
    await llm_client._enforce_rate_limit()
    second_duration = asyncio.get_event_loop().time() - start

    # First request should be fast, second should take ~1 second
    assert first_duration < 0.1
    assert second_duration >= 0.9  # Allow some margin


@pytest.mark.asyncio
async def test_rate_limiting_not_enforced_when_disabled(
    llm_client, mock_resource_config
):
    """Tests that rate limiting is skipped when set to 0."""
    mock_resource_config.get_rate_limit = AsyncMock(return_value=0)

    start = asyncio.get_event_loop().time()
    await llm_client._enforce_rate_limit()
    await llm_client._enforce_rate_limit()
    duration = asyncio.get_event_loop().time() - start

    # Both requests should be fast
    assert duration < 0.1


@pytest.mark.asyncio
async def test_semaphore_limits_concurrent_requests(llm_client, mock_provider):
    """Tests that semaphore limits concurrent requests."""
    # Create a client with max 2 concurrent requests
    llm_client._semaphore = asyncio.Semaphore(2)

    # Track concurrent request count
    concurrent_count = 0
    max_concurrent = 0

    async def slow_request(*args, **kwargs):
        nonlocal concurrent_count, max_concurrent
        concurrent_count += 1
        max_concurrent = max(max_concurrent, concurrent_count)
        await asyncio.sleep(0.1)
        concurrent_count -= 1
        return "response"

    mock_provider.chat_completion = slow_request

    # Try to make 5 concurrent requests
    await asyncio.gather(*[llm_client.make_request_async("test") for _ in range(5)])

    # Max concurrent should never exceed semaphore limit
    assert max_concurrent <= 2


@pytest.mark.asyncio
async def test_client_without_semaphore_raises_error(
    mock_provider, mock_resource_config
):
    """Tests that client raises error if used without proper initialization."""
    client = LLMClient(mock_provider, mock_resource_config)
    # Don't set _semaphore

    with pytest.raises(RuntimeError, match="not properly initialized"):
        await client.make_request_async("test")


@pytest.mark.asyncio
async def test_create_factory_method(mocker):
    """Tests the create() factory method."""
    # Mock database session
    mock_db = AsyncMock()

    # Mock ConfigService
    mock_config = AsyncMock()
    mock_config_class = mocker.patch("services.llm.client.ConfigService")
    mock_config_class.create = AsyncMock(return_value=mock_config)

    # Mock LLMResourceConfig
    mock_resource_config = AsyncMock()
    mock_resource_config.get_max_concurrent = AsyncMock(return_value=10)

    mock_resource_config_class = mocker.patch("services.llm.client.LLMResourceConfig")
    mock_resource_config_class.for_resource = AsyncMock(
        return_value=mock_resource_config
    )

    # Mock provider
    mock_provider = MagicMock()
    mock_provider.model_name = "test-model"

    # Create client
    client = await LLMClient.create(mock_db, mock_provider, "test_resource")

    # Verify initialization
    assert client.provider is mock_provider
    assert client._semaphore is not None
    assert client._semaphore._value == 10


@pytest.mark.asyncio
async def test_exponential_backoff_timing(llm_client, mocker):
    """Tests that retry delays use exponential backoff."""
    mock_method = AsyncMock(
        side_effect=[
            Exception("Fail 1"),
            Exception("Fail 2"),
            Exception("Fail 3"),
            "success",
        ]
    )

    # Mock asyncio.sleep to track delays
    sleep_times = []
    original_sleep = asyncio.sleep

    async def mock_sleep(duration):
        sleep_times.append(duration)
        await original_sleep(0.001)  # Sleep very briefly for test speed

    mocker.patch("asyncio.sleep", side_effect=mock_sleep)

    await llm_client._request_with_retry(mock_method)

    # Verify exponential backoff: ~1s, ~2s, ~4s (with jitter)
    assert len(sleep_times) == 3
    assert 0.9 <= sleep_times[0] <= 1.5
    assert 1.9 <= sleep_times[1] <= 2.5
    assert 3.9 <= sleep_times[2] <= 4.5
