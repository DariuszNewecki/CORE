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
        return await self._poll_at_path(
            f"/v1/fix/runs/{run_id}", timeout_seconds=timeout_seconds
        )

    # ID: c19f4d5e-2b7a-4f8e-bd03-6a8c5d1f9e02
    async def _poll_at_path(self, path: str, timeout_seconds: float = 300.0) -> dict:
        """Poll an arbitrary `GET {path}` until status terminal.

        Generalisation of `_poll_run` for Phase 3 resources whose poll
        paths differ from /v1/fix/runs/ (e.g. /v1/coverage/runs/,
        /v1/refactor/runs/, /v1/audit/remediations/).
        """
        async with asyncio.timeout(timeout_seconds):
            while True:
                payload = await self._request("GET", path)
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

    # ID: 4e6f1a2b-8c3d-47e9-a5b1-2d3f4c5a6b7d
    async def quality_policy_coverage(self) -> dict:
        """POST /v1/quality/policy-coverage — sync constitutional policy-coverage audit.

        Returns the flattened PolicyCoverageReport: {report_id,
        generated_at_utc, repo_root, summary, records, exit_code}.
        """
        return await self._request("POST", "/v1/quality/policy-coverage", json={})

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

    # ------------------------------------------------------------------
    # Phase 3 — /coverage (ADR-057 D1)
    # ------------------------------------------------------------------

    # ID: a8b2c4d6-1e3f-4a5b-6c7d-8e9f0a1b2c3d
    async def coverage_check(self) -> dict:
        """GET /v1/coverage/check — constitutional coverage compliance check."""
        return await self._request("GET", "/v1/coverage/check", timeout=300.0)

    # ID: b9c3d5e7-2f4a-4b6c-7d8e-9f0a1b2c3d4e
    async def coverage_report(
        self, show_missing: bool = False, output_format: str = "text"
    ) -> dict:
        """GET /v1/coverage/report — pytest --cov report.

        `output_format='text'` (default) returns the term report shape;
        `output_format='html'` triggers `--cov-report=html` and returns
        the `htmlcov/` path in `html_path` (#358).
        """
        return await self._request(
            "GET",
            "/v1/coverage/report",
            params={"show_missing": show_missing, "format": output_format},
            timeout=300.0,
        )

    # ID: c0d4e6f8-3a5b-4c7d-8e9f-0a1b2c3d4e5f
    async def coverage_targets(self) -> dict:
        """GET /v1/coverage/targets — constitutional coverage targets."""
        return await self._request("GET", "/v1/coverage/targets")

    # ID: d1e5f7a9-4b6c-4d8e-9f0a-1b2c3d4e5f60
    async def coverage_gaps(self, threshold: float = 75.0, limit: int = 20) -> dict:
        """GET /v1/coverage/gaps — modules below threshold, ranked by deficit."""
        return await self._request(
            "GET",
            "/v1/coverage/gaps",
            params={"threshold": threshold, "limit": limit},
            timeout=300.0,
        )

    # ID: e2f6a8b0-5c7d-4e9f-0a1b-2c3d4e5f6071
    async def coverage_history(self, limit: int = 30) -> dict:
        """GET /v1/coverage/history — recent coverage measurements."""
        return await self._request(
            "GET", "/v1/coverage/history", params={"limit": limit}
        )

    # ID: f3a7b9c1-6d8e-4f0a-1b2c-3d4e5f607182
    async def coverage_methods(self) -> dict:
        """GET /v1/coverage/methods — coverage method comparison descriptor."""
        return await self._request("GET", "/v1/coverage/methods")

    # ID: 04b8c0d2-7e9f-4a1b-2c3d-4e5f60718293
    async def coverage_generate(self, target_file: str, write: bool = False) -> dict:
        """POST /v1/coverage/generate — single-file adaptive test generation."""
        return await self._request(
            "POST",
            "/v1/coverage/generate",
            json={"target_file": target_file, "write": write},
        )

    # ID: 15c9d1e3-8f0a-4b2c-3d4e-5f60718293a4
    async def coverage_generate_batch(
        self, priority: str = "all", write: bool = False
    ) -> dict:
        """POST /v1/coverage/generate:batch — prioritised batch generation."""
        return await self._request(
            "POST",
            "/v1/coverage/generate:batch",
            json={"priority": priority, "write": write},
        )

    # ID: 26dae2f4-9a1b-4c3d-4e5f-60718293a4b5
    async def get_coverage_run(self, run_id: str) -> dict:
        """GET /v1/coverage/runs/{run_id} — fetch a coverage_runs row."""
        return await self._request("GET", f"/v1/coverage/runs/{run_id}")

    # ID: 37ebf3a5-0b2c-4d4e-5f60-718293a4b5c6
    async def poll_coverage_run(
        self, run_id: str, timeout_seconds: float = 600.0
    ) -> dict:
        """Poll a coverage run until terminal. Test generation can be slow."""
        return await self._poll_at_path(
            f"/v1/coverage/runs/{run_id}", timeout_seconds=timeout_seconds
        )

    # ID: 48fc04b6-1c3d-4e5f-6071-8293a4b5c6d7
    async def tests_interactive(self, target_file: str | None = None) -> dict:
        """POST /v1/tests/interactive — sync interactive test generation."""
        return await self._request(
            "POST",
            "/v1/tests/interactive",
            json={"target_file": target_file},
            timeout=600.0,
        )

    # ------------------------------------------------------------------
    # Phase 3 — /refactor (ADR-057 D2)
    # ------------------------------------------------------------------

    # ID: 59ad15c7-2d4e-4f60-7182-93a4b5c6d7e8
    async def refactor_threshold(self) -> dict:
        """GET /v1/refactor/threshold — constitutional modularity threshold."""
        return await self._request("GET", "/v1/refactor/threshold")

    # ID: 6abe26d8-3e5f-4071-8293-a4b5c6d7e8f9
    async def refactor_score(self, file: str) -> dict:
        """GET /v1/refactor/score?file= — per-file modularity score."""
        return await self._request("GET", "/v1/refactor/score", params={"file": file})

    # ID: 7bcf37e9-4f60-4182-93a4-b5c6d7e8f90a
    async def refactor_candidates(
        self,
        min_score: float | None = None,
        limit: int = 50,
    ) -> dict:
        """GET /v1/refactor/candidates — files exceeding modularity threshold."""
        params: dict[str, Any] = {"limit": limit}
        if min_score is not None:
            params["min_score"] = min_score
        return await self._request(
            "GET", "/v1/refactor/candidates", params=params, timeout=300.0
        )

    # ID: 8cd048fa-5071-4293-a4b5-c6d7e8f90a1b
    async def refactor_stats(self) -> dict:
        """GET /v1/refactor/stats — aggregate modularity distribution."""
        return await self._request("GET", "/v1/refactor/stats", timeout=300.0)

    # ID: 9de1590b-6182-4304-b5c6-d7e8f90a1b2c
    async def refactor_autonomous(self, goal: str, write: bool = False) -> dict:
        """POST /v1/refactor/autonomous — trigger A3 autonomous refactor cycle."""
        return await self._request(
            "POST",
            "/v1/refactor/autonomous",
            json={"goal": goal, "write": write},
        )

    # ID: aef26a1c-7293-4415-c6d7-e8f90a1b2c3d
    async def get_refactor_run(self, run_id: str) -> dict:
        """GET /v1/refactor/runs/{run_id} — fetch a refactor_runs row."""
        return await self._request("GET", f"/v1/refactor/runs/{run_id}")

    # ID: bf037b2d-83a4-4526-d7e8-f90a1b2c3d4e
    async def poll_refactor_run(
        self, run_id: str, timeout_seconds: float = 1800.0
    ) -> dict:
        """Poll a refactor run until terminal. A3 loops can take minutes."""
        return await self._poll_at_path(
            f"/v1/refactor/runs/{run_id}", timeout_seconds=timeout_seconds
        )

    # ------------------------------------------------------------------
    # Phase 3 — /status, /decisions, /refusals, /analysis (ADR-057 D3)
    # ------------------------------------------------------------------

    # ID: c0148c3e-94b5-4637-e8f9-0a1b2c3d4e5f
    async def status_db(self) -> dict:
        """GET /v1/status/db — DB connection and schema state."""
        return await self._request("GET", "/v1/status/db")

    # ID: d1259d4f-a5c6-4748-f90a-1b2c3d4e5f60
    async def status_drift(self, scope: str = "all") -> dict:
        """GET /v1/status/drift — consolidated drift snapshot."""
        return await self._request("GET", "/v1/status/drift", params={"scope": scope})

    # ID: e236ae50-b6d7-4859-0a1b-2c3d4e5f6071
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
        return await self._request("GET", "/v1/decisions", params=params)

    # ID: f347bf61-c7e8-495a-1b2c-3d4e5f607182
    async def decisions_patterns(self, days: int = 7) -> dict:
        """GET /v1/decisions/patterns — pattern classification stats."""
        return await self._request(
            "GET", "/v1/decisions/patterns", params={"days": days}
        )

    # ID: 0458c072-d8f9-4a6b-2c3d-4e5f60718293
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
        return await self._request("GET", "/v1/refusals", params=params)

    # ID: 1569d183-e90a-4b7c-3d4e-5f60718293a4
    async def refusals_stats(self, days: int = 7) -> dict:
        """GET /v1/refusals/stats — refusal statistics by type."""
        return await self._request("GET", "/v1/refusals/stats", params={"days": days})

    # ID: 267ae294-f01b-4c8d-4e5f-60718293a4b5
    async def analysis_clusters(self, limit: int = 25) -> dict:
        """GET /v1/analysis/clusters — semantic capability clusters."""
        return await self._request(
            "GET", "/v1/analysis/clusters", params={"limit": limit}
        )

    # ID: 378bf3a5-012c-4d9e-5f60-718293a4b5c6
    async def analysis_duplicates(self, threshold: float = 0.85) -> dict:
        """GET /v1/analysis/duplicates — semantic code duplication candidates."""
        return await self._request(
            "GET",
            "/v1/analysis/duplicates",
            params={"threshold": threshold},
            timeout=300.0,
        )

    # ID: 489c04b6-123d-4e0f-6071-8293a4b5c6d7
    async def analysis_common_knowledge(self, limit: int = 25) -> dict:
        """GET /v1/analysis/common-knowledge — DRY-violation candidates."""
        return await self._request(
            "GET", "/v1/analysis/common-knowledge", params={"limit": limit}
        )

    # ID: 59ad15c7-234e-4f10-7182-93a4b5c6d7e8
    async def analysis_command_tree(self) -> dict:
        """GET /v1/analysis/command-tree — introspected CLI command hierarchy."""
        return await self._request("GET", "/v1/analysis/command-tree")

    # ID: 6abe26d8-345f-4021-8293-a4b5c6d7e8f9
    async def analysis_test_targets(self) -> dict:
        """GET /v1/analysis/test-targets — SIMPLE/COMPLEX test target classification."""
        return await self._request("GET", "/v1/analysis/test-targets")

    # ID: b347cf17-8caa-4c05-9853-4942b3d8c08f
    async def inspect_components(self, filter_type: str | None = None) -> dict:
        """GET /v1/components — V2 component inventory (ADR-057 D5)."""
        params: dict[str, Any] = {}
        if filter_type is not None:
            params["type"] = filter_type
        return await self._request("GET", "/v1/components", params=params)

    # ID: dbf1dc9a-2a32-4319-94d4-d450c9a54836
    async def inspect_search_capabilities(self, q: str, limit: int = 10) -> dict:
        """GET /v1/search/capabilities — semantic capability search (ADR-057 D5)."""
        return await self._request(
            "GET", "/v1/search/capabilities", params={"q": q, "limit": limit}
        )

    # ID: 792970ef-a9d3-493d-9049-55d2cbfcf3b3
    async def inspect_search_commands(self, q: str, limit: int = 25) -> dict:
        """GET /v1/search/commands — fuzzy substring search over the CLI registry (ADR-057 D5)."""
        return await self._request(
            "GET", "/v1/search/commands", params={"q": q, "limit": limit}
        )

    # ------------------------------------------------------------------
    # Phase 3 — /audit/remediations (ADR-057 D4)
    # ------------------------------------------------------------------

    # ID: 7bcf37e9-4561-4132-93a4-b5c6d7e8f90a
    async def audit_remediate(
        self,
        audit_run_id: str,
        mode: str = "safe",
        write: bool = False,
    ) -> dict:
        """POST /v1/audit/remediations — dispatch autonomous audit remediation."""
        return await self._request(
            "POST",
            "/v1/audit/remediations",
            json={
                "audit_run_id": audit_run_id,
                "mode": mode,
                "write": write,
            },
        )

    # ID: 8cd048fa-5672-4243-a4b5-c6d7e8f90a1b
    async def get_audit_remediation_run(self, run_id: str) -> dict:
        """GET /v1/audit/remediations/{run_id} — fetch a remediation_runs row."""
        return await self._request("GET", f"/v1/audit/remediations/{run_id}")

    # ID: 9de1590b-6783-4354-b5c6-d7e8f90a1b2c
    async def poll_audit_remediation_run(
        self, run_id: str, timeout_seconds: float = 1800.0
    ) -> dict:
        """Poll an audit remediation run until terminal."""
        return await self._poll_at_path(
            f"/v1/audit/remediations/{run_id}", timeout_seconds=timeout_seconds
        )

    # ------------------------------------------------------------------
    # Phase 4 — /census (ADR-058 D1)
    # ------------------------------------------------------------------

    # ID: 1a5b8c2d-3e4f-4567-89ab-cdef01234567
    async def census_run(
        self, snapshot: bool = False, requested_by: str = "api"
    ) -> dict:
        """POST /v1/census/runs — dispatch a CIM-0 structural census."""
        return await self._request(
            "POST",
            "/v1/census/runs",
            json={"snapshot": snapshot, "requested_by": requested_by},
        )

    # ID: 2b6c9d3e-4f5a-4678-9abc-def012345678
    async def get_census_run(self, run_id: str) -> dict:
        """GET /v1/census/runs/{run_id} — fetch a census_runs row."""
        return await self._request("GET", f"/v1/census/runs/{run_id}")

    # ID: 3c7d0e4f-5a6b-4789-abcd-ef0123456789
    async def poll_census_run(
        self, run_id: str, timeout_seconds: float = 1800.0
    ) -> dict:
        """Poll a census run until terminal. CIM-0 traversal can be slow."""
        return await self._poll_at_path(
            f"/v1/census/runs/{run_id}", timeout_seconds=timeout_seconds
        )

    # ID: 4d8e1f5a-6b7c-489a-bcde-f01234567890
    async def census_create_baseline(
        self, name: str, snapshot_file: str | None = None
    ) -> dict:
        """POST /v1/census/baselines/{name} — create a named baseline."""
        return await self._request(
            "POST",
            f"/v1/census/baselines/{name}",
            json={"snapshot_file": snapshot_file},
        )

    # ID: 5e9f2a6b-7c8d-490b-cdef-012345678901
    async def census_list_baselines(self) -> dict:
        """GET /v1/census/baselines — list all named baselines."""
        return await self._request("GET", "/v1/census/baselines")

    # ID: 6a0b3c7d-8e9f-401c-def0-123456789012
    async def census_diff(self, baseline: str | None = None) -> dict:
        """GET /v1/census/diff — diff current vs baseline (or previous)."""
        params: dict[str, Any] = {}
        if baseline is not None:
            params["baseline"] = baseline
        return await self._request("GET", "/v1/census/diff", params=params)

    # ------------------------------------------------------------------
    # Phase 4 — /sync (ADR-058 D2)
    # ------------------------------------------------------------------

    # ID: 7b1c4d8e-9f0a-412d-ef01-234567890123
    async def sync_knowledge_graph(
        self,
        write: bool = False,
        target: str | None = None,
        requested_by: str = "api",
    ) -> dict:
        """POST /v1/sync/knowledge-graph — CLI command tree -> PostgreSQL."""
        return await self._request(
            "POST",
            "/v1/sync/knowledge-graph",
            json={"write": write, "target": target, "requested_by": requested_by},
        )

    # ID: 8c2d5e9f-0a1b-423e-f012-345678901234
    async def sync_vectors(
        self,
        write: bool = False,
        target: str | None = None,
        requested_by: str = "api",
    ) -> dict:
        """POST /v1/sync/vectors — constitutional vector sync."""
        return await self._request(
            "POST",
            "/v1/sync/vectors",
            json={"write": write, "target": target, "requested_by": requested_by},
        )

    # ID: 9d3e6f0a-1b2c-434f-0123-456789012345
    async def sync_code_vectors(
        self,
        write: bool = False,
        target: str | None = None,
        requested_by: str = "api",
    ) -> dict:
        """POST /v1/sync/code-vectors — codebase symbol embedding."""
        return await self._request(
            "POST",
            "/v1/sync/code-vectors",
            json={"write": write, "target": target, "requested_by": requested_by},
        )

    # ID: 0e4f7a1b-2c3d-4450-1234-567890123456
    async def sync_dev_sync(
        self,
        write: bool = False,
        target: str | None = None,
        requested_by: str = "api",
    ) -> dict:
        """POST /v1/sync/dev-sync — composite fix + knowledge-graph + vectors."""
        return await self._request(
            "POST",
            "/v1/sync/dev-sync",
            json={"write": write, "target": target, "requested_by": requested_by},
        )

    # ID: 1f5a8b2c-3d4e-4561-2345-678901234567
    async def get_sync_run(self, run_id: str) -> dict:
        """GET /v1/sync/runs/{run_id} — fetch a sync_runs row."""
        return await self._request("GET", f"/v1/sync/runs/{run_id}")

    # ID: 2a6b9c3d-4e5f-4672-3456-789012345678
    async def poll_sync_run(self, run_id: str, timeout_seconds: float = 1800.0) -> dict:
        """Poll a sync run until terminal."""
        return await self._poll_at_path(
            f"/v1/sync/runs/{run_id}", timeout_seconds=timeout_seconds
        )

    # ------------------------------------------------------------------
    # Integrity — /integrity (ADR-055 D6 follow-up — closes #353)
    # ------------------------------------------------------------------

    # ID: 7ba84c02-f8a8-4895-befd-8e43e397cfbb
    async def baseline(self, label: str = "default") -> dict:
        """POST /v1/integrity/baseline — SHA256-fingerprint src/."""
        return await self._request(
            "POST",
            "/v1/integrity/baseline",
            json={"label": label},
        )

    # ID: dc4b010a-8220-42e4-9d11-78613b6a2eb7
    async def verify(self, label: str = "default") -> dict:
        """POST /v1/integrity/verify — diff src/ against a named baseline."""
        return await self._request(
            "POST",
            "/v1/integrity/verify",
            json={"label": label},
        )

    # ------------------------------------------------------------------
    # Phase 4 — /daemon (ADR-058 D3)
    # ------------------------------------------------------------------

    # ID: 3b7c0d4e-5f6a-4783-4567-890123456789
    async def daemon_status(self) -> dict:
        """GET /v1/daemon/status — daemon liveness + per-worker health."""
        return await self._request("GET", "/v1/daemon/status")

    # ID: 4c8d1e5f-6a7b-4894-5678-901234567890
    async def daemon_start(self) -> dict:
        """POST /v1/daemon/start — start core-daemon via systemctl."""
        return await self._request("POST", "/v1/daemon/start", json={})

    # ID: 5d9e2f6a-7b8c-49a5-6789-012345678901
    async def daemon_stop(self) -> dict:
        """POST /v1/daemon/stop — schedule core-daemon stop (fire-and-forget)."""
        return await self._request("POST", "/v1/daemon/stop", json={})
