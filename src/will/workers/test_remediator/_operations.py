# src/will/workers/test_remediator/_operations.py
"""
Module-level operations for TestRemediatorWorker.

Extracted from the monolithic worker file to satisfy modularity.needs_split.
All functions are private (`_name`) — they are consumed exclusively by
TestRemediatorWorker.run() and the integration test for _defer_to_proposal.
"""

from __future__ import annotations

import uuid
from typing import Any

from shared.logger import getLogger
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)


logger = getLogger(__name__)

_MISSING_SUBJECT_PREFIX = "test.missing::"
_FAILURE_SUBJECT_PREFIX = "test.failure::"
_TARGET_ACTION_ID = "build.tests"
_TARGET_RULES: list[str] = ["test.missing", "test.failure"]

_ACTIVE_STATUSES: frozenset[ProposalStatus] = frozenset(
    {
        ProposalStatus.DRAFT,
        ProposalStatus.PENDING,
        ProposalStatus.APPROVED,
        ProposalStatus.EXECUTING,
    }
)


async def _load_open_findings(worker_uuid: uuid.UUID) -> list[dict[str, Any]]:
    """
    Claim open test.missing and test.failure findings from the Blackboard.

    Two separate claim_violation_findings calls (one per prefix) whose
    results are merged. Findings without a source_file in payload are
    released immediately so they do not stay claimed indefinitely.
    """
    from body.services.service_registry import service_registry

    merged: list[dict[str, Any]] = []

    try:
        blackboard_service = await service_registry.get_blackboard_service()
        for prefix in (_MISSING_SUBJECT_PREFIX, _FAILURE_SUBJECT_PREFIX):
            claimed = await blackboard_service.claim_violation_findings(
                prefix=f"{prefix}%",
                limit=200,
                claimed_by=worker_uuid,
            )
            merged.extend(claimed)
    except Exception as e:
        logger.error("TestRemediatorWorker: failed to load findings: %s", e)
        return []

    if not merged:
        return []

    valid: list[dict[str, Any]] = []
    invalid_ids: list[str] = []
    for finding in merged:
        payload = finding.get("payload") or {}
        if payload.get("source_file"):
            valid.append(finding)
        else:
            invalid_ids.append(finding["id"])

    if invalid_ids:
        try:
            blackboard_service = await service_registry.get_blackboard_service()
            released = await blackboard_service.release_claimed_entries(invalid_ids)
            logger.info(
                "TestRemediatorWorker: released %d/%d findings missing "
                "source_file at claim time",
                released,
                len(invalid_ids),
            )
        except Exception as e:
            logger.error(
                "TestRemediatorWorker: failed to release invalid "
                "findings at claim time: %s",
                e,
            )

    return valid


async def _get_active_build_tests_source_files() -> set[str]:
    """
    Return the set of source_file values currently in flight for the
    'build.tests' action — i.e. referenced by any active proposal.

    A proposal is active when its status is in _ACTIVE_STATUSES. For
    each such proposal, every action whose action_id is 'build.tests'
    contributes its parameters["source_file"] (when present) to the
    returned set.

    Fail open — if the lookup raises, return an empty set and the
    caller proceeds without per-source_file deduplication.
    """
    from body.services.service_registry import service_registry
    from will.autonomy.proposal_repository import ProposalRepository

    active_source_files: set[str] = set()
    try:
        async with service_registry.session() as session:
            repo = ProposalRepository(session)
            for status in _ACTIVE_STATUSES:
                proposals = await repo.list_by_status(status, limit=200)
                for proposal in proposals:
                    for action in proposal.actions:
                        if action.action_id != _TARGET_ACTION_ID:
                            continue
                        source_file = (action.parameters or {}).get("source_file")
                        if source_file:
                            active_source_files.add(source_file)
    except Exception as e:
        logger.warning(
            "TestRemediatorWorker: could not load active proposals (%s). "
            "Proceeding without per-source_file deduplication.",
            e,
        )
    return active_source_files


async def _create_proposal(
    action_id: str,
    findings: list[dict[str, Any]],
) -> str | None:
    """Create and persist a Proposal for the given action and findings.

    All findings passed to this method must share a single source_file
    (the caller groups them accordingly). The action parameter carries
    exactly that source_file.

    Safe proposals (approval_required=False) are created in APPROVED status
    so ProposalConsumerWorker can execute them without a separate approval step.
    Proposals requiring human approval are created in DRAFT.
    """
    from body.services.service_registry import service_registry
    from will.autonomy.proposal_repository import ProposalRepository
    from will.autonomy.proposal_state_manager import ProposalStateManager

    affected_files: list[str] = sorted(
        {
            f["payload"].get("source_file", "")
            for f in findings
            if f["payload"].get("source_file")
        }
    )

    primary_source_file = affected_files[0] if affected_files else None

    proposal = Proposal(
        goal=(
            f"Autonomous test remediation: {action_id} "
            f"({len(findings)} finding(s) — rules: {', '.join(_TARGET_RULES)})"
        ),
        actions=[
            ProposalAction(
                action_id=action_id,
                parameters={
                    "source_file": primary_source_file,
                    "write": True,
                },
                order=0,
            )
        ],
        scope=ProposalScope(files=affected_files),
        created_by="test_remediator_worker",
        constitutional_constraints={
            "source": "blackboard_findings",
            "rules": list(_TARGET_RULES),
            "affected_files_count": len(affected_files),
        },
    )

    proposal.compute_risk()

    # status remains DRAFT here; the auto-approval path below routes
    # through ProposalStateManager.approve() so approval_authority is
    # recorded on the row (URS NFR.5; ADR-015 D6).

    is_valid, errors = proposal.validate()
    if not is_valid:
        logger.warning(
            "TestRemediatorWorker: proposal for '%s' failed validation: %s",
            action_id,
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
                    "TestRemediatorWorker: proposal for '%s' auto-approved "
                    "(risk=%s, approval_required=False)",
                    action_id,
                    proposal.risk.overall_risk if proposal.risk else "unknown",
                )
            else:
                logger.info(
                    "TestRemediatorWorker: proposal for '%s' requires human approval "
                    "(risk=%s) — created in DRAFT",
                    action_id,
                    proposal.risk.overall_risk if proposal.risk else "unknown",
                )

            await session.commit()
        return proposal_id
    except Exception as e:
        logger.error(
            "TestRemediatorWorker: failed to persist proposal for '%s': %s",
            action_id,
            e,
        )
        return None


# ID: 0337c11c-7b70-4106-9e1f-3610556ed25c
async def _defer_to_proposal(entry_ids: list[str], proposal_id: str) -> int:
    """
    Transition Blackboard entries to 'deferred_to_proposal' and store
    the proposal_id in each entry's payload.

    Happy-path terminal transition for findings consumed into a newly-
    created build.tests proposal. Mirrors ViolationRemediatorWorker's
    contract (CORE-Finding.md §7 row 4, ADR-010); the §7a revival
    path in ProposalStateManager.mark_failed depends on this linkage.

    Returns count of entries successfully deferred. Fail-soft: if the
    service call raises, logs the error and returns 0 rather than
    propagating — matches the existing pattern of _release_entries.
    The caller's `proposals_created` list is already populated by the
    time this runs, so a revival-layer failure here does not reverse
    the proposal creation.
    """
    if not entry_ids:
        return 0

    from body.services.service_registry import service_registry

    try:
        blackboard_service = await service_registry.get_blackboard_service()
        return await blackboard_service.defer_entries_to_proposal(
            entry_ids, proposal_id
        )
    except Exception as e:
        logger.error(
            "TestRemediatorWorker: failed to defer entries to proposal %s: %s",
            proposal_id,
            e,
        )
        return 0


async def _release_entries(entry_ids: list[str]) -> int:
    """
    Release claimed findings back to open status.
    Used when proposal creation is skipped by dedup.
    """
    from body.services.service_registry import service_registry

    if not entry_ids:
        return 0

    try:
        blackboard_service = await service_registry.get_blackboard_service()
        return await blackboard_service.release_claimed_entries(entry_ids)
    except Exception as e:
        logger.error("TestRemediatorWorker: failed to release entries: %s", e)
        return 0
