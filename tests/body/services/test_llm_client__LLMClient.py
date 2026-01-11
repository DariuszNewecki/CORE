"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/services/llm_client.py
- Symbol: LLMClient
- Status: verified_in_sandbox
- Generated: 2026-01-11 03:11:33
"""

import pytest

from body.services.llm_client import LLMClient


# LLMClient.make_request is async def, so tests must be async too


@pytest.mark.asyncio
async def test_llmclient_init():
    """Test LLMClient initialization with all required parameters."""
    client = LLMClient(
        api_url="https://api.example.com/v1/chat/completions",
        api_key="test-key-123",
        model_name="test-model",
        http_timeout=30,
    )

    assert client.api_url == "https://api.example.com/v1/chat/completions"
    assert client.api_key == "test-key-123"
    assert client.model_name == "test-model"
    assert client.http_timeout == 30
    assert client.base_url == "https://api.example.com/v1/chat/completions"


@pytest.mark.asyncio
async def test_llmclient_init_default_timeout():
    """Test LLMClient initialization with default timeout."""
    client = LLMClient(
        api_url="https://api.example.com/v1/chat/completions",
        api_key="test-key-456",
        model_name="test-model-2",
    )

    assert client.api_url == "https://api.example.com/v1/chat/completions"
    assert client.api_key == "test-key-456"
    assert client.model_name == "test-model-2"
    assert client.http_timeout == 60  # Default value
    assert client.base_url == "https://api.example.com/v1/chat/completions"


@pytest.mark.asyncio
async def test_make_request_requires_async():
    """Test that make_request is an async method."""
    # This test verifies the method signature is async
    client = LLMClient(
        api_url="https://api.example.com/v1/chat/completions",
        api_key="test-key",
        model_name="test-model",
    )

    # Check that make_request is a coroutine function
    import inspect

    assert inspect.iscoroutinefunction(client.make_request)


# Note: Since we cannot mock httpx.AsyncClient per the "NO MOCKING" rule,
# and we cannot make actual HTTP requests in unit tests, we cannot test
# the actual execution of make_request() method. The method contains
# external HTTP calls which would require mocking to test properly,
# but mocking is explicitly prohibited by the rules.

# The following tests demonstrate what we would test if mocking were allowed,
# but are commented out since they would fail without mocking:

"""
@pytest.mark.asyncio
async def test_make_request_success():
    # This test would require mocking httpx.AsyncClient
    pass

@pytest.mark.asyncio
async def test_make_request_empty_response():
    # This test would require mocking to return empty content
    pass

@pytest.mark.asyncio
async def test_make_request_http_error():
    # This test would require mocking to raise HTTPStatusError
    pass
"""

# The LLMClient class is primarily a wrapper for HTTP calls,
# and without mocking, we can only test its initialization and
# method signatures in unit tests.
