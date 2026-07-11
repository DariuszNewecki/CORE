# src/api/cli/project_client.py

"""Project namespace sub-client for CoreApiClient (ADR-146 D2).

Covers /v1/project/*. Accessed via the facade as `core_api_client.project`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: b3792437-f79c-485b-b45f-a1b3f2aeb355
class ProjectClient:
    """Sub-client for /project/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 779e1957-6c8f-4888-937f-ed208f46586f
    async def generate_docs(
        self, output: str = "docs/10_CAPABILITY_REFERENCE.md"
    ) -> dict:
        """POST /v1/project/docs — generate capability reference documentation."""
        return await self._facade._request(
            "POST", "/v1/project/docs", json={"output": output}
        )

    # ID: c2bdad0e-4778-4a05-a8a8-a5c92ea73cfd
    async def onboard(
        self, path: str, write: bool = False, stage: bool = False
    ) -> dict:
        """POST /v1/project/onboard — deliver BYOR machinery floor to an external repo."""
        return await self._facade._request(
            "POST",
            "/v1/project/onboard",
            json={"path": path, "write": write, "stage": stage},
        )

    # ID: a110aa79-4e0d-49cf-8c5f-a86ffc5cd147
    async def promote(self, path: str) -> dict:
        """POST /v1/project/onboard/promote — promote a staged machinery floor."""
        return await self._facade._request(
            "POST", "/v1/project/onboard/promote", json={"path": path}
        )
