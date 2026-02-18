# src/shared/protocols/knowledge.py

"""
Protocol defining the shape of a Session provider.

Allows Mind layer to access DB infrastructure via injection.
"""

from __future__ import annotations

from contextlib import AbstractAsyncContextManager
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
# ID: 2331a8d3-36e3-4bf3-aa76-b4fbbb110194
class SessionProviderProtocol(Protocol):
    """The formal blueprint for getting a DB session."""

    # ID: 32604693-5d46-4f66-b006-9704313f6681
    def session(self) -> AbstractAsyncContextManager[Any]: ...
