# tests/cli/resources/demo/conftest.py
"""Shared builders for the ADR-155 Phase 3 CLI-surface tests.

These build fully-populated ``PhaseResult`` records (as the real orchestration
would return) so the D12 renderer and the exit-code mapping can be exercised
without Docker, a database, or a child process.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from cli.logic.demo.models import (
    AssertionResult,
    ChainEvidence,
    ChainScenarioResult,
    FindingIdentity,
    PhaseResult,
    ProposalIdentity,
)


SEED_PATH = "src/body/analyzers/demo_onramp_abcd1234.py"
FINDING_ID = "finding-1111"
PROPOSAL_ID = "proposal-2222"


def _proposal() -> ProposalIdentity:
    return ProposalIdentity(
        proposal_id=PROPOSAL_ID,
        goal="FINDING",
        status="completed",
        overall_risk="safe",
        approval_required=False,
        approval_authority="risk_classification.safe_auto_approval",
        approved_by="autonomous_self_promote",
        finding_ids=[FINDING_ID],
        action_ids=["fix.ids"],
        scope_files=[SEED_PATH],
    )


def _passing_scenario() -> ChainScenarioResult:
    proposal = _proposal()
    return ChainScenarioResult(
        run_id="run-abcd",
        seed_rel_path=SEED_PATH,
        finding=FindingIdentity(
            entry_id=FINDING_ID,
            subject="audit_finding:linkage.assign_ids",
            rule_id="linkage.assign_ids",
            file_path=SEED_PATH,
            status="open",
        ),
        finding_matches_count=1,
        proposal=proposal,
        chain=ChainEvidence(
            proposal=proposal,
            lifecycle_status="completed",
            execution_claimer="proposal-consumer",
            pre_execution_sha="aaaa1111",
            post_execution_sha="bbbb2222",
            files_changed=[SEED_PATH],
            findings_resolved=[FINDING_ID],
        ),
        reaudit_clean=True,
        reaudit_matches_count=0,
        finding_final_status="resolved",
        finding_final_proposal_id=PROPOSAL_ID,
    )


@pytest.fixture
def passing_result() -> PhaseResult:
    return PhaseResult(
        run_id="run-abcd",
        ok=True,
        assertions=[AssertionResult(name="D10.1_infra_healthy", passed=True)],
        assessed_commit="deadbeef",
        state_dir=Path("/state/runs/run-abcd"),
        cleaned_up=True,
        scenario=_passing_scenario(),
    )


@pytest.fixture
def failing_result() -> PhaseResult:
    scenario = _passing_scenario()
    scenario.chain = None
    scenario.reaudit_clean = False
    scenario.reaudit_matches_count = 1
    scenario.error = "execution did not reach completed"
    return PhaseResult(
        run_id="run-fail",
        ok=False,
        assertions=[
            AssertionResult(name="D10.1_infra_healthy", passed=True),
            AssertionResult(
                name="D10.6_execution_reaches_completed",
                passed=False,
                detail="finalizing",
            ),
        ],
        assessed_commit="deadbeef",
        state_dir=Path("/state/runs/run-fail"),
        cleaned_up=False,
        scenario=scenario,
    )
