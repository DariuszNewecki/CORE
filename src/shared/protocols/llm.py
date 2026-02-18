# src/shared/protocols/llm.py

"""
Protocol defining the shape of an LLM Client.

Allows Mind/Will layers to use AI without importing Body implementations.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable


@runtime_checkable
# ID: eda72309-ce4a-43a7-b25b-edce15912fad
class LLMClientProtocol(Protocol):
    """The formal blueprint for an LLM requester."""

    # ID: e5c09d35-665a-4b15-922d-5486579a4d09
    async def make_request(
        self,
        prompt: str,
        system_prompt: str = "You are a helpful assistant.",
        max_tokens: int = 4096,
    ) -> str: ...
