# src/api/cli/integrity_client.py

"""Integrity namespace sub-client for CoreApiClient (issue #360).

Covers /v1/integrity/* (ADR-055 D6 follow-up, #353). Accessed via the
facade as `core_api_client.integrity`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 6f3a9345-83a9-4199-a52f-4d032e2883a1
class IntegrityClient:
    """Sub-client for /integrity/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 6afef209-3b8c-4dfd-93da-006cb0576106
    async def baseline(self, label: str = "default") -> dict:
        """POST /v1/integrity/baseline — SHA256-fingerprint src/."""
        return await self._facade._request(
            "POST",
            "/v1/integrity/baseline",
            json={"label": label},
        )

    # ID: deeb12f0-a8e1-4b5e-81da-d3fa945dcbf8
    async def verify(self, label: str = "default") -> dict:
        """POST /v1/integrity/verify — diff src/ against a named baseline."""
        return await self._facade._request(
            "POST",
            "/v1/integrity/verify",
            json={"label": label},
        )
