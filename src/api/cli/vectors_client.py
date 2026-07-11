# src/api/cli/vectors_client.py

"""Vectors namespace sub-client for CoreApiClient (ADR-146 D2).

Covers /v1/vectors/*. Accessed via the facade as `core_api_client.vectors`.
For vector sync operations (sync, sync-code), use the existing SyncClient.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 3cac9fc5-d601-4c1d-8f3e-6451aaf6675f
class VectorsClient:
    """Sub-client for /vectors/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 5f47153e-4cef-4a7a-b902-d9c01a57cf17
    async def status(self) -> dict:
        """GET /v1/vectors/status — list Qdrant collections with status."""
        return await self._facade._request("GET", "/v1/vectors/status")

    # ID: dcdfd8b8-3408-4dd1-af46-b0e6c296e32f
    async def query(
        self,
        query: str,
        collection: str = "policies",
        limit: int = 5,
    ) -> dict:
        """POST /v1/vectors/query — semantic search over a named collection."""
        return await self._facade._request(
            "POST",
            "/v1/vectors/query",
            json={"query": query, "collection": collection, "limit": limit},
        )

    # ID: 0e6ed064-cde8-4ef6-95be-9cdd4a8679d4
    async def rebuild(self, collection: str, write: bool = False) -> dict:
        """POST /v1/vectors/rebuild — delete collection + reset chunk_count."""
        return await self._facade._request(
            "POST",
            "/v1/vectors/rebuild",
            json={"collection": collection, "write": write},
        )
