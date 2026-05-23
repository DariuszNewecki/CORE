# src/api/cli/integration_client.py

"""Integration namespace sub-client for CoreApiClient (issue #360).

Covers /v1/integrate and /v1/lint. Accessed via the facade as
`core_api_client.integration`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: c3f4b99b-4a50-4b27-ae4a-124e80158523
class IntegrationClient:
    """Sub-client for /integrate and /lint endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 6ffecf82-ab85-4571-abb0-c666da7a7b6a
    async def integrate(self, commit_message: str) -> dict:
        """POST /v1/integrate — stage, format, lint, and commit working-tree changes."""
        return await self._facade._request(
            "POST",
            "/v1/integrate",
            json={"commit_message": commit_message},
            timeout=300.0,
        )

    # ID: 0c7ef9a9-17ca-4003-90c1-d390297efb16
    async def lint(self) -> dict:
        """POST /v1/lint — run black --check and ruff check on src/ and tests/."""
        return await self._facade._request("POST", "/v1/lint", timeout=300.0)
