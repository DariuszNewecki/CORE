# src/will/workers/violation_remediator_proposal.py
"""
Proposal creation, active-proposal dedup index, and circuit-breaker
gate for ViolationRemediatorWorker.

Collaborator module. Owns three operations that ViolationRemediatorWorker
calls from its run loop:

- create_proposal: build a Proposal from a (ref_id, ref_kind, findings) group,
  validate it, and submit it through the Body-owned
  ``submit_mapped_proposal`` so that proposal persistence, the deferral of
  every source finding to it, and the safe auto-approval transition
  (ProposalStateManager.approve, when risk classification says safe) commit
  or roll back as ONE transaction (#886; ADR-154 D3b applied to this lane).
  Safe proposals land in APPROVED status so the consumer worker can pick
  them up without a separate human approval step (ADR-035 D1; per-finding
  scope keyed by (action_id, file_path) for atomic actions, or by flow_id
  alone for flows).
- get_active_proposal_id_by_action_file: load all proposals in active states
  ({DRAFT, PENDING, APPROVED, EXECUTING}) and return a
  (ref_id, file_path) → proposal_id map keyed for the dedup-subsume check
  (ADR-035 D2). Earliest by Proposal.created_at wins — the original anchor
  whose existence caused subsequent dedup-subsume decisions. The dedup-
  subsume path records the subsuming proposal_id on the resolved finding's
  payload as the audit linkage (URS Q1.F / ADR-015 D4).
- check_circuit_breaker: opens a short-lived session and returns the
  ADR-038 consecutive-identical-failure streak count for a
  (ref_id, file_path) before the next proposal is minted. Fail-soft on
  DB error: returns (0, None, None, None) so the breaker degrades
  toward retry rather than silent rejection on transient infra.

Implements:
  ADR-035 — per-finding proposal scoping (one proposal per (action, file))
  ADR-010 — Finding→Proposal linkage on the happy path
  ADR-038 — circuit-breaker context (this module produces the proposal that
            the breaker counts failures on; the trip itself lives in
            circuit_breaker.py)

Dependencies are acquired lazily inside each function via the body service
registry — same pattern as proposal_consumer_revival.mark_proposal_failed,
which is the precedent for proposal-row mutations from a will collaborator
module. No file writes, no LLM calls. No Worker reference required —
nothing in this module posts to the blackboard. Finding deferral is NOT
performed here (nor anywhere else in this lane's collaborators): it is the
Body-owned submission service's half of the D3b transaction, and the
approval transition it needs is handed to it as a closure over the
sanctioned ProposalStateManager gate — never a bypass around it.

LAYER: will/workers — internal collaborator of ViolationRemediatorWorker.
"""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING, Any

from shared.logger import getLogger
from will.autonomy.circuit_breaker import recent_consecutive_identical_count
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)
from will.autonomy.safe_auto_approval_envelope import SafeAutoApprovalDeniedError


if TYPE_CHECKING:
    from body.services.proposal_submission_service import MappedSubmissionResult


logger = getLogger(__name__)


_ACTIVE_STATUSES: frozenset[ProposalStatus] = frozenset(
    {
        ProposalStatus.DRAFT,
        ProposalStatus.PENDING,
        ProposalStatus.APPROVED,
        ProposalStatus.EXECUTING,
    }
)


def _entry_id(finding: dict[str, Any]) -> str:
    """Extract the blackboard-entry id from a finding dict.

    Findings arriving from BlackboardService carry either 'id' or 'entry_id'
    depending on the serialization path; both are accepted. Raises
    ValueError if neither is present.
    """
    value = finding.get("id") or finding.get("entry_id")
    if value is None:
        raise ValueError(f"Finding has neither 'id' nor 'entry_id': {finding!r}")
    return str(value)


# ID: f922189d-4c9d-478b-ab6f-6bf179221773
async def create_proposal(
    ref_id: str,
    ref_kind: str,
    findings: list[dict[str, Any]],
    *,
    claimed_by: uuid.UUID,
) -> MappedSubmissionResult | None:
    """Create, persist and link a Proposal for the given remediation reference.

    ref_kind selects the ProposalAction shape: "action" produces
    ProposalAction(action_id=ref_id, ...) and "flow" produces
    ProposalAction(flow_id=ref_id, ...). The two are mutually exclusive
    per ProposalAction.__post_init__.

    One transaction (#886, ADR-154 D3b): the proposal row, the transition
    of every finding in *findings* from ``claimed`` (by *claimed_by* — the
    worker that claimed them) to ``deferred_to_proposal`` carrying the new
    proposal_id, and — for safe proposals (approval_required=False) — the
    auto-approval through ProposalStateManager so the row carries
    approval_authority (URS NFR.5; ADR-015 D6) all commit together, or none
    of them do. Proposals requiring human approval, and safe proposals the
    safe auto-approval envelope denies (#853 ruling 6), commit unapproved in
    DRAFT with their findings deferred.

    Returns the committed submission (proposal_id, deferred_count,
    auto_approved) on success; None on validation failure, on any finding
    no longer being this worker's live claim at submission time (nothing
    persisted — the caller releases what it still holds), or on any other
    persistence/approval failure (also nothing persisted).
    """
    from body.services.proposal_submission_service import (
        ProposalSubmissionError,
        submit_mapped_proposal,
    )
    from shared.infrastructure.database.models.autonomous_proposals import (
        AutonomousProposal,
    )
    from will.autonomy.proposal_mapper import ProposalMapper
    from will.autonomy.proposal_state_manager import ProposalStateManager

    affected_files: list[str] = sorted(
        {
            f["payload"].get("file_path", "")
            for f in findings
            if f["payload"].get("file_path")
        }
    )

    rules = sorted(
        {
            f["payload"].get("check_id") or f["payload"].get("rule", "unknown")
            for f in findings
        }
    )

    # finding_ids is the exact set submit_mapped_proposal defers in the same
    # transaction that persists this row, making the proposal→finding read
    # path symmetric with the finding→proposal write path. Consumed by
    # ProposalExecutor when emitting consequence-log entries
    # (proposal_executor.py:265-266). ADR-015 D7: forward-only — historical
    # proposals predating this field are not backfilled.
    finding_ids = [_entry_id(f) for f in findings]

    # ADR-032+: omit file_path from parameters when the ref is a flow.
    # Flows are codebase-wide operations; per-file file_path is a category
    # mismatch. ADR-033's parameter-routing filter discards it at runtime,
    # but persisting meaningless data here is confusing. Atomic actions
    # keep file_path because ADR-035 makes (action_id, file_path) the
    # proposal scope unit.
    if affected_files:
        proposal_actions = [
            ProposalAction(
                action_id=ref_id if ref_kind == "action" else None,
                flow_id=ref_id if ref_kind == "flow" else None,
                parameters=(
                    {"write": True, "file_path": file_path}
                    if ref_kind == "action"
                    else {"write": True}
                ),
                order=order,
            )
            for order, file_path in enumerate(affected_files)
        ]
    else:
        proposal_actions = [
            ProposalAction(
                action_id=ref_id if ref_kind == "action" else None,
                flow_id=ref_id if ref_kind == "flow" else None,
                parameters=(
                    {"write": True, "file_path": None}
                    if ref_kind == "action"
                    else {"write": True}
                ),
                order=0,
            )
        ]

    proposal = Proposal(
        goal=(
            f"Autonomous remediation: {ref_id} "
            f"({len(findings)} violation(s) — rules: {', '.join(rules)})"
        ),
        actions=proposal_actions,
        scope=ProposalScope(files=affected_files),
        created_by="violation_remediator_worker",
        constitutional_constraints={
            "source": "blackboard_findings",
            "rules": rules,
            "affected_files_count": len(affected_files),
            "finding_ids": finding_ids,
        },
    )

    proposal.compute_risk()

    is_valid, errors = proposal.validate()
    if not is_valid:
        logger.warning(
            "ViolationRemediatorWorker: proposal for '%s' failed validation: %s",
            ref_id,
            errors,
        )
        return None

    async def _approve_in_transaction(session: Any, proposal_id: str) -> bool:
        """Safe auto-approval step, run by the Body service inside its
        transaction (ApprovalStep contract: no commit/rollback here).

        ProposalStateManager.approve() is caller-transaction-scoped by
        design — it never commits — which is exactly what lets the
        sanctioned gate (envelope validation included) sit inside the
        D3b transaction without a bypass.
        """
        try:
            await ProposalStateManager(session).approve(
                proposal_id,
                approved_by="autonomous_self_promote",
                approval_authority="risk_classification.safe_auto_approval",
            )
        except SafeAutoApprovalDeniedError as denial:
            # #853 governor ruling 6: not eligible for safe auto-approval
            # is NOT a persistence failure. approve() validated the
            # envelope BEFORE its UPDATE, so the row is untouched — return
            # False and let the transaction commit the proposal in DRAFT
            # (findings deferred) for principal.governor review.
            logger.warning(
                "ViolationRemediatorWorker: proposal for '%s' is not "
                "eligible for safe auto-approval (%s) — committing in "
                "DRAFT for governor review.",
                ref_id,
                denial,
            )
            return False
        logger.info(
            "ViolationRemediatorWorker: proposal for '%s' auto-approved "
            "(risk=%s, approval_required=False)",
            ref_id,
            proposal.risk.overall_risk if proposal.risk else "unknown",
        )
        return True

    if proposal.approval_required:
        logger.info(
            "ViolationRemediatorWorker: proposal for '%s' requires human "
            "approval (risk=%s) — creating in DRAFT",
            ref_id,
            proposal.risk.overall_risk if proposal.risk else "unknown",
        )

    # Will owns constructing/mapping the governed proposal representation;
    # the Body-owned service only ever receives the persistence model
    # (architecture.layers.no_body_to_will — same split as lane_service).
    proposal_model = ProposalMapper.to_db_model(proposal, AutonomousProposal)

    try:
        return await submit_mapped_proposal(
            proposal_model,
            finding_ids=finding_ids,
            expected_worker_uuid=claimed_by,
            approval_step=(
                None if proposal.approval_required else _approve_in_transaction
            ),
        )
    except ProposalSubmissionError as stale:
        logger.warning(
            "ViolationRemediatorWorker: proposal for '%s' not created — %s",
            ref_id,
            stale,
        )
        return None
    except Exception as e:
        logger.error(
            "ViolationRemediatorWorker: failed to persist proposal for '%s' "
            "(nothing committed — proposal, deferrals and approval rolled "
            "back together): %s",
            ref_id,
            e,
        )
        return None


# ID: 18141610-fad9-423f-9b8f-cc81c6028f40
async def get_active_proposal_id_by_action_file() -> dict[tuple[str, str | None], str]:
    """Return (ref_id, file_path) → proposal_id for active proposals — ADR-035 D2.

    Per-finding scoping (ADR-035 D1) makes the dedup unit (ref_id,
    file_path), not ref_id alone. ref_id is action.action_id for atomic-
    action proposals or action.flow_id for flow-based proposals.
    file_path lives on action.parameters. The dedup-subsume path needs
    the proposal_id (not just the ref_id) to record the linkage in the
    subsumed finding's payload — URS Q1.F / ADR-015 D4.

    Historical batch proposals (pre-ADR-035) with multiple ProposalActions
    across different file_paths are handled correctly: each action
    contributes its own (ref_id, file_path) entry.

    When multiple active proposals share a (ref_id, file_path), the
    earliest by Proposal.created_at wins — the original anchor whose
    existence caused subsequent dedup-subsume decisions.

    Fail-open: on exception returns an empty dict so the worker
    proceeds without dedup rather than blocking remediation.
    """
    from body.services.service_registry import service_registry
    from will.autonomy.proposal_repository import ProposalRepository

    candidates: list[tuple[tuple[str, str | None], str, Any]] = []
    try:
        async with service_registry.session() as session:
            repo = ProposalRepository(session)
            for status in _ACTIVE_STATUSES:
                proposals = await repo.list_by_status(status, limit=200)
                for proposal in proposals:
                    for action in proposal.actions:
                        action_file_path = (
                            action.parameters.get("file_path")
                            if action.parameters
                            else None
                        )
                        candidates.append(
                            (
                                (action.ref_id, action_file_path),
                                proposal.proposal_id,
                                proposal.created_at,
                            )
                        )
    except Exception as e:
        logger.warning(
            "ViolationRemediatorWorker: could not load active proposals (%s). "
            "Proceeding without deduplication.",
            e,
        )
        return {}

    candidates.sort(key=lambda t: t[2])
    result: dict[tuple[str, str | None], str] = {}
    for key, proposal_id, _created_at in candidates:
        result.setdefault(key, proposal_id)
    return result


# ID: 856e5070-2566-4a25-be09-4c9ae9cf6964
async def check_circuit_breaker(
    *,
    ref_id: str,
    ref_kind: str,
    file_path: str | None,
    config: Any,
) -> tuple[int, str | None, str | None, str | None]:
    """ADR-038 consecutive-identical-failure streak for (ref_id, file_path).

    Opens its own short-lived session so the breaker query does not
    extend the lifetime of the ProposalRepository session that backs
    create_proposal. Fail-soft: any DB error returns (0, None, None, None)
    so the breaker degrades toward retry rather than silent rejection on
    transient infra issues.
    """
    from body.services.service_registry import service_registry

    try:
        async with service_registry.session() as session:
            return await recent_consecutive_identical_count(
                session,
                ref_id=ref_id,
                ref_kind=ref_kind,
                file_path=file_path,
                config=config,
            )
    except Exception as exc:
        logger.warning(
            "ViolationRemediatorWorker: circuit-breaker session failed for "
            "(%s, %s, %s): %s — proceeding without gate.",
            ref_kind,
            ref_id,
            file_path,
            exc,
        )
        return 0, None, None, None
