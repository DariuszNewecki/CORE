# src/api/cli/client.py

"""Thin async HTTP client for the CORE API (ADR-054).

CoreApiClient is a thin facade over twelve per-namespace sub-clients
(issue #360). Each sub-client owns the HTTP endpoint family for one
namespace (audit, fix, quality, coverage, refactor, inspect,
proposals, integration, census, sync, daemon, integrity) and uses
`self._facade._request` and `self._facade._poll_at_path` to share
the connection config and polling helpers that live on the facade.

The facade keeps the original 75 flat methods as delegating shims so
existing CLI call-sites continue to work unchanged. Namespaced access
via attributes (e.g. `client.coverage.coverage_gaps(...)`) is the
preferred form for new callers.

The sub-client attribute for the audit namespace is `audits` (plural)
to avoid collision with the existing `audit()` method.
"""

from __future__ import annotations

import asyncio
from typing import Any

import httpx

from api.cli.audit_client import AuditClient
from api.cli.census_client import CensusClient
from api.cli.coverage_client import CoverageClient
from api.cli.daemon_client import DaemonClient
from api.cli.fix_client import FixClient
from api.cli.inspect_client import InspectClient
from api.cli.integration_client import IntegrationClient
from api.cli.integrity_client import IntegrityClient
from api.cli.lane_client import LaneClient
from api.cli.proposals_client import ProposalsClient
from api.cli.quality_client import QualityClient
from api.cli.refactor_client import RefactorClient
from api.cli.secrets_client import SecretsClient
from api.cli.sync_client import SyncClient


_DEFAULT_BASE_URL = "http://127.0.0.1:8000"
_DEFAULT_TIMEOUT_SECONDS = 30.0
_POLL_INTERVAL_SECONDS = 1.0
_POLL_TERMINAL_STATES = frozenset({"completed", "failed"})


# ID: 03d88f8c-1a13-4901-a03c-52db4b5ee5b2
class CoreApiClient:
    """Async HTTP client targeting the loopback-bound CORE API.

    OSS CORE runs in trusted-localhost mode — no authentication required.
    Internally a facade over namespace sub-clients (see module docstring).
    Existing flat methods are preserved as delegating shims for
    backwards-compatible call sites.
    """

    def __init__(self, base_url: str | None = None) -> None:
        self.base_url = base_url or _DEFAULT_BASE_URL
        self.timeout = _DEFAULT_TIMEOUT_SECONDS
        self.audits = AuditClient(self)
        self.fix = FixClient(self)
        self.quality = QualityClient(self)
        self.coverage = CoverageClient(self)
        self.refactor = RefactorClient(self)
        self.inspect = InspectClient(self)
        self.proposals = ProposalsClient(self)
        self.integration = IntegrationClient(self)
        self.census = CensusClient(self)
        self.sync = SyncClient(self)
        self.daemon = DaemonClient(self)
        self.integrity = IntegrityClient(self)
        self.lane = LaneClient(self)
        self.secrets = SecretsClient(self)

    # ID: 77466c97-58c5-4ad2-8e5a-814396965f73
    async def _request(self, method: str, path: str, **kwargs: Any) -> dict:
        url = f"{self.base_url}{path}"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.request(method, url, **kwargs)
            if response.status_code >= 400:
                try:
                    detail = response.json().get("detail", response.text)
                except Exception:
                    detail = response.text
                raise RuntimeError(f"API error {response.status_code}: {detail}")
            response.raise_for_status()
            return response.json()

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

    # -- /proposals (ProposalsClient) ----------------------------------

    # ID: daf8f641-0358-4298-8465-af1d1c09e221
    async def create_proposal(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/proposals — see ProposalsClient.create_proposal."""
        return await self.proposals.create_proposal(*args, **kwargs)

    # ID: 36434e12-c232-4452-9ff5-c0690263804f
    async def list_proposals(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/proposals — see ProposalsClient.list_proposals."""
        return await self.proposals.list_proposals(*args, **kwargs)

    # ID: 2e321d91-d4e6-45ff-834c-a7394fe47fa0
    async def get_proposal(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/proposals/{id} — see ProposalsClient.get_proposal."""
        return await self.proposals.get_proposal(*args, **kwargs)

    # ID: 4223e0c4-41e1-4105-9b9a-b65d52b616d9
    async def approve_proposal(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/proposals/{id}/approve — see ProposalsClient.approve_proposal."""
        return await self.proposals.approve_proposal(*args, **kwargs)

    # ID: 85d96758-f6f0-4162-a44f-32d7dd65bf5c
    async def reject_proposal(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/proposals/{id}/reject — see ProposalsClient.reject_proposal."""
        return await self.proposals.reject_proposal(*args, **kwargs)

    # ID: f7f70b77-7766-4112-86d5-81d0bf6cd830
    async def execute_proposal(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/proposals/{id}/execute — see ProposalsClient.execute_proposal."""
        return await self.proposals.execute_proposal(*args, **kwargs)

    # -- /integrate, /lint (IntegrationClient) ------------------------

    # ID: 756d1f0f-7315-4fb9-9cd6-4ba14f92dd8a
    async def integrate(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/integrate — see IntegrationClient.integrate."""
        return await self.integration.integrate(*args, **kwargs)

    # ID: 77313481-4787-431c-944f-84a1ab44c594
    async def lint(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/lint — see IntegrationClient.lint."""
        return await self.integration.lint(*args, **kwargs)

    # -- /audit (AuditClient, attr=audits) ----------------------------

    # ID: b67c3e8d-93d5-4307-a347-4a6d50ab768d
    async def audit(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/audit/runs — see AuditClient.audit."""
        return await self.audits.audit(*args, **kwargs)

    # ID: 7bcf37e9-4561-4132-93a4-b5c6d7e8f90a
    async def audit_remediate(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/audit/remediations — see AuditClient.audit_remediate."""
        return await self.audits.audit_remediate(*args, **kwargs)

    # ID: 8cd048fa-5672-4243-a4b5-c6d7e8f90a1b
    async def get_audit_remediation_run(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/audit/remediations/{run_id} — see AuditClient.get_audit_remediation_run."""
        return await self.audits.get_audit_remediation_run(*args, **kwargs)

    # ID: 9de1590b-6783-4354-b5c6-d7e8f90a1b2c
    async def poll_audit_remediation_run(self, *args: Any, **kwargs: Any) -> dict:
        """Poll an audit remediation run — see AuditClient.poll_audit_remediation_run."""
        return await self.audits.poll_audit_remediation_run(*args, **kwargs)

    # -- /fix, /actions (FixClient) ------------------------------------

    # ID: d4b48241-75a5-4e53-bc46-e80b0c8e36e5
    async def list_fix_commands(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/fix/commands — see FixClient.list_fix_commands."""
        return await self.fix.list_fix_commands(*args, **kwargs)

    # ID: ae1230d2-9f37-4e2f-9025-8b409a73ee32
    async def list_actions(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/actions — see FixClient.list_actions."""
        return await self.fix.list_actions(*args, **kwargs)

    # ID: cca11da8-9878-4c7e-9149-1972446a9d81
    async def run_fix(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/fix/run/{fix_id} — see FixClient.run_fix."""
        return await self.fix.run_fix(*args, **kwargs)

    # ID: b54035a3-7c41-452c-bd1d-2cb7c92e9214
    async def fix_all(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/fix/all — see FixClient.fix_all."""
        return await self.fix.fix_all(*args, **kwargs)

    # ID: 22c3d638-ed25-40a0-8aec-52c569e5e776
    async def fix_modularity(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/fix/modularity — see FixClient.fix_modularity."""
        return await self.fix.fix_modularity(*args, **kwargs)

    # ID: 4dcdaddd-1cd1-4561-9d1b-6e76637bada6
    async def fix_ir(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/fix/ir — see FixClient.fix_ir."""
        return await self.fix.fix_ir(*args, **kwargs)

    # ID: 42e18693-ee64-42e7-bf48-dd855f2f3463
    async def get_fix_run(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/fix/runs/{run_id} — see FixClient.get_fix_run."""
        return await self.fix.get_fix_run(*args, **kwargs)

    # -- /quality (QualityClient) --------------------------------------

    # ID: 7863008f-424f-4e14-b461-eeb8b969291e
    async def quality_imports(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/quality/imports — see QualityClient.quality_imports."""
        return await self.quality.quality_imports(*args, **kwargs)

    # ID: e2563ebe-4fc9-45aa-91bc-a362ce637e95
    async def quality_body_ui(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/quality/body-ui — see QualityClient.quality_body_ui."""
        return await self.quality.quality_body_ui(*args, **kwargs)

    # ID: 4e6f1a2b-8c3d-47e9-a5b1-2d3f4c5a6b7d
    async def quality_policy_coverage(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/quality/policy-coverage — see QualityClient.quality_policy_coverage."""
        return await self.quality.quality_policy_coverage(*args, **kwargs)

    # ID: 0774cb34-3305-4fee-89b3-8f33bec667a9
    async def quality_lint(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/quality/lint — see QualityClient.quality_lint."""
        return await self.quality.quality_lint(*args, **kwargs)

    # ID: 1824000e-1ced-488b-a083-56e2e25529ec
    async def quality_tests(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/quality/tests — see QualityClient.quality_tests."""
        return await self.quality.quality_tests(*args, **kwargs)

    # ID: efdd8365-2deb-4093-b03e-fb5aa303647f
    async def quality_system(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/quality/system — see QualityClient.quality_system."""
        return await self.quality.quality_system(*args, **kwargs)

    # ID: d41045dd-54cb-4b72-897b-55ed29d3f305
    async def quality_gates(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/quality/gates — see QualityClient.quality_gates."""
        return await self.quality.quality_gates(*args, **kwargs)

    # -- /coverage, /tests/interactive (CoverageClient) ----------------

    # ID: a8b2c4d6-1e3f-4a5b-6c7d-8e9f0a1b2c3d
    async def coverage_check(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/coverage/check — see CoverageClient.coverage_check."""
        return await self.coverage.coverage_check(*args, **kwargs)

    # ID: b9c3d5e7-2f4a-4b6c-7d8e-9f0a1b2c3d4e
    async def coverage_report(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/coverage/report — see CoverageClient.coverage_report."""
        return await self.coverage.coverage_report(*args, **kwargs)

    # ID: c0d4e6f8-3a5b-4c7d-8e9f-0a1b2c3d4e5f
    async def coverage_targets(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/coverage/targets — see CoverageClient.coverage_targets."""
        return await self.coverage.coverage_targets(*args, **kwargs)

    # ID: d1e5f7a9-4b6c-4d8e-9f0a-1b2c3d4e5f60
    async def coverage_gaps(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/coverage/gaps — see CoverageClient.coverage_gaps."""
        return await self.coverage.coverage_gaps(*args, **kwargs)

    # ID: e2f6a8b0-5c7d-4e9f-0a1b-2c3d4e5f6071
    async def coverage_history(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/coverage/history — see CoverageClient.coverage_history."""
        return await self.coverage.coverage_history(*args, **kwargs)

    # ID: f3a7b9c1-6d8e-4f0a-1b2c-3d4e5f607182
    async def coverage_methods(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/coverage/methods — see CoverageClient.coverage_methods."""
        return await self.coverage.coverage_methods(*args, **kwargs)

    # ID: 04b8c0d2-7e9f-4a1b-2c3d-4e5f60718293
    async def coverage_generate(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/coverage/generate — see CoverageClient.coverage_generate."""
        return await self.coverage.coverage_generate(*args, **kwargs)

    # ID: 15c9d1e3-8f0a-4b2c-3d4e-5f60718293a4
    async def coverage_generate_batch(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/coverage/generate:batch — see CoverageClient.coverage_generate_batch."""
        return await self.coverage.coverage_generate_batch(*args, **kwargs)

    # ID: 26dae2f4-9a1b-4c3d-4e5f-60718293a4b5
    async def get_coverage_run(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/coverage/runs/{run_id} — see CoverageClient.get_coverage_run."""
        return await self.coverage.get_coverage_run(*args, **kwargs)

    # ID: 37ebf3a5-0b2c-4d4e-5f60-718293a4b5c6
    async def poll_coverage_run(self, *args: Any, **kwargs: Any) -> dict:
        """Poll a coverage run — see CoverageClient.poll_coverage_run."""
        return await self.coverage.poll_coverage_run(*args, **kwargs)

    # ID: 48fc04b6-1c3d-4e5f-6071-8293a4b5c6d7
    async def tests_interactive(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/tests/interactive — see CoverageClient.tests_interactive."""
        return await self.coverage.tests_interactive(*args, **kwargs)

    # -- /refactor (RefactorClient) ------------------------------------

    # ID: 59ad15c7-2d4e-4f60-7182-93a4b5c6d7e8
    async def refactor_threshold(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/refactor/threshold — see RefactorClient.refactor_threshold."""
        return await self.refactor.refactor_threshold(*args, **kwargs)

    # ID: 6abe26d8-3e5f-4071-8293-a4b5c6d7e8f9
    async def refactor_score(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/refactor/score — see RefactorClient.refactor_score."""
        return await self.refactor.refactor_score(*args, **kwargs)

    # ID: 7bcf37e9-4f60-4182-93a4-b5c6d7e8f90a
    async def refactor_candidates(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/refactor/candidates — see RefactorClient.refactor_candidates."""
        return await self.refactor.refactor_candidates(*args, **kwargs)

    # ID: 8cd048fa-5071-4293-a4b5-c6d7e8f90a1b
    async def refactor_stats(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/refactor/stats — see RefactorClient.refactor_stats."""
        return await self.refactor.refactor_stats(*args, **kwargs)

    # ID: 9de1590b-6182-4304-b5c6-d7e8f90a1b2c
    async def refactor_autonomous(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/refactor/autonomous — see RefactorClient.refactor_autonomous."""
        return await self.refactor.refactor_autonomous(*args, **kwargs)

    # ID: aef26a1c-7293-4415-c6d7-e8f90a1b2c3d
    async def get_refactor_run(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/refactor/runs/{run_id} — see RefactorClient.get_refactor_run."""
        return await self.refactor.get_refactor_run(*args, **kwargs)

    # ID: bf037b2d-83a4-4526-d7e8-f90a1b2c3d4e
    async def poll_refactor_run(self, *args: Any, **kwargs: Any) -> dict:
        """Poll a refactor run — see RefactorClient.poll_refactor_run."""
        return await self.refactor.poll_refactor_run(*args, **kwargs)

    # -- /status, /decisions, /refusals, /analysis, /components, /search (InspectClient) --

    # ID: c0148c3e-94b5-4637-e8f9-0a1b2c3d4e5f
    async def status_db(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/status/db — see InspectClient.status_db."""
        return await self.inspect.status_db(*args, **kwargs)

    # ID: d1259d4f-a5c6-4748-f90a-1b2c3d4e5f60
    async def status_drift(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/status/drift — see InspectClient.status_drift."""
        return await self.inspect.status_drift(*args, **kwargs)

    # ID: e236ae50-b6d7-4859-0a1b-2c3d4e5f6071
    async def decisions_list(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/decisions — see InspectClient.decisions_list."""
        return await self.inspect.decisions_list(*args, **kwargs)

    # ID: f347bf61-c7e8-495a-1b2c-3d4e5f607182
    async def decisions_patterns(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/decisions/patterns — see InspectClient.decisions_patterns."""
        return await self.inspect.decisions_patterns(*args, **kwargs)

    # ID: 0458c072-d8f9-4a6b-2c3d-4e5f60718293
    async def refusals_list(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/refusals — see InspectClient.refusals_list."""
        return await self.inspect.refusals_list(*args, **kwargs)

    # ID: 1569d183-e90a-4b7c-3d4e-5f60718293a4
    async def refusals_stats(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/refusals/stats — see InspectClient.refusals_stats."""
        return await self.inspect.refusals_stats(*args, **kwargs)

    # ID: 267ae294-f01b-4c8d-4e5f-60718293a4b5
    async def analysis_clusters(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/analysis/clusters — see InspectClient.analysis_clusters."""
        return await self.inspect.analysis_clusters(*args, **kwargs)

    # ID: 378bf3a5-012c-4d9e-5f60-718293a4b5c6
    async def analysis_duplicates(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/analysis/duplicates — see InspectClient.analysis_duplicates."""
        return await self.inspect.analysis_duplicates(*args, **kwargs)

    # ID: 489c04b6-123d-4e0f-6071-8293a4b5c6d7
    async def analysis_common_knowledge(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/analysis/common-knowledge — see InspectClient.analysis_common_knowledge."""
        return await self.inspect.analysis_common_knowledge(*args, **kwargs)

    # ID: 59ad15c7-234e-4f10-7182-93a4b5c6d7e8
    async def analysis_command_tree(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/analysis/command-tree — see InspectClient.analysis_command_tree."""
        return await self.inspect.analysis_command_tree(*args, **kwargs)

    # ID: 6abe26d8-345f-4021-8293-a4b5c6d7e8f9
    async def analysis_test_targets(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/analysis/test-targets — see InspectClient.analysis_test_targets."""
        return await self.inspect.analysis_test_targets(*args, **kwargs)

    # ID: b347cf17-8caa-4c05-9853-4942b3d8c08f
    async def inspect_components(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/components — see InspectClient.inspect_components."""
        return await self.inspect.inspect_components(*args, **kwargs)

    # ID: dbf1dc9a-2a32-4319-94d4-d450c9a54836
    async def inspect_search_capabilities(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/search/capabilities — see InspectClient.inspect_search_capabilities."""
        return await self.inspect.inspect_search_capabilities(*args, **kwargs)

    # ID: 792970ef-a9d3-493d-9049-55d2cbfcf3b3
    async def inspect_search_commands(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/search/commands — see InspectClient.inspect_search_commands."""
        return await self.inspect.inspect_search_commands(*args, **kwargs)

    # -- /census (CensusClient) ----------------------------------------

    # ID: 1a5b8c2d-3e4f-4567-89ab-cdef01234567
    async def census_run(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/census/runs — see CensusClient.census_run."""
        return await self.census.census_run(*args, **kwargs)

    # ID: 2b6c9d3e-4f5a-4678-9abc-def012345678
    async def get_census_run(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/census/runs/{run_id} — see CensusClient.get_census_run."""
        return await self.census.get_census_run(*args, **kwargs)

    # ID: 3c7d0e4f-5a6b-4789-abcd-ef0123456789
    async def poll_census_run(self, *args: Any, **kwargs: Any) -> dict:
        """Poll a census run — see CensusClient.poll_census_run."""
        return await self.census.poll_census_run(*args, **kwargs)

    # ID: 4d8e1f5a-6b7c-489a-bcde-f01234567890
    async def census_create_baseline(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/census/baselines/{name} — see CensusClient.census_create_baseline."""
        return await self.census.census_create_baseline(*args, **kwargs)

    # ID: 5e9f2a6b-7c8d-490b-cdef-012345678901
    async def census_list_baselines(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/census/baselines — see CensusClient.census_list_baselines."""
        return await self.census.census_list_baselines(*args, **kwargs)

    # ID: 6a0b3c7d-8e9f-401c-def0-123456789012
    async def census_diff(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/census/diff — see CensusClient.census_diff."""
        return await self.census.census_diff(*args, **kwargs)

    # -- /sync (SyncClient) --------------------------------------------

    # ID: 7b1c4d8e-9f0a-412d-ef01-234567890123
    async def sync_knowledge_graph(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/sync/knowledge-graph — see SyncClient.sync_knowledge_graph."""
        return await self.sync.sync_knowledge_graph(*args, **kwargs)

    # ID: 8c2d5e9f-0a1b-423e-f012-345678901234
    async def sync_vectors(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/sync/vectors — see SyncClient.sync_vectors."""
        return await self.sync.sync_vectors(*args, **kwargs)

    # ID: 9d3e6f0a-1b2c-434f-0123-456789012345
    async def sync_code_vectors(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/sync/code-vectors — see SyncClient.sync_code_vectors."""
        return await self.sync.sync_code_vectors(*args, **kwargs)

    # ID: 0e4f7a1b-2c3d-4450-1234-567890123456
    async def sync_dev_sync(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/sync/dev-sync — see SyncClient.sync_dev_sync."""
        return await self.sync.sync_dev_sync(*args, **kwargs)

    # ID: 1f5a8b2c-3d4e-4561-2345-678901234567
    async def get_sync_run(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/sync/runs/{run_id} — see SyncClient.get_sync_run."""
        return await self.sync.get_sync_run(*args, **kwargs)

    # ID: 2a6b9c3d-4e5f-4672-3456-789012345678
    async def poll_sync_run(self, *args: Any, **kwargs: Any) -> dict:
        """Poll a sync run — see SyncClient.poll_sync_run."""
        return await self.sync.poll_sync_run(*args, **kwargs)

    # -- /integrity (IntegrityClient) ----------------------------------

    # ID: 7ba84c02-f8a8-4895-befd-8e43e397cfbb
    async def baseline(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/integrity/baseline — see IntegrityClient.baseline."""
        return await self.integrity.baseline(*args, **kwargs)

    # ID: dc4b010a-8220-42e4-9d11-78613b6a2eb7
    async def verify(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/integrity/verify — see IntegrityClient.verify."""
        return await self.integrity.verify(*args, **kwargs)

    # -- /daemon (DaemonClient) ----------------------------------------

    # ID: 3b7c0d4e-5f6a-4783-4567-890123456789
    async def daemon_status(self, *args: Any, **kwargs: Any) -> dict:
        """GET /v1/daemon/status — see DaemonClient.daemon_status."""
        return await self.daemon.daemon_status(*args, **kwargs)

    # ID: 4c8d1e5f-6a7b-4894-5678-901234567890
    async def daemon_start(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/daemon/start — see DaemonClient.daemon_start."""
        return await self.daemon.daemon_start(*args, **kwargs)

    # ID: 5d9e2f6a-7b8c-49a5-6789-012345678901
    async def daemon_stop(self, *args: Any, **kwargs: Any) -> dict:
        """POST /v1/daemon/stop — see DaemonClient.daemon_stop."""
        return await self.daemon.daemon_stop(*args, **kwargs)
