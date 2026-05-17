# src/api/cli/client.py

"""Thin async HTTP client for the CORE API (ADR-054)."""

from __future__ import annotations

from typing import Any

import httpx


_DEFAULT_BASE_URL = "http://127.0.0.1:8000"
_DEFAULT_TIMEOUT_SECONDS = 30.0


# ID: 03d88f8c-1a13-4901-a03c-52db4b5ee5b2
class CoreApiClient:
    """Async HTTP client targeting the loopback-bound CORE API.

    ADR-054 D3 keeps the API loopback-only with no authentication for
    Phase 1; this client mirrors that posture (no auth headers).
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or _DEFAULT_BASE_URL
        self.timeout = _DEFAULT_TIMEOUT_SECONDS

    # ID: 77466c97-58c5-4ad2-8e5a-814396965f73
    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()

    # ID: daf8f641-0358-4298-8465-af1d1c09e221
    async def create_proposal(
        self,
        goal: str,
        actions: list[dict] | None = None,
        files: list[str] | None = None,
        created_by: str = "cli_operator",
        write: bool = True,
    ) -> dict:
        """POST /v1/proposals — create a new proposal (dry-run when write=False)."""
        return await self._request(
            "POST",
            "/v1/proposals",
            json={
                "goal": goal,
                "actions": actions or [],
                "files": files or [],
                "created_by": created_by,
                "write": write,
            },
        )

    # ID: 36434e12-c232-4452-9ff5-c0690263804f
    async def list_proposals(
        self,
        status: str | None = None,
        limit: int = 50,
    ) -> dict:
        """GET /v1/proposals — list proposals, optionally filtered by status."""
        params: dict[str, Any] = {"limit": limit}
        if status is not None:
            params["status"] = status
        return await self._request("GET", "/v1/proposals", params=params)

    # ID: 2e321d91-d4e6-45ff-834c-a7394fe47fa0
    async def get_proposal(self, proposal_id: str) -> dict:
        """GET /v1/proposals/{id} — fetch a single proposal by id."""
        return await self._request("GET", f"/v1/proposals/{proposal_id}")

    # ID: 4223e0c4-41e1-4105-9b9a-b65d52b616d9
    async def approve_proposal(
        self,
        proposal_id: str,
        approved_by: str,
        approval_authority: str,
    ) -> dict:
        """POST /v1/proposals/{id}/approve — authorize a proposal for execution."""
        return await self._request(
            "POST",
            f"/v1/proposals/{proposal_id}/approve",
            json={
                "approved_by": approved_by,
                "approval_authority": approval_authority,
            },
        )

    # ID: 85d96758-f6f0-4162-a44f-32d7dd65bf5c
    async def reject_proposal(self, proposal_id: str, reason: str) -> dict:
        """POST /v1/proposals/{id}/reject — reject a proposal with a reason."""
        return await self._request(
            "POST",
            f"/v1/proposals/{proposal_id}/reject",
            json={"reason": reason},
        )

    # ID: f7f70b77-7766-4112-86d5-81d0bf6cd830
    async def execute_proposal(self, proposal_id: str, write: bool = False) -> dict:
        """POST /v1/proposals/{id}/execute — execute an approved proposal."""
        return await self._request(
            "POST",
            f"/v1/proposals/{proposal_id}/execute",
            json={"write": write},
        )

    # ID: 756d1f0f-7315-4fb9-9cd6-4ba14f92dd8a
    async def integrate(self, commit_message: str) -> dict:
        """POST /v1/integrate — stage, format, lint, and commit working-tree changes."""
        return await self._request(
            "POST",
            "/v1/integrate",
            json={"commit_message": commit_message},
            timeout=300.0,
        )

    # ID: 77313481-4787-431c-944f-84a1ab44c594
    async def lint(self) -> dict:
        """POST /v1/lint — run black --check and ruff check on src/ and tests/."""
        return await self._request("POST", "/v1/lint", timeout=300.0)
