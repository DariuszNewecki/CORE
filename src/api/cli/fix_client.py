# src/api/cli/fix_client.py

"""Fix namespace sub-client for CoreApiClient (issue #360).

Covers /v1/fix/* and /v1/actions. Accessed via the facade as
`core_api_client.fix`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 8ae59396-5ea3-4b83-8753-d2a0b1eadb27
class FixClient:
    """Sub-client for /fix/* and /actions endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: fb719d93-d058-4517-8818-7e86a12ad43c
    async def list_fix_commands(self) -> dict:
        """GET /v1/fix/commands — list registered fix commands."""
        return await self._facade._request("GET", "/v1/fix/commands")

    # ID: 5e2aa721-01af-4244-8d23-f0e72909cd17
    async def list_actions(self) -> dict:
        """GET /v1/actions — list all registered atomic actions."""
        return await self._facade._request("GET", "/v1/actions")

    # ID: 4a4c82b7-63fe-4076-b07f-3b6d55c0a265
    async def run_fix(
        self,
        fix_id: str,
        target_files: list[str] | None = None,
        write: bool = False,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """POST /v1/fix/run/{fix_id} — dispatch a registered fix action.

        `params` carries action-specific kwargs (e.g. fix.docstrings's
        `limit`); forwarded to ActionExecutor as **kwargs.
        """
        return await self._facade._request(
            "POST",
            f"/v1/fix/run/{fix_id}",
            json={
                "target_files": target_files or [],
                "write": write,
                "params": params or {},
            },
        )

    # ID: fa36d0ec-f588-43dc-a46e-2a1b1ced8799
    async def fix_all(self, write: bool = False) -> dict:
        """POST /v1/fix/all — run the curated flow.fix_code sequence."""
        return await self._facade._request(
            "POST",
            "/v1/fix/all",
            json={"write": write},
        )

    # ID: 861f09ab-deef-4c29-9870-6d21c4b3a4ba
    async def fix_modularity(
        self,
        write: bool = False,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """POST /v1/fix/modularity — trigger modularity remediation.

        `params` carries kwargs forwarded to
        will.self_healing.ModularityRemediationService.remediate_batch
        (e.g. `min_score`, `limit`).
        """
        return await self._facade._request(
            "POST",
            "/v1/fix/modularity",
            json={"write": write, "params": params or {}},
        )

    # ID: 4691876d-3fd5-4449-a038-0894480f286f
    async def fix_ir(self, kind: str) -> dict:
        """POST /v1/fix/ir — scaffold an IR YAML file (triage or log)."""
        return await self._facade._request(
            "POST",
            "/v1/fix/ir",
            json={"kind": kind},
        )

    # ID: 037af02f-fbaf-4da8-8746-c8b9a28b4432
    async def get_fix_run(self, run_id: str) -> dict:
        """GET /v1/fix/runs/{run_id} — fetch a fix run's status and result."""
        return await self._facade._request("GET", f"/v1/fix/runs/{run_id}")
