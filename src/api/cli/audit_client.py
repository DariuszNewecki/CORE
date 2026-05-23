# src/api/cli/audit_client.py

"""Audit namespace sub-client for CoreApiClient (issue #360).

Covers /v1/audit/runs and /v1/audit/remediations. Accessed via the
facade as `core_api_client.audits` — the attribute is pluralised to
avoid collision with the `audit()` method on the facade.
"""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from api.cli.client import CoreApiClient


# ID: e3e5a3e4-acaa-4003-a19b-c4c04a1d3777
class AuditClient:
    """Sub-client for /audit/* endpoints.

    Constructed by and bound to a CoreApiClient facade; uses
    `self._facade._request` for HTTP and `self._facade._poll_at_path`
    for polling.
    """

    def __init__(self, facade: CoreApiClient) -> None:
        self._facade = facade

    # ID: 746cb31b-78bc-44e8-a4c0-c60ba0785a8a
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
        return await self._facade._request(
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

    # ID: 7b45ae44-3004-4924-92d9-a2039285cb92
    async def audit_remediate(
        self,
        audit_run_id: str,
        mode: str = "safe",
        write: bool = False,
    ) -> dict:
        """POST /v1/audit/remediations — dispatch autonomous audit remediation."""
        return await self._facade._request(
            "POST",
            "/v1/audit/remediations",
            json={
                "audit_run_id": audit_run_id,
                "mode": mode,
                "write": write,
            },
        )

    # ID: 0942ee5a-1361-4081-b960-9b17e9a2e5c4
    async def get_audit_remediation_run(self, run_id: str) -> dict:
        """GET /v1/audit/remediations/{run_id} — fetch a remediation_runs row."""
        return await self._facade._request("GET", f"/v1/audit/remediations/{run_id}")

    # ID: d80816c8-e131-4283-ad13-d642f98c6cb8
    async def poll_audit_remediation_run(
        self, run_id: str, timeout_seconds: float = 1800.0
    ) -> dict:
        """Poll an audit remediation run until terminal."""
        return await self._facade._poll_at_path(
            f"/v1/audit/remediations/{run_id}", timeout_seconds=timeout_seconds
        )
