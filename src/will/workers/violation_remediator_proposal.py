# src/will/workers/violation_remediator_proposal.py
"""
Proposal creation, active-proposal dedup index, and circuit-breaker
gate for ViolationRemediatorWorker.

Collaborator module. Owns three operations that ViolationRemediatorWorker
calls from its run loop:

- create_proposal: build a Proposal from a (ref_id, ref_kind, findings) group,
  validate it, persist via ProposalRepository, auto-approve through
  ProposalStateManager when risk classification says safe, and return the
  proposal_id. Safe proposals land in APPROVED status so the consumer worker
  can pick them up without a separate human approval step (ADR-035 D1;
  per-finding scope keyed by (action_id, file_path) for atomic actions, or
  by flow_id alone for flows).
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
nothing in this module posts to the blackboard.

LAYER: will/workers — internal collaborator of ViolationRemediatorWorker.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)
from will.workers.circuit_breaker import recent_consecutive_identical_count


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
) -> str | None:
    """Create and persist a Proposal for the given remediation reference.

    ref_kind selects the ProposalAction shape: "action" produces
    ProposalAction(action_id=ref_id, ...) and "flow" produces
    ProposalAction(flow_id=ref_id, ...). The two are mutually exclusive
    per ProposalAction.__post_init__.

    Safe proposals (approval_required=False) are auto-approved through
    ProposalStateManager so the row carries approval_authority
    (URS NFR.5; ADR-015 D6) and the consumer worker can execute without
    a separate approval step. Proposals requiring human approval stay
    in DRAFT.

    Returns proposal_id on success, None on validation or persistence
    failure.
    """
    from body.services.service_registry import service_registry
    from will.autonomy.proposal_repository import ProposalRepository
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

    # finding_ids mirrors the entry_ids subsequently passed to
    # defer_to_proposal in the worker run loop, making the proposal→finding
    # read path symmetric with the finding→proposal write path. Consumed
    # by ProposalExecutor when emitting consequence-log entries
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

    try:
        async with service_registry.session() as session:
            repo = ProposalRepository(session)
            proposal_id = await repo.create(proposal)

            if not proposal.approval_required:
                state_manager = ProposalStateManager(session)
                await state_manager.approve(
                    proposal_id,
                    approved_by="autonomous_self_promote",
                    approval_authority="risk_classification.safe_auto_approval",
                )
                logger.info(
                    "ViolationRemediatorWorker: proposal for '%s' auto-approved "
                    "(risk=%s, approval_required=False)",
                    ref_id,
                    proposal.risk.overall_risk if proposal.risk else "unknown",
                )
            else:
                logger.info(
                    "ViolationRemediatorWorker: proposal for '%s' requires human "
                    "approval (risk=%s) — created in DRAFT",
                    ref_id,
                    proposal.risk.overall_risk if proposal.risk else "unknown",
                )

            await session.commit()
        return proposal_id
    except Exception as e:
        logger.error(
            "ViolationRemediatorWorker: failed to persist proposal for '%s': %s",
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
