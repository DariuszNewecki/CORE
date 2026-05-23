# src/api/cli/census_client.py

"""Census namespace sub-client for CoreApiClient (issue #360).

Covers /v1/census/* (ADR-058 D1). Accessed via the facade as
`core_api_client.census`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: d404ec40-f91b-4fa1-9c9f-601d48db64ee
class CensusClient:
    """Sub-client for /census/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP and `self._facade._poll_at_path`
    for polling.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 0e87b0fd-8ace-4226-96c4-61a0f48c3c10
    async def census_run(
        self, snapshot: bool = False, requested_by: str = "api"
    ) -> dict:
        """POST /v1/census/runs — dispatch a CIM-0 structural census."""
        return await self._facade._request(
            "POST",
            "/v1/census/runs",
            json={"snapshot": snapshot, "requested_by": requested_by},
        )

    # ID: 4bca8e01-c366-426d-94ee-b303cf340111
    async def get_census_run(self, run_id: str) -> dict:
        """GET /v1/census/runs/{run_id} — fetch a census_runs row."""
        return await self._facade._request("GET", f"/v1/census/runs/{run_id}")

    # ID: fdbfebb8-8c63-4b5f-9350-f2311a7f3fd7
    async def poll_census_run(
        self, run_id: str, timeout_seconds: float = 1800.0
    ) -> dict:
        """Poll a census run until terminal. CIM-0 traversal can be slow."""
        return await self._facade._poll_at_path(
            f"/v1/census/runs/{run_id}", timeout_seconds=timeout_seconds
        )

    # ID: 48bd7f42-fb2c-467f-8512-4883eadedf7d
    async def census_create_baseline(
        self, name: str, snapshot_file: str | None = None
    ) -> dict:
        """POST /v1/census/baselines/{name} — create a named baseline."""
        return await self._facade._request(
            "POST",
            f"/v1/census/baselines/{name}",
            json={"snapshot_file": snapshot_file},
        )

    # ID: 1aaeb14e-8c7f-4e50-85af-a77052ba3942
    async def census_list_baselines(self) -> dict:
        """GET /v1/census/baselines — list all named baselines."""
        return await self._facade._request("GET", "/v1/census/baselines")

    # ID: 8c073b32-2f9d-406e-a3a4-7d9862377173
    async def census_diff(self, baseline: str | None = None) -> dict:
        """GET /v1/census/diff — diff current vs baseline (or previous)."""
        params: dict[str, Any] = {}
        if baseline is not None:
            params["baseline"] = baseline
        return await self._facade._request("GET", "/v1/census/diff", params=params)
