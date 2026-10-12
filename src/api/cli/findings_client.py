# src/api/cli/findings_client.py

"""Findings namespace sub-client for CoreApiClient.

Covers POST /v1/findings/{id}/resolve, the governor's closure of a finding
delegated to a human (ADR-132 D10.4). Accessed via the facade as
`core_api_client.findings`; reach it over CORE's Unix socket
(`CORE_API_URL=unix:///run/core/api/api.sock`), since TCP is refused.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 36e40a84-aa3a-4f30-a1e8-07abd1296f72
class FindingsClient:
    """Sub-client for /findings/* endpoints."""

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: c6af42a2-788b-41a2-87c5-aa6dfbf4c91e
    async def resolve(self, entry_id: str, reason: str) -> dict:
        """POST /v1/findings/{entry_id}/resolve — the server names the actor."""
        return await self._facade._request(
            "POST", f"/v1/findings/{entry_id}/resolve", json={"reason": reason}
        )
