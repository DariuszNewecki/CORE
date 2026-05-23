# src/api/cli/refactor_client.py

"""Refactor namespace sub-client for CoreApiClient (issue #360).

Covers /v1/refactor/*. Accessed via the facade as
`core_api_client.refactor`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 784ad541-c8a0-4d7c-baac-7788034b5a7d
class RefactorClient:
    """Sub-client for /refactor/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP and `self._facade._poll_at_path`
    for polling.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: ebcc6da1-83a3-421d-943a-db1933bda593
    async def refactor_threshold(self) -> dict:
        """GET /v1/refactor/threshold — constitutional modularity threshold."""
        return await self._facade._request("GET", "/v1/refactor/threshold")

    # ID: dd32d723-a1e2-465a-95ae-ad6ff6692418
    async def refactor_score(self, file: str) -> dict:
        """GET /v1/refactor/score?file= — per-file modularity score."""
        return await self._facade._request(
            "GET", "/v1/refactor/score", params={"file": file}
        )

    # ID: d2f20f4b-514b-45a2-b088-85183a6b67a2
    async def refactor_candidates(
        self,
        min_score: float | None = None,
        limit: int = 50,
    ) -> dict:
        """GET /v1/refactor/candidates — files exceeding modularity threshold."""
        params: dict[str, Any] = {"limit": limit}
        if min_score is not None:
            params["min_score"] = min_score
        return await self._facade._request(
            "GET", "/v1/refactor/candidates", params=params, timeout=300.0
        )

    # ID: d271251e-04de-44f3-933c-ba5d3c87bef6
    async def refactor_stats(self) -> dict:
        """GET /v1/refactor/stats — aggregate modularity distribution."""
        return await self._facade._request("GET", "/v1/refactor/stats", timeout=300.0)

    # ID: b134eb49-2581-4db0-abd7-1fc4cffac28a
    async def refactor_autonomous(self, goal: str, write: bool = False) -> dict:
        """POST /v1/refactor/autonomous — trigger A3 autonomous refactor cycle."""
        return await self._facade._request(
            "POST",
            "/v1/refactor/autonomous",
            json={"goal": goal, "write": write},
        )

    # ID: 2914d738-7f45-407c-970f-2eb8767dd4eb
    async def get_refactor_run(self, run_id: str) -> dict:
        """GET /v1/refactor/runs/{run_id} — fetch a refactor_runs row."""
        return await self._facade._request("GET", f"/v1/refactor/runs/{run_id}")

    # ID: 63614394-1f03-4643-b5bf-bdf7603b80fa
    async def poll_refactor_run(
        self, run_id: str, timeout_seconds: float = 1800.0
    ) -> dict:
        """Poll a refactor run until terminal. A3 loops can take minutes."""
        return await self._facade._poll_at_path(
            f"/v1/refactor/runs/{run_id}", timeout_seconds=timeout_seconds
        )
