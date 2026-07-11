# src/api/cli/symbols_client.py

"""Symbols namespace sub-client for CoreApiClient (ADR-146 D2).

Read-only diagnostic surface: /v1/symbols/unassigned and /v1/symbols/drift.
Mutation ops (fix-ids, resolve-duplicates, sync) delegate to FixClient via
POST /fix/run/{fix_id} using the existing CoreApiClient.fix sub-client.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 967ab182-7416-49a2-9a13-6b12a1a9497b
class SymbolsClient:
    """Sub-client for /symbols/* read endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 47732c8c-03f9-4553-9e28-490a2bbc37f1
    async def get_unassigned(self) -> dict:
        """GET /v1/symbols/unassigned — symbols with no capability assignment."""
        return await self._facade._request("GET", "/v1/symbols/unassigned")

    # ID: 01a59d9c-3fac-42b2-b9e0-5082f26c694e
    async def get_drift(self) -> dict:
        """GET /v1/symbols/drift — pipeline-sourced drift summary."""
        return await self._facade._request("GET", "/v1/symbols/drift")
