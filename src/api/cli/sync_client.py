# src/api/cli/sync_client.py

"""Sync namespace sub-client for CoreApiClient (issue #360).

Covers /v1/sync/* (ADR-058 D2). Accessed via the facade as
`core_api_client.sync`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: b2c87630-4860-495e-83d2-03349d072479
class SyncClient:
    """Sub-client for /sync/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP and `self._facade._poll_at_path`
    for polling.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 0d65500c-229f-4fc0-9575-7cfafdb51968
    async def sync_knowledge_graph(
        self,
        write: bool = False,
        target: str | None = None,
        requested_by: str = "api",
    ) -> dict:
        """POST /v1/sync/knowledge-graph — CLI command tree -> PostgreSQL."""
        return await self._facade._request(
            "POST",
            "/v1/sync/knowledge-graph",
            json={"write": write, "target": target, "requested_by": requested_by},
        )

    # ID: 2a470e64-e22c-4dc1-bc12-0ca7c5efda9c
    async def sync_vectors(
        self,
        write: bool = False,
        target: str | None = None,
        requested_by: str = "api",
    ) -> dict:
        """POST /v1/sync/vectors — constitutional vector sync."""
        return await self._facade._request(
            "POST",
            "/v1/sync/vectors",
            json={"write": write, "target": target, "requested_by": requested_by},
        )

    # ID: a4868645-b7af-4f55-835b-e17860e1c50e
    async def sync_code_vectors(
        self,
        write: bool = False,
        target: str | None = None,
        requested_by: str = "api",
        force: bool = False,
    ) -> dict:
        """POST /v1/sync/code-vectors — codebase symbol embedding.

        `force=True` resets chunk_count on already-embedded artifacts so the
        embed loop re-processes them. No-op when `write` is False.
        """
        return await self._facade._request(
            "POST",
            "/v1/sync/code-vectors",
            json={
                "write": write,
                "target": target,
                "requested_by": requested_by,
                "force": force,
            },
        )

    # ID: d78efc87-ac06-4f1e-b89b-31dc6baf00d2
    async def sync_dev_sync(
        self,
        write: bool = False,
        target: str | None = None,
        requested_by: str = "api",
    ) -> dict:
        """POST /v1/sync/dev-sync — composite fix + knowledge-graph + vectors."""
        return await self._facade._request(
            "POST",
            "/v1/sync/dev-sync",
            json={"write": write, "target": target, "requested_by": requested_by},
        )

    # ID: 7d4494ca-fd4d-4847-9b79-742809263c6f
    async def get_sync_run(self, run_id: str) -> dict:
        """GET /v1/sync/runs/{run_id} — fetch a sync_runs row."""
        return await self._facade._request("GET", f"/v1/sync/runs/{run_id}")

    # ID: 51369913-2fe9-447d-9069-b3cd163ceda2
    async def poll_sync_run(self, run_id: str, timeout_seconds: float = 1800.0) -> dict:
        """Poll a sync run until terminal."""
        return await self._facade._poll_at_path(
            f"/v1/sync/runs/{run_id}", timeout_seconds=timeout_seconds
        )
