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
