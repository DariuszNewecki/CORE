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

    # ID: 4b9e2d7a-8c3f-4a1e-b6d4-2e7a9c5f1b3d
    async def setup(
        self,
        *,
        api_url: str,
        embedding_model: str,
        chat_model: str,
        locality: str = "local",
        embedding_api_url: str = "",
        embedding_locality: str = "",
        write: bool = False,
    ) -> dict:
        """POST /v1/llm-resources/setup — the one-step model setup (#1374)."""
        return await self._facade._request(
            "POST",
            "/v1/llm-resources/setup",
            json={
                "api_url": api_url,
                "embedding_model": embedding_model,
                "chat_model": chat_model,
                "locality": locality,
                "embedding_api_url": embedding_api_url,
                "embedding_locality": embedding_locality,
                "write": write,
            },
        )

    # ID: 8f1c6a3e-2d9b-4e7a-a5c8-3b6e1d9f4a2c
    async def check(self) -> dict:
        """POST /v1/llm-resources/check — call both setup models once."""
        return await self._facade._request("POST", "/v1/llm-resources/check")
