# src/api/cli/lane_client.py

"""Lane namespace sub-client for CoreApiClient (ADR-109, issue #652).

Covers /v1/lane/*. Accessed via the facade as `core_api_client.lane`.
The Assisted Remediation Lane is the external-agent contract for working
delegated findings (`indeterminate` + `human`) under human-gated approval.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 3ac1a30e-ea63-456e-bce3-4e96d7aac0aa
class LaneClient:
    """Sub-client for /lane/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: edcf8cfb-a897-4699-bd3b-5d4e2b0eafce
    async def list_delegated(self, limit: int = 50) -> dict:
        """GET /v1/lane — list delegated findings (the assisted-lane queue)."""
        return await self._facade._request(
            "GET",
            "/v1/lane",
            params={"limit": limit},
        )

    # ID: bbfbfc6b-1ad5-40cc-b396-db7e93a9ec20
    async def get_delegated(self, finding_id: str) -> dict:
        """GET /v1/lane/{finding_id} — one delegated finding (404 if not live)."""
        return await self._facade._request(
            "GET",
            f"/v1/lane/{finding_id}",
        )

    # ID: 4779d328-4aa3-4ef0-8e67-2f289baf8b85
    async def propose(
        self, finding_id: str, patch: str, validation_run_id: str
    ) -> dict:
        """POST /v1/lane/{finding_id}/propose — ingest a validated diff as a proposal.

        `validation_run_id` is the id of the `assisted.validate_diff` run
        (dispatched via run_fix) that cleared this patch; the endpoint re-reads
        its persisted verdict before creating the proposal.
        """
        return await self._facade._request(
            "POST",
            f"/v1/lane/{finding_id}/propose",
            json={"patch": patch, "validation_run_id": validation_run_id},
        )
