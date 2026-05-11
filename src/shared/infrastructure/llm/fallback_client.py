# src/shared/infrastructure/llm/fallback_client.py

"""
FallbackAwareLLMClient — wraps an ordered chain of LLM resources with
lazy client construction and transparent fallback.

Each resource in the chain is held as a factory callable. The wrapper
builds the underlying ``LLMClient`` only when a call actually reaches
that position. Two failure modes are skipped and recorded as "tried":

1. ``httpx.HTTPStatusError`` with status 402 (Payment Required) or 429
   (Too Many Requests) — the resource is reachable but out of quota.
2. ``ValueError`` raised by the factory itself — typically a provisioning
   failure (missing ``api_url`` / ``model_name`` in ``runtime_settings``,
   missing ``env_prefix``). The resource cannot be reached at all.

When every resource has been disqualified, ``ProviderQuotaExhausted`` is
raised with the per-resource reason tags. Other exceptions propagate
unchanged so genuine bugs and 5xx failures are not masked.

Lazy construction matters: prior to this design, the orchestrator built
clients eagerly via a list comprehension, so a single misconfigured
resource anywhere in the qualified set raised ``ValueError`` during
chain construction and poisoned the entire role — even when an earlier,
healthy resource would have served the call. Surfaced as a regression
in the Architect role (#293 follow-up).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

import httpx

from shared.exceptions import ProviderQuotaExhausted
from shared.infrastructure.llm.client import LLMClient
from shared.logger import getLogger


logger = getLogger(__name__)


_RETRYABLE_STATUSES: frozenset[int] = frozenset({402, 429})

ClientFactory = Callable[[], Awaitable[LLMClient]]


# ID: 4e7b9d2a-3c1f-4a85-b6d9-2e8c5f7a1b3d
class FallbackAwareLLMClient:
    """
    Duck-compatible wrapper around an ordered chain of LLM resources.
    Exposes the same public surface as ``LLMClient``
    (``make_request_async``, ``make_request_with_system_async``,
    ``get_embedding``) so existing callers of
    ``CognitiveService.aget_client_for_role`` need no change.
    """

    def __init__(
        self,
        client_factories: list[ClientFactory],
        resource_names: list[str],
    ) -> None:
        if not client_factories:
            raise ValueError(
                "FallbackAwareLLMClient requires at least one client factory."
            )
        if len(client_factories) != len(resource_names):
            raise ValueError(
                "client_factories and resource_names must have the same length "
                f"(got {len(client_factories)} factories, "
                f"{len(resource_names)} names)."
            )
        self._client_factories = client_factories
        self._resource_names = resource_names
        self._clients: dict[int, LLMClient] = {}
        self._unavailable: dict[int, str] = {}

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

    async def _ensure_client(self, idx: int) -> LLMClient:
        if idx not in self._clients:
            self._clients[idx] = await self._client_factories[idx]()
        return self._clients[idx]

    async def _call_with_fallback(
        self, method_name: str, *args: Any, **kwargs: Any
    ) -> Any:
        tried: list[tuple[str, str]] = []
        for idx in range(len(self._client_factories)):
            name = self._resource_names[idx]

            if idx in self._unavailable:
                tried.append((name, self._unavailable[idx]))
                continue

            try:
                client = await self._ensure_client(idx)
            except ValueError as e:
                tag = "provisioning_error"
                self._unavailable[idx] = tag
                tried.append((name, tag))
                logger.warning(
                    "LLM resource '%s' failed to provision (%s) — marking "
                    "unavailable, trying next fallback (%d/%d)",
                    name,
                    e,
                    idx + 1,
                    len(self._client_factories),
                )
                continue

            try:
                return await getattr(client, method_name)(*args, **kwargs)
            except httpx.HTTPStatusError as e:
                status = e.response.status_code
                if status not in _RETRYABLE_STATUSES:
                    raise
                tag = str(status)
                self._unavailable[idx] = tag
                tried.append((name, tag))
                logger.warning(
                    "LLM resource '%s' returned %d on %s — marking "
                    "unavailable, trying next fallback (%d/%d)",
                    name,
                    status,
                    method_name,
                    idx + 1,
                    len(self._client_factories),
                )

        raise ProviderQuotaExhausted(tried_resources=tried)
