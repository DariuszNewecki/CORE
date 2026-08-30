# src/api/cli/cognitive_roles_client.py
"""Cognitive-roles namespace sub-client for CoreApiClient (#821 Unit 2).

Covers /v1/cognitive-roles/* (governor-only). Accessed via the facade as
`core_api_client.cognitive_roles`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: e6c1a9f4-3b7d-4e2c-a5f9-8d2b4c7e1a9f
class CognitiveRolesClient:
    """Sub-client for /cognitive-roles/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP, matching SyncClient's pattern.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: f7d2b0a5-4c8e-4f3d-b6a1-9e3c5d8f2b0a
    async def project(self, write: bool = False) -> dict:
        """POST /v1/cognitive-roles/project — diff (write=False) or apply (write=True)."""
        return await self._facade._request(
            "POST",
            "/v1/cognitive-roles/project",
            json={"write": write},
        )
