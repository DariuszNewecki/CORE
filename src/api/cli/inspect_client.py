# src/api/cli/inspect_client.py

"""Inspect namespace sub-client for CoreApiClient (issue #360).

Covers /v1/status/*, /v1/decisions/*, /v1/refusals/*, /v1/analysis/*,
/v1/components, /v1/search/*. Accessed via the facade as
`core_api_client.inspect`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 90a0cd13-bae3-49f4-b7e6-156ed056fd8a
class InspectClient:
    """Sub-client for read-only introspection endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: a89090e1-2710-41cc-ab63-444d2f79a527
    async def status_db(self) -> dict:
        """GET /v1/status/db — DB connection and schema state."""
        return await self._facade._request("GET", "/v1/status/db")

    # ID: 7b664840-00e9-4877-accd-e4e46662213b
    async def status_drift(self, scope: str = "all") -> dict:
        """GET /v1/status/drift — consolidated drift snapshot."""
        return await self._facade._request(
            "GET", "/v1/status/drift", params={"scope": scope}
        )

    # ID: d810fc7f-d21e-4200-8678-9ba090ae36de
    async def decisions_list(
        self,
        session_id: str | None = None,
        agent: str | None = None,
        pattern: str | None = None,
        limit: int = 50,
    ) -> dict:
        """GET /v1/decisions — recent decision traces."""
        params: dict[str, Any] = {"limit": limit}
        if session_id is not None:
            params["session_id"] = session_id
        if agent is not None:
            params["agent"] = agent
        if pattern is not None:
            params["pattern"] = pattern
        return await self._facade._request("GET", "/v1/decisions", params=params)

    # ID: 423afac1-a466-4fd7-b94a-66aad65daf4b
    async def decisions_patterns(self, days: int = 7) -> dict:
        """GET /v1/decisions/patterns — pattern classification stats."""
        return await self._facade._request(
            "GET", "/v1/decisions/patterns", params={"days": days}
        )

    # ID: c1576944-7180-424c-bc89-33e8eb3db2c2
    async def refusals_list(
        self,
        refusal_type: str | None = None,
        session_id: str | None = None,
        limit: int = 50,
    ) -> dict:
        """GET /v1/refusals — recent constitutional refusals."""
        params: dict[str, Any] = {"limit": limit}
        if refusal_type is not None:
            params["type"] = refusal_type
        if session_id is not None:
            params["session"] = session_id
        return await self._facade._request("GET", "/v1/refusals", params=params)

    # ID: 38395049-6fb9-4799-b2b6-8628a3c356a5
    async def refusals_stats(self, days: int = 7) -> dict:
        """GET /v1/refusals/stats — refusal statistics by type."""
        return await self._facade._request(
            "GET", "/v1/refusals/stats", params={"days": days}
        )

    # ID: 9527b482-c9c3-4504-b2e4-cc2ccfcc1108
    async def analysis_clusters(self, limit: int = 25) -> dict:
        """GET /v1/analysis/clusters — semantic capability clusters."""
        return await self._facade._request(
            "GET", "/v1/analysis/clusters", params={"limit": limit}
        )

    # ID: 4d56c093-8ded-41c4-bac5-5ef25c89b44e
    async def analysis_duplicates(self, threshold: float = 0.85) -> dict:
        """GET /v1/analysis/duplicates — semantic code duplication candidates."""
        return await self._facade._request(
            "GET",
            "/v1/analysis/duplicates",
            params={"threshold": threshold},
            timeout=300.0,
        )

    # ID: ac51a548-13b9-4f27-95d3-b0e1b393ea32
    async def analysis_common_knowledge(self, limit: int = 25) -> dict:
        """GET /v1/analysis/common-knowledge — DRY-violation candidates."""
        return await self._facade._request(
            "GET", "/v1/analysis/common-knowledge", params={"limit": limit}
        )

    # ID: 2ee57341-aa70-482d-beca-b32d17fe8c02
    async def analysis_command_tree(self) -> dict:
        """GET /v1/analysis/command-tree — introspected CLI command hierarchy."""
        return await self._facade._request("GET", "/v1/analysis/command-tree")

    # ID: ddb23eeb-0bcf-4bdf-9d19-a5e1ed6aa1b7
    async def analysis_test_targets(self) -> dict:
        """GET /v1/analysis/test-targets — SIMPLE/COMPLEX test target classification."""
        return await self._facade._request("GET", "/v1/analysis/test-targets")

    # ID: e677a202-2558-4dd1-9a98-12391ce721d2
    async def inspect_components(self, filter_type: str | None = None) -> dict:
        """GET /v1/components — V2 component inventory (ADR-057 D5)."""
        params: dict[str, Any] = {}
        if filter_type is not None:
            params["type"] = filter_type
        return await self._facade._request("GET", "/v1/components", params=params)

    # ID: 28f208bc-36bf-4335-b245-a02d2eecacdd
    async def inspect_search_capabilities(self, q: str, limit: int = 10) -> dict:
        """GET /v1/search/capabilities — semantic capability search (ADR-057 D5)."""
        return await self._facade._request(
            "GET", "/v1/search/capabilities", params={"q": q, "limit": limit}
        )

    # ID: e94ca5cb-534b-4d96-bc2a-a18ab6caf63f
    async def inspect_search_commands(self, q: str, limit: int = 25) -> dict:
        """GET /v1/search/commands — fuzzy substring search over the CLI registry (ADR-057 D5)."""
        return await self._facade._request(
            "GET", "/v1/search/commands", params={"q": q, "limit": limit}
        )
