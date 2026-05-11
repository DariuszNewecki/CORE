# src/shared/infrastructure/llm/fallback_client.py

"""
FallbackAwareLLMClient — wraps an ordered list of LLMClient instances.

On any call that raises ``httpx.HTTPStatusError`` with status 402 or 429,
the current client is marked unavailable for this wrapper's lifetime and
the same call is retried against the next client in the list. When all
clients are exhausted, ``ProviderQuotaExhausted`` is raised naming each
tried resource and the status code that disqualified it.

Other exceptions propagate unchanged — only quota/billing-style status
codes trigger fallback. This keeps genuine errors (5xx, network failures,
provider bugs) from being silently masked by the fallback path.

Surfaced by issue #293 after DeepSeek 402 stalled the autonomous test
generation loop with no provider failover anywhere in the stack.
"""

from __future__ import annotations

from typing import Any

import httpx

from shared.exceptions import ProviderQuotaExhausted
from shared.infrastructure.llm.client import LLMClient
from shared.logger import getLogger


logger = getLogger(__name__)


_RETRYABLE_STATUSES: frozenset[int] = frozenset({402, 429})


# ID: 4e7b9d2a-3c1f-4a85-b6d9-2e8c5f7a1b3d
class FallbackAwareLLMClient:
    """
    Duck-compatible wrapper around an ordered list of ``LLMClient``
    instances. Exposes the same public surface (``make_request_async``,
    ``make_request_with_system_async``, ``get_embedding``) so existing
    callers of ``CognitiveService.aget_client_for_role`` need no change.
    """

    def __init__(
        self,
        clients: list[LLMClient],
        resource_names: list[str],
    ) -> None:
        if not clients:
            raise ValueError("FallbackAwareLLMClient requires at least one client.")
        if len(clients) != len(resource_names):
            raise ValueError(
                "clients and resource_names must have the same length "
                f"(got {len(clients)} clients, {len(resource_names)} names)."
            )
        self._clients = clients
        self._resource_names = resource_names
        self._unavailable: dict[int, int] = {}
        self.model_name = clients[0].model_name
        self.provider = clients[0].provider

    # ID: 9c2e4d6f-5a8b-4d72-9e1c-3f8b6a2d5c4e
    async def make_request_async(self, *args: Any, **kwargs: Any) -> str:
        return await self._call_with_fallback("make_request_async", *args, **kwargs)

    # ID: b7d3a5c9-2e4f-4861-9c8b-5d7a3e1f9c4b
    async def make_request_with_system_async(self, *args: Any, **kwargs: Any) -> str:
        return await self._call_with_fallback(
            "make_request_with_system_async", *args, **kwargs
        )

    # ID: 5f8a2c4d-9e3b-4751-8c2d-6a4b9e3f1c7d
    async def get_embedding(self, *args: Any, **kwargs: Any) -> list[float]:
        return await self._call_with_fallback("get_embedding", *args, **kwargs)

    async def _call_with_fallback(
        self, method_name: str, *args: Any, **kwargs: Any
    ) -> Any:
        tried: list[tuple[str, int]] = []
        for idx, client in enumerate(self._clients):
            if idx in self._unavailable:
                tried.append((self._resource_names[idx], self._unavailable[idx]))
                continue
            try:
                return await getattr(client, method_name)(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status not in _RETRYABLE_STATUSES:
                    raise
                self._unavailable[idx] = status
                tried.append((self._resource_names[idx], status))
                logger.warning(
                    "LLM resource '%s' returned %d on %s — marking unavailable, "
                    "trying next fallback (%d/%d)",
                    self._resource_names[idx],
                    status,
                    method_name,
                    idx + 1,
                    len(self._clients),
                )
        raise ProviderQuotaExhausted(tried_resources=tried)
