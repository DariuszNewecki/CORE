# tests/conftest.py
"""
Global test configuration and fixtures for pytest.
"""
from __future__ import annotations

from unittest.mock import AsyncMock

import pytest


@pytest.fixture(autouse=True)
def mock_embedding_service(mocker):
    """
    Automatically mocks the EmbeddingService for all tests to prevent
    slow, real network calls.

    This fixture replaces the `get_embedding` method with an async mock that
    returns a valid-looking vector of the correct dimension (768) instantly.
    This makes tests fast, reliable, and independent of external services.
    """
    # FIX 1: The vector dimension must match the project's configuration (768).
    fake_vector = [0.0] * 768

    # FIX 2: The path to the EmbeddingService has changed after the refactoring.
    mocker.patch(
        "services.adapters.embedding_provider.EmbeddingService.get_embedding",
        new_callable=AsyncMock,
        return_value=fake_vector,
    )
