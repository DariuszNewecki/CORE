# src/api/cli/client.py

"""Thin async HTTP client for the CORE API (ADR-054)."""

from __future__ import annotations

import asyncio
from typing import Any

import httpx


_DEFAULT_BASE_URL = "http://127.0.0.1:8000"
_DEFAULT_TIMEOUT_SECONDS = 30.0
_POLL_INTERVAL_SECONDS = 1.0
_POLL_TERMINAL_STATES = frozenset({"completed", "failed"})


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

    # ID: b67c3e8d-93d5-4307-a347-4a6d50ab768d
    async def audit(
        self,
        rule_ids: list[str] | None = None,
        policy_ids: list[str] | None = None,
        files: list[str] | None = None,
        force_llm: bool = False,
        source: str = "api",
    ) -> dict:
        """POST /v1/audit/runs with wait=true — full sync audit result.

        Returns the dict the server's run_sync_audit emits: verdict,
        passed, stats, findings, executed_rule_ids, auto_ignored,
        run_id (None for filtered runs), duration_sec. Audit duration
        is ~60s; uses a 300s HTTP timeout matching integrate() and
        lint().
        """
        return await self._request(
            "POST",
            "/v1/audit/runs",
            json={
                "rule_ids": rule_ids or [],
                "policy_ids": policy_ids or [],
                "files": files or [],
                "force_llm": force_llm,
                "source": source,
                "wait": True,
            },
            timeout=300.0,
        )

    # ID: d4b48241-75a5-4e53-bc46-e80b0c8e36e5
    async def list_fix_commands(self) -> dict:
        """GET /v1/fix/commands — list registered fix commands."""
        return await self._request("GET", "/v1/fix/commands")

    # ID: ae1230d2-9f37-4e2f-9025-8b409a73ee32
    async def list_actions(self) -> dict:
        """GET /v1/actions — list all registered atomic actions."""
        return await self._request("GET", "/v1/actions")

    # ID: cca11da8-9878-4c7e-9149-1972446a9d81
    async def run_fix(
        self,
        fix_id: str,
        target_files: list[str] | None = None,
        write: bool = False,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """POST /v1/fix/run/{fix_id} — dispatch a registered fix action.

        `params` carries action-specific kwargs (e.g. fix.docstrings's
        `limit`); forwarded to ActionExecutor as **kwargs.
        """
        return await self._request(
            "POST",
            f"/v1/fix/run/{fix_id}",
            json={
                "target_files": target_files or [],
                "write": write,
                "params": params or {},
            },
        )

    # ID: b54035a3-7c41-452c-bd1d-2cb7c92e9214
    async def fix_all(self, write: bool = False) -> dict:
        """POST /v1/fix/all — run the curated flow.fix_code sequence."""
        return await self._request(
            "POST",
            "/v1/fix/all",
            json={"write": write},
        )

    # ID: 22c3d638-ed25-40a0-8aec-52c569e5e776
    async def fix_modularity(
        self,
        write: bool = False,
        params: dict[str, Any] | None = None,
    ) -> dict:
        """POST /v1/fix/modularity — trigger modularity remediation.

        `params` carries kwargs forwarded to
        will.self_healing.ModularityRemediationService.remediate_batch
        (e.g. `min_score`, `limit`).
        """
        return await self._request(
            "POST",
            "/v1/fix/modularity",
            json={"write": write, "params": params or {}},
        )

    # ID: 4dcdaddd-1cd1-4561-9d1b-6e76637bada6
    async def fix_ir(self, kind: str) -> dict:
        """POST /v1/fix/ir — scaffold an IR YAML file (triage or log)."""
        return await self._request(
            "POST",
            "/v1/fix/ir",
            json={"kind": kind},
        )

    # ID: 42e18693-ee64-42e7-bf48-dd855f2f3463
    async def get_fix_run(self, run_id: str) -> dict:
        """GET /v1/fix/runs/{run_id} — fetch a fix run's status and result."""
        return await self._request("GET", f"/v1/fix/runs/{run_id}")

    # ID: 1205e380-4b68-4a53-b56d-0eec74896962
    async def _poll_run(self, run_id: str, timeout_seconds: float = 300.0) -> dict:
        """Poll GET /v1/fix/runs/{run_id} until status is completed or failed.

        Returns the terminal run payload. Raises TimeoutError if the run
        does not reach a terminal state within `timeout_seconds`. Used by
        CLIs over async /fix and /quality endpoints (ADR-055 D2/D3).
        """
        async with asyncio.timeout(timeout_seconds):
            while True:
                payload = await self.get_fix_run(run_id)
                if payload.get("status") in _POLL_TERMINAL_STATES:
                    return payload
                await asyncio.sleep(_POLL_INTERVAL_SECONDS)

    # ID: 7863008f-424f-4e14-b461-eeb8b969291e
    async def quality_imports(self, target_files: list[str] | None = None) -> dict:
        """POST /v1/quality/imports — synchronous import-resolution check."""
        return await self._request(
            "POST",
            "/v1/quality/imports",
            json={"target_files": target_files or []},
        )

    # ID: e2563ebe-4fc9-45aa-91bc-a362ce637e95
    async def quality_body_ui(self, target_files: list[str] | None = None) -> dict:
        """POST /v1/quality/body-ui — synchronous Body-layer UI contract check."""
        return await self._request(
            "POST",
            "/v1/quality/body-ui",
            json={"target_files": target_files or []},
        )

    # ID: 0774cb34-3305-4fee-89b3-8f33bec667a9
    async def quality_lint(self, fix: bool = False) -> dict:
        """POST /v1/quality/lint — async ruff lint run (fix=true applies --fix)."""
        return await self._request(
            "POST",
            "/v1/quality/lint",
            json={"fix": fix},
        )

    # ID: 1824000e-1ced-488b-a083-56e2e25529ec
    async def quality_tests(self, path: str | None = None) -> dict:
        """POST /v1/quality/tests — async pytest run."""
        return await self._request(
            "POST",
            "/v1/quality/tests",
            json={"path": path},
        )

    # ID: efdd8365-2deb-4093-b03e-fb5aa303647f
    async def quality_system(self) -> dict:
        """POST /v1/quality/system — async lint + tests + audit bundle."""
        return await self._request("POST", "/v1/quality/system", json={})

    # ID: d41045dd-54cb-4b72-897b-55ed29d3f305
    async def quality_gates(self) -> dict:
        """POST /v1/quality/gates — async six-gate quality bundle."""
        return await self._request("POST", "/v1/quality/gates", json={})
