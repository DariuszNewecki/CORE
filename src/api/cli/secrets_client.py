# src/api/cli/secrets_client.py

"""Secrets namespace sub-client for CoreApiClient (ADR-146 D2).

Covers /v1/secrets/*. Accessed via the facade as `core_api_client.secrets`.
Manages encrypted secrets stored in the governed project's CORE installation.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 0618378f-13b3-4e58-a3e7-c5b424abcb97
class SecretsClient:
    """Sub-client for /secrets/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 2e35806a-9d53-4072-9218-9b2d208f04ee
    async def list_secrets(self) -> dict:
        """List all secret keys (no values)."""
        return await self._facade._request("GET", "/v1/secrets")

    # ID: 9e53db8b-cc66-4d5b-81ab-9a8a2da8465b
    async def set_secret(
        self,
        key: str,
        value: str,
        description: str | None = None,
        force: bool = False,
    ) -> dict:
        """Create or overwrite an encrypted secret."""
        return await self._facade._request(
            "POST",
            "/v1/secrets",
            json={
                "key": key,
                "value": value,
                "description": description,
                "force": force,
            },
        )

    # ID: a274fd8f-eb15-41bc-973f-45a079902f16
    async def get_secret(self, key: str, show: bool = False) -> dict:
        """Check whether a secret exists, optionally revealing the value."""
        return await self._facade._request(
            "GET", f"/v1/secrets/{key}", params={"show": show}
        )

    # ID: b45138a4-3363-4007-abb2-3ad02cd35d26
    async def delete_secret(self, key: str) -> dict:
        """Permanently delete a secret."""
        return await self._facade._request("DELETE", f"/v1/secrets/{key}")

    # ID: 72a56475-5e8d-43c5-bf14-6d346be0c977
    async def rotate_secret(self, key: str, new_value: str) -> dict:
        """Replace the value of an existing secret and update last_rotated_at."""
        return await self._facade._request(
            "PUT", f"/v1/secrets/{key}/rotate", json={"new_value": new_value}
        )
