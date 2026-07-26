# tests/cli/logic/demo/test_scenario_runner_resolution.py
"""Unit tests for `scenario_runner._resolve_finding` / `_resolve_proposal`
adversarial paths (ADR-155 Phase1-Map U08/U09/U10).

D8 requires an *exact* single-match resolution for both the seeded finding
and its linked proposal — never "latest", never a silently-picked-first
result. `_resolve_finding` already returns `(None, match_count)` for zero OR
multiple matches (scenario_runner.py ~line 154); `_resolve_proposal` already
fails closed on a missing entry, a missing `proposal_id`, an unresolvable
proposal, or a broken reverse link (~line 184-200). Both were previously
covered only indirectly:

- `_resolve_finding`'s multi-match branch had no test at all.
- `_resolve_proposal`'s reverse-link check had a test only at the
  assertion-evaluator layer (`test_consequence_chain_assertions.py::
  test_negative_claim_finding_and_proposal_not_linked_both_directions`),
  which fabricates a `ChainScenarioResult` directly rather than calling
  `_resolve_proposal` itself.

These tests call both functions directly, with `BlackboardQueryService` and
`ProposalRepository` faked at the method level — the same style used by
`tests/body/services/blackboard_service/test_blackboard_query_service_
fetch_entry_by_id.py` and `tests/will/autonomy/test_proposal_executor_stop_
on_failure.py`. No DB, no Docker.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, patch

from body.services.blackboard_service.blackboard_query_service import (
    BlackboardQueryService,
)
from body.services.service_registry import ServiceRegistry
from cli.logic.demo.scenario_runner import _resolve_finding, _resolve_proposal
from shared.lifecycles.proposal import ProposalStatus
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    RiskAssessment,
)


_SEED_REL_PATH = "src/body/analyzers/demo_onramp_abc12345.py"
_FINDING_ENTRY_ID = "finding-entry-1"
_PROPOSAL_ID = "proposal-1"


def _finding_row(entry_id: str = _FINDING_ENTRY_ID) -> dict[str, Any]:
    return {
        "id": entry_id,
        "subject": f"python::linkage.assign_ids::{_SEED_REL_PATH}",
        "payload": {"rule": "linkage.assign_ids", "file_path": _SEED_REL_PATH},
    }


@asynccontextmanager
async def _session_ctx(session: AsyncMock):
    yield session


def _patched_session():
    """A session whose ``.execute()`` is never expected to be reached in
    these tests — `ProposalRepository.get` is patched directly instead, so
    this only satisfies `service_registry.session()`'s context-manager
    contract."""
    session = AsyncMock()
    return patch.object(ServiceRegistry, "session", return_value=_session_ctx(session))


def _linked_proposal(
    *, finding_ids: list[str], status: ProposalStatus = ProposalStatus.APPROVED
) -> Proposal:
    return Proposal(
        proposal_id=_PROPOSAL_ID,
        goal="Autonomous remediation: fix.ids",
        actions=[ProposalAction(action_id="fix.ids", order=0)],
        scope=ProposalScope(files=[_SEED_REL_PATH]),
        risk=RiskAssessment(overall_risk="safe"),
        status=status,
        constitutional_constraints={"finding_ids": finding_ids},
        approval_required=False,
        approved_by="autonomous_self_promote",
        approval_authority="risk_classification.safe_auto_approval",
    )


# ── _resolve_finding ───────────────────────────────────────────────────────


async def test_resolve_finding_zero_matches_returns_none_and_count() -> None:
    with patch.object(
        BlackboardQueryService,
        "fetch_open_findings_by_patterns",
        AsyncMock(return_value=[]),
    ):
        finding, count = await _resolve_finding(_SEED_REL_PATH)

    assert finding is None
    assert count == 0


async def test_resolve_finding_exactly_one_match_returns_identity() -> None:
    with patch.object(
        BlackboardQueryService,
        "fetch_open_findings_by_patterns",
        AsyncMock(return_value=[_finding_row()]),
    ):
        finding, count = await _resolve_finding(_SEED_REL_PATH)

    assert count == 1
    assert finding is not None
    assert finding.entry_id == _FINDING_ENTRY_ID
    assert finding.rule_id == "linkage.assign_ids"
    assert finding.file_path == _SEED_REL_PATH
    assert finding.status == "open"


async def test_resolve_finding_multiple_matches_fails_closed_not_picked_first() -> None:
    """The adversarial case (U08/U09/U10): duplicate/stale rows matching the
    same exact subject must fail closed with the real count, never silently
    resolve to the first row."""
    rows = [_finding_row("entry-a"), _finding_row("entry-b")]
    with patch.object(
        BlackboardQueryService,
        "fetch_open_findings_by_patterns",
        AsyncMock(return_value=rows),
    ):
        finding, count = await _resolve_finding(_SEED_REL_PATH)

    assert finding is None
    assert count == 2


# ── _resolve_proposal ───────────────────────────────────────────────────────


async def test_resolve_proposal_finding_entry_missing_returns_none() -> None:
    with patch.object(
        BlackboardQueryService, "fetch_entry_by_id", AsyncMock(return_value=None)
    ):
        proposal = await _resolve_proposal(_FINDING_ENTRY_ID)

    assert proposal is None


async def test_resolve_proposal_id_absent_from_payload_returns_none() -> None:
    entry = {"id": _FINDING_ENTRY_ID, "payload": {}}
    with patch.object(
        BlackboardQueryService, "fetch_entry_by_id", AsyncMock(return_value=entry)
    ):
        proposal = await _resolve_proposal(_FINDING_ENTRY_ID)

    assert proposal is None


async def test_resolve_proposal_not_found_in_repository_returns_none() -> None:
    entry = {"id": _FINDING_ENTRY_ID, "payload": {"proposal_id": _PROPOSAL_ID}}
    session_patcher = _patched_session()
    with (
        patch.object(
            BlackboardQueryService, "fetch_entry_by_id", AsyncMock(return_value=entry)
        ),
        session_patcher,
        patch(
            "will.autonomy.proposal_repository.ProposalRepository.get",
            AsyncMock(return_value=None),
        ),
    ):
        proposal = await _resolve_proposal(_FINDING_ENTRY_ID)

    assert proposal is None


async def test_resolve_proposal_reverse_link_broken_returns_none() -> None:
    """Live, function-level version of ``test_negative_claim_finding_and_
    proposal_not_linked_both_directions`` (assertion layer): the proposal
    resolves, but its own ``constitutional_constraints.finding_ids`` does not
    contain the finding that led to it."""
    entry = {"id": _FINDING_ENTRY_ID, "payload": {"proposal_id": _PROPOSAL_ID}}
    domain_proposal = _linked_proposal(finding_ids=["some-other-finding-id"])
    session_patcher = _patched_session()
    with (
        patch.object(
            BlackboardQueryService, "fetch_entry_by_id", AsyncMock(return_value=entry)
        ),
        session_patcher,
        patch(
            "will.autonomy.proposal_repository.ProposalRepository.get",
            AsyncMock(return_value=domain_proposal),
        ),
    ):
        proposal = await _resolve_proposal(_FINDING_ENTRY_ID)

    assert proposal is None


async def test_resolve_proposal_bidirectionally_linked_returns_identity() -> None:
    """Positive case: forward (finding -> proposal_id) and reverse
    (proposal.constitutional_constraints.finding_ids -> finding) both hold."""
    entry = {"id": _FINDING_ENTRY_ID, "payload": {"proposal_id": _PROPOSAL_ID}}
    domain_proposal = _linked_proposal(finding_ids=[_FINDING_ENTRY_ID])
    session_patcher = _patched_session()
    with (
        patch.object(
            BlackboardQueryService, "fetch_entry_by_id", AsyncMock(return_value=entry)
        ),
        session_patcher,
        patch(
            "will.autonomy.proposal_repository.ProposalRepository.get",
            AsyncMock(return_value=domain_proposal),
        ),
    ):
        proposal = await _resolve_proposal(_FINDING_ENTRY_ID)

    assert proposal is not None
    assert proposal.proposal_id == _PROPOSAL_ID
    assert proposal.finding_ids == [_FINDING_ENTRY_ID]
    assert proposal.action_ids == ["fix.ids"]
    assert proposal.scope_files == [_SEED_REL_PATH]
    assert proposal.overall_risk == "safe"
    assert proposal.approval_authority == "risk_classification.safe_auto_approval"
    assert proposal.approved_by == "autonomous_self_promote"
