# src/api/cli/daemon_client.py

"""Daemon namespace sub-client for CoreApiClient (issue #360).

Covers /v1/daemon/* (ADR-058 D3). Accessed via the facade as
`core_api_client.daemon`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 692aabbc-6659-4ba4-a137-bbc1c920c77f
class DaemonClient:
    """Sub-client for /daemon/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 3db9fe94-a072-42b1-bb6f-4697266445c0
    async def daemon_status(self) -> dict:
        """GET /v1/daemon/status — daemon liveness + per-worker health."""
        return await self._facade._request("GET", "/v1/daemon/status")

    # ID: fe391d8b-e92b-49a9-9392-0d520f8476ea
    async def daemon_start(self) -> dict:
        """POST /v1/daemon/start — start core-daemon via systemctl."""
        return await self._facade._request("POST", "/v1/daemon/start", json={})

    # ID: 6d4ab8d7-ff36-4cd6-8917-43d7dd4afb57
    async def daemon_stop(self) -> dict:
        """POST /v1/daemon/stop — schedule core-daemon stop (fire-and-forget)."""
        return await self._facade._request("POST", "/v1/daemon/stop", json={})
