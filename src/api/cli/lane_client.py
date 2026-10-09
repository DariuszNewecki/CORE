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

    # ID: fb8b18eb-6c8f-4e83-b93e-40c3fd375410
    async def claim(self, finding_id: str, agent: str) -> dict:
        """POST /v1/lane/{finding_id}/claim — mark a finding as being worked."""
        return await self._facade._request(
            "POST",
            f"/v1/lane/{finding_id}/claim",
            params={"agent": agent},
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
