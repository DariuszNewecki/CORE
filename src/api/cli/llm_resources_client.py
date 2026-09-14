# src/api/cli/llm_resources_client.py
"""llm-resources namespace sub-client for CoreApiClient (#821 Unit 3).

Covers /v1/llm-resources/* (governor-only). Accessed via the facade as
`core_api_client.llm_resources`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: ee03fc4a-8498-445e-a4e3-075b60bb95df
class LlmResourcesClient:
    """Sub-client for /llm-resources/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP, matching CognitiveRolesClient's pattern.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 600be55d-c052-4ae2-adb5-5489eeebfc9e
    async def author(self, definition: dict[str, Any], write: bool = False) -> dict:
        """POST /v1/llm-resources/author — validate (write=False) or persist (write=True)."""
        return await self._facade._request(
            "POST",
            "/v1/llm-resources/author",
            json={"definition": definition, "write": write},
        )
