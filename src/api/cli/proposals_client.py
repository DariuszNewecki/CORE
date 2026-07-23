# src/api/cli/proposals_client.py

"""Proposals namespace sub-client for CoreApiClient (issue #360).

Covers /v1/proposals/*. Accessed via the facade as
`core_api_client.proposals`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 8472ad98-79a0-4b7e-91bf-1dda947c3d0a
class ProposalsClient:
    """Sub-client for /proposals/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 3bc55abf-2046-473c-9f77-9e0db3525a02
    async def create_proposal(
        self,
        goal: str,
        actions: list[dict] | None = None,
        files: list[str] | None = None,
        created_by: str = "cli_operator",
        write: bool = True,
    ) -> dict:
        """POST /v1/proposals — create a new proposal (dry-run when write=False)."""
        return await self._facade._request(
            "POST",
            "/v1/proposals",
            json={
                "goal": goal,
                "actions": actions or [],
                "files": files or [],
                "created_by": created_by,
                "write": write,
            },
        )

    # ID: 0c3fd55c-ae4a-477b-9f59-2fe5c64ccc2c
    async def list_proposals(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> dict:
        """GET /v1/proposals — list proposals, optionally filtered by status."""
        params: dict = {"limit": limit}
        if status is not None:
            params["status"] = status
        return await self._facade._request("GET", "/v1/proposals", params=params)

    # ID: c45e1e26-7004-4961-a912-fcc6bf58997a
    async def get_proposal(self, proposal_id: str) -> dict:
        """GET /v1/proposals/{id} — fetch a single proposal by id."""
        return await self._facade._request("GET", f"/v1/proposals/{proposal_id}")

    # ID: bd72561f-494c-43d1-80f5-b0b3bf13a143
    async def approve_proposal(
        self,
        proposal_id: str,
        approved_by: str,
        approval_authority: str,
    ) -> dict:
        """POST /v1/proposals/{id}/approve — authorize a proposal for execution."""
        return await self._facade._request(
            "POST",
            f"/v1/proposals/{proposal_id}/approve",
            json={
                "approved_by": approved_by,
                "approval_authority": approval_authority,
            },
        )

    # ID: 0d896778-608e-4ae5-93e2-449c9d2421a7
    async def reject_proposal(self, proposal_id: str, reason: str) -> dict:
        """POST /v1/proposals/{id}/reject — reject a proposal with a reason."""
        return await self._facade._request(
            "POST",
            f"/v1/proposals/{proposal_id}/reject",
            json={"reason": reason},
        )

    # ID: 181068f0-dc97-4d46-95b3-b8bb9c2f3d86
    async def execute_proposal(self, proposal_id: str, write: bool = False) -> dict:
        """POST /v1/proposals/{id}/execute — execute an approved proposal."""
        return await self._facade._request(
            "POST",
            f"/v1/proposals/{proposal_id}/execute",
            json={"write": write},
        )

    # ID: c9e41e95-e71f-415c-9dea-7184c9e1c473
    async def get_proposal_chain(self, proposal_id: str) -> dict:
        """GET /v1/proposals/{id}/chain — exact-ID governance chain evidence
        (finding, proposal, consequence). ADR-155 D6/D12: the only sanctioned
        evidence source for the isolated consequence-chain demo's chain
        rendering — never "latest" selection or direct SQL.
        """
        return await self._facade._request("GET", f"/v1/proposals/{proposal_id}/chain")
