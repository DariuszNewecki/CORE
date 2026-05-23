# src/api/cli/quality_client.py

"""Quality namespace sub-client for CoreApiClient (issue #360).

Covers /v1/quality/*. Accessed via the facade as `core_api_client.quality`.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: 2e3200fc-86e0-4f95-9a1b-83b2ccfd2ec6
class QualityClient:
    """Sub-client for /quality/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 4f8fbaeb-0a08-45b9-b38a-dab3039b56c0
    async def quality_imports(self, target_files: list[str] | None = None) -> dict:
        """POST /v1/quality/imports — synchronous import-resolution check."""
        return await self._facade._request(
            "POST",
            "/v1/quality/imports",
            json={"target_files": target_files or []},
        )

    # ID: 49bfd745-751c-4e87-8fc5-175acca51511
    async def quality_body_ui(self, target_files: list[str] | None = None) -> dict:
        """POST /v1/quality/body-ui — synchronous Body-layer UI contract check."""
        return await self._facade._request(
            "POST",
            "/v1/quality/body-ui",
            json={"target_files": target_files or []},
        )

    # ID: 48a167ac-14f3-4b84-9b73-94eaf4a430d0
    async def quality_policy_coverage(self) -> dict:
        """POST /v1/quality/policy-coverage — sync constitutional policy-coverage audit.

        Returns the flattened PolicyCoverageReport: {report_id,
        generated_at_utc, repo_root, summary, records, exit_code}.
        """
        return await self._facade._request(
            "POST", "/v1/quality/policy-coverage", json={}
        )

    # ID: b1809257-a30c-4629-b064-dcad6b592c5d
    async def quality_lint(self, fix: bool = False) -> dict:
        """POST /v1/quality/lint — async ruff lint run (fix=true applies --fix)."""
        return await self._facade._request(
            "POST",
            "/v1/quality/lint",
            json={"fix": fix},
        )

    # ID: 762057fc-0a60-4c1c-afb6-f9e3502d5f90
    async def quality_tests(self, path: str | None = None) -> dict:
        """POST /v1/quality/tests — async pytest run."""
        return await self._facade._request(
            "POST",
            "/v1/quality/tests",
            json={"path": path},
        )

    # ID: bd7db7b5-4e78-4ddb-82ed-8c5b6eda3742
    async def quality_system(self) -> dict:
        """POST /v1/quality/system — async lint + tests + audit bundle."""
        return await self._facade._request("POST", "/v1/quality/system", json={})

    # ID: aea726cc-5ef4-493b-9068-db8cb6b08f9c
    async def quality_gates(self) -> dict:
        """POST /v1/quality/gates — async six-gate quality bundle."""
        return await self._facade._request("POST", "/v1/quality/gates", json={})
