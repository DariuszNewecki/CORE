# src/will/workers/violation_remediator.py
# ID: workers.violation_remediator
"""
ViolationRemediatorWorker - Closes the autonomous audit loop.

Constitutional role: acting worker, remediation phase.

Responsibility (from .intent/workers/violation_remediator.yaml):
  Consume open audit violation findings from the Blackboard, look up the
  remediating action from .intent/enforcement/mappings/remediation/auto_remediation.yaml
  (via _load_remediation_map), create one Proposal per unique action group,
  and defer each consumed Blackboard entry to the created Proposal.

The autonomous audit loop this closes:

  AuditViolationSensor (sensing)
      posts open findings to Blackboard
          ↓
  ViolationRemediatorWorker (acting)  ← THIS WORKER
      reads open findings from Blackboard
      looks up action via remediation map from .intent/
      creates Proposal (one per action group)
      transitions findings to 'deferred_to_proposal' with proposal_id
          ↓
  ProposalConsumerWorker
      executes APPROVED proposals via ProposalExecutor
          ↓  (on proposal failure)
      ProposalStateManager.mark_failed revives deferred findings
          ↓
  AuditViolationSensor runs again
      confirms violation gone or finds revived findings still open

Design constraints:
- No LLM calls
- No direct file writes
- Never creates a proposal if an active one exists for the same action
- Defers Blackboard entries to proposal AFTER the proposal is persisted (not before)
- One proposal per action ID (not one per finding)
- Safe proposals (approval_required=False) are created in APPROVED status
  so ProposalConsumerWorker can pick them up immediately

Per-path terminal-state semantics (ADR-010):

- Proposal created successfully     → findings deferred_to_proposal with
                                       proposal_id in payload. §7/§7a of
                                       CORE-Finding.md: on proposal failure
                                       these findings are revived to open
                                       by ProposalStateManager.mark_failed.
- Active proposal already exists    → findings resolved with the
                                       subsuming proposal_id stored in
                                       payload (subsumed by the in-flight
                                       proposal; the mandate's "consumed"
                                       covers routing-to-proposal, not
                                       only proposal-creation). Status is
                                       still 'resolved' — not
                                       'deferred_to_proposal' — because
                                       the subsuming proposal does not
                                       track these duplicates in its
                                       scope, so the §7a revival contract
                                       does not apply (ADR-010
                                       Alternatives Considered). The
                                       payload pointer is the audit
                                       linkage (URS Q1.F / ADR-015 D4).
- Proposal creation failed          → findings released back to open so the
                                       next run can retry cleanly.
- Finding unmappable                → already released (see _load_open_findings).
- Finding marked DELEGATE           → marked indeterminate (human decision).

FUTURE(two-log): the dedup-subsume path does NOT carry a payload pointer
to the subsuming proposal. The primary path (deferred_to_proposal with
proposal_id) is linked as of ADR-010; the dedup path is not, and
reconciling it would require a second finding→proposal relationship
shape the paper does not currently define. When the full consequence-
logging work lands, revisit dedup linkage.
CLOSED: the dedup-subsume payload-pointer gap above is closed by ADR-015 D4.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)


logger = getLogger(__name__)

_FINDING_SUBJECT_PREFIX = "audit.violation::"

_ACTIVE_STATUSES: frozenset[ProposalStatus] = frozenset(
    {
        ProposalStatus.DRAFT,
        ProposalStatus.PENDING,
        ProposalStatus.APPROVED,
        ProposalStatus.EXECUTING,
    }
)


def _entry_id(finding: dict[str, Any]) -> str:
    """
    Extract the blackboard-entry id from a finding dict.

    Findings arriving from BlackboardService carry either an 'id' or an
    'entry_id' key depending on the serialization path; both are accepted.
    Raises ValueError if neither is present — findings without a resolvable
    id cannot be acted on by this worker and represent a contract violation
    from the service layer. Fail loud at extraction rather than passing None
    down to the SQL layer where the error is less legible.
    """
    value = finding.get("id") or finding.get("entry_id")
    if value is None:
        raise ValueError(f"Finding has neither 'id' nor 'entry_id': {finding!r}")
    return str(value)


# ID: b4c5d6e7-f8a9-0123-bcde-f12345678904
class ViolationRemediatorWorker(Worker):
    """
    Acting worker that converts Blackboard violation findings into proposals.

    Reads open audit.violation findings, maps each rule to a remediation
    action via .intent/ remediation map, groups by action, deduplicates
    against active proposals, creates proposals, transitions the
    consumed entries to 'deferred_to_proposal' with the proposal_id
    stored in their payload (per CORE-Finding.md §7).

    Safe proposals (approval_required=False) are created in APPROVED status
    so ProposalConsumerWorker can execute them without a separate approval step.
    """

    declaration_name = "violation_remediator"

    def __init__(
        self, core_context: Any = None, declaration_name: str = "", **kwargs: Any
    ) -> None:
        """Accept daemon kwargs — stores core_context for repo path resolution."""
        super().__init__(declaration_name=declaration_name)
        self._core_context = core_context

    def _get_remediation_map(self) -> dict:
        """Load rule-to-action mappings from .intent/ via PathResolver."""
        from body.autonomy.audit_analyzer import _load_remediation_map
        from shared.path_resolver import PathResolver

        path_resolver = PathResolver(self._core_context.git_service.repo_path)
        return _load_remediation_map(path_resolver)

    # ID: c5d6e7f8-a9b0-1234-cdef-123456789014
    async def run(self) -> None:
        """
        Core work unit:
        1. Load open violation findings from Blackboard
        2. Group by action (via .intent/ remediation map)
        3. Deduplicate against active proposals
        4. Create proposals for new action groups
        5. Transition consumed Blackboard entries:
             - happy path:    deferred_to_proposal (with proposal_id)
             - dedup-subsume: resolved
             - create-failed: released back to open
        6. Post blackboard report
        """
        # 1. Load open findings
        open_findings = await self._load_open_findings()

        if not open_findings:
            await self.post_heartbeat()
            logger.info("ViolationRemediatorWorker: no open violation findings")
            return

        logger.info(
            "ViolationRemediatorWorker: %d open findings to process",
            len(open_findings),
        )

        # 2. Group by action using .intent/ remediation map
        remediation_map = self._get_remediation_map()

        action_groups: dict[str, list[dict[str, Any]]] = {}
        unmappable: list[dict[str, Any]] = []
        delegate: list[dict[str, Any]] = []

        for finding in open_findings:
            rule = finding["payload"].get("check_id") or finding["payload"].get(
                "rule", ""
            )
            entry = remediation_map.get(rule)

            if entry and entry.get("status") == "DELEGATE":
                finding["_map_entry"] = entry
                delegate.append(finding)
            elif entry:
                action_id = entry["action"]
                action_groups.setdefault(action_id, [])
                action_groups[action_id].append(finding)
            else:
                unmappable.append(finding)
                logger.debug(
                    "ViolationRemediatorWorker: no remediation mapping for rule '%s'",
                    rule,
                )

        # 3. Deduplicate against active proposals
        active_proposal_ids = await self._get_active_proposal_id_by_action()

        # 4. Create proposals + 5. Transition entries per ADR-010 / ADR-015 D4.
        proposals_created: list[str] = []
        proposals_skipped: list[str] = []
        entries_deferred: int = 0
        entries_resolved_dedup: int = 0
        entries_released_after_failure: int = 0

        for action_id, findings in action_groups.items():
            entry_ids = [_entry_id(f) for f in findings]

            subsuming_proposal_id = active_proposal_ids.get(action_id)
            if subsuming_proposal_id:
                # Dedup: an active proposal already represents this action
                # group. Findings are subsumed — the mandate's "consumed"
                # applies (routing-to-proposal, not only proposal-creation).
                # Status is 'resolved' — not 'deferred_to_proposal' —
                # because the subsuming proposal does not track these
                # duplicates in its scope, so the §7a revival contract
                # does not apply (ADR-010 Alternatives Considered). The
                # subsuming proposal_id is recorded in payload as the
                # audit linkage (URS Q1.F / ADR-015 D4).
                resolved = await self._resolve_entries(entry_ids, subsuming_proposal_id)
                entries_resolved_dedup += resolved
                proposals_skipped.append(action_id)
                logger.info(
                    "ViolationRemediatorWorker: skipping '%s' — active proposal "
                    "%s exists; resolved %d subsumed finding(s) with proposal_id "
                    "linkage",
                    action_id,
                    subsuming_proposal_id,
                    resolved,
                )
                continue

            proposal_id = await self._create_proposal(action_id, findings)

            if proposal_id:
                proposals_created.append(action_id)
                # ADR-010 / CORE-Finding.md §7: on successful proposal
                # creation, transition findings to 'deferred_to_proposal'
                # and store proposal_id in their payload. The §7a revival
                # contract in ProposalStateManager.mark_failed depends on
                # this linkage.
                deferred = await self._defer_to_proposal(entry_ids, proposal_id)
                entries_deferred += deferred
                logger.info(
                    "ViolationRemediatorWorker: created proposal '%s' for action "
                    "'%s' (%d findings, %d entries deferred to proposal)",
                    proposal_id,
                    action_id,
                    len(findings),
                    deferred,
                )
            else:
                # Proposal creation failed (validation or persist error).
                # Release the claimed findings so the next run can retry
                # instead of leaving them stuck at claimed.
                released = await self._release_entries(entry_ids)
                entries_released_after_failure += released
                logger.warning(
                    "ViolationRemediatorWorker: proposal for '%s' not created; "
                    "released %d finding(s) back to open",
                    action_id,
                    released,
                )

        # 5b. Release unmappable findings back to open so they don't stay claimed
        entries_released = await self._release_unmappable(unmappable)
        if entries_released:
            logger.info(
                "ViolationRemediatorWorker: released %d unmappable findings back to open",
                entries_released,
            )

        # 5c. Mark delegated findings as indeterminate — requires human decision
        entries_delegated = await self._mark_delegated(delegate)
        for finding in delegate:
            rule = finding["payload"].get("check_id") or finding["payload"].get(
                "rule", "unknown"
            )
            file_path = finding["payload"].get("file_path", "unknown")
            map_entry = finding.get("_map_entry", {})
            description = map_entry.get("description", "")
            logger.info(
                "[DELEGATE] %s -> HUMAN REQUIRED\n"
                "           File: %s\n"
                "           Decision needed: %s\n"
                "           Resolve with: core-admin workers blackboard --reopen %s",
                rule,
                file_path,
                description,
                finding.get("id") or finding.get("entry_id"),
            )

        # 6. Post blackboard report.
        # Report-shape note (ADR-010): the happy-path counter is now
        # 'entries_deferred'. The legacy 'entries_resolved' key is removed
        # rather than kept-as-zero, because 'entries_resolved: 0' was a
        # known diagnostic signal for the silent claim-leak bug and
        # preserving it as a structural zero would create a false positive
        # for that diagnostic. Consumers that read the old key will fail
        # loudly — the correct signal of the contract change.
        await self.post_report(
            subject="violation_remediator.completed",
            payload={
                "open_findings": len(open_findings),
                "unmappable": len(unmappable),
                "action_groups": len(action_groups),
                "proposals_created": len(proposals_created),
                "proposals_skipped_dedup": len(proposals_skipped),
                "entries_deferred": entries_deferred,
                "entries_resolved_dedup": entries_resolved_dedup,
                "entries_released_after_failure": entries_released_after_failure,
                "entries_released": entries_released,
                "entries_delegated": entries_delegated,
                "created_actions": proposals_created,
                "skipped_actions": proposals_skipped,
                "unmappable_rules": list(
                    {
                        f["payload"].get("check_id")
                        or f["payload"].get("rule", "unknown")
                        for f in unmappable
                    }
                ),
                "delegated": len(delegate),
                "delegated_rules": list(
                    {
                        f["payload"].get("check_id")
                        or f["payload"].get("rule", "unknown")
                        for f in delegate
                    }
                ),
            },
        )

        logger.info(
            "ViolationRemediatorWorker: done — %d proposals created "
            "(%d entries deferred), %d skipped (dedup, %d subsumed entries "
            "resolved), %d unmappable findings, %d entries released after failure",
            len(proposals_created),
            entries_deferred,
            len(proposals_skipped),
            entries_resolved_dedup,
            len(unmappable),
            entries_released_after_failure,
        )

    # -------------------------------------------------------------------------
    # Private helpers
    # -------------------------------------------------------------------------

    # ID: d6e7f8a9-b0c1-2345-defa-234567890125
    async def _load_open_findings(self) -> list[dict[str, Any]]:
        """
        Query Blackboard for open audit violation findings.

        Claims findings atomically, then immediately filters out any whose
        check_id/rule has no entry in the .intent/ remediation map.  Unmappable
        findings are released back to open status so they are not held
        claimed indefinitely.

        Returns only mappable findings (list of dicts with: id, subject, payload).
        """
        from body.services.service_registry import service_registry

        try:
            blackboard_service = await service_registry.get_blackboard_service()
            claimed = await blackboard_service.claim_violation_findings(
                prefix=f"{_FINDING_SUBJECT_PREFIX}%",
                limit=200,
                claimed_by=self._worker_uuid,
            )
        except Exception as e:
            logger.error("ViolationRemediatorWorker: failed to load findings: %s", e)
            return []

        if not claimed:
            return []

        # Post-claim filter: keep only findings with a known remediation mapping.
        remediation_map = self._get_remediation_map()
        mappable: list[dict[str, Any]] = []
        unmappable_ids: list[str] = []

        for finding in claimed:
            rule = finding["payload"].get("check_id") or finding["payload"].get(
                "rule", ""
            )
            if remediation_map.get(rule):
                mappable.append(finding)
            else:
                unmappable_ids.append(_entry_id(finding))

        # Immediately release unmappable findings so they don't stay claimed.
        if unmappable_ids:
            try:
                released = await blackboard_service.release_claimed_entries(
                    unmappable_ids
                )
                logger.info(
                    "ViolationRemediatorWorker: released %d/%d unmappable "
                    "findings at claim time",
                    released,
                    len(unmappable_ids),
                )
            except Exception as e:
                logger.error(
                    "ViolationRemediatorWorker: failed to release "
                    "unmappable findings at claim time: %s",
                    e,
                )

        return mappable

    # ID: 8a7c5e91-2b4f-4d63-9e07-1a3c5d8b2f04
    async def _get_active_proposal_id_by_action(self) -> dict[str, str]:
        """
        Return a mapping of action_id → proposal_id for actions that
        already have an active proposal. The dedup-subsume path needs
        the proposal_id (not just the action_id) to record the linkage
        in the subsumed finding's payload — URS Q1.F / ADR-015 D4.

        When multiple active proposals share an action_id, the earliest
        by Proposal.created_at wins. The earliest proposal is the
        original anchor whose existence caused subsequent dedup-subsume
        decisions, so subsumed findings attribute to it.

        Fail-open: on exception returns an empty dict so the worker
        proceeds without dedup rather than blocking remediation.
        """
        from body.services.service_registry import service_registry
        from will.autonomy.proposal_repository import ProposalRepository

        candidates: list[tuple[str, str, Any]] = []
        try:
            async with service_registry.session() as session:
                repo = ProposalRepository(session)
                for status in _ACTIVE_STATUSES:
                    proposals = await repo.list_by_status(status, limit=200)
                    for proposal in proposals:
                        for action in proposal.actions:
                            candidates.append(
                                (
                                    action.action_id,
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

        # Earliest-wins: ascending sort by created_at then setdefault keeps
        # the first seen — the original anchor proposal for that action.
        candidates.sort(key=lambda t: t[2])
        result: dict[str, str] = {}
        for action_id, proposal_id, _created_at in candidates:
            result.setdefault(action_id, proposal_id)
        return result

    # ID: f8a9b0c1-d2e3-4567-fabc-456789012347
    async def _create_proposal(
        self,
        action_id: str,
        findings: list[dict[str, Any]],
    ) -> str | None:
        """Create and persist a Proposal for the given action and findings.

        Safe proposals (approval_required=False) are created in APPROVED status
        so ProposalConsumerWorker can execute them without a separate approval step.
        Proposals requiring human approval are created in DRAFT.
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
        # _defer_to_proposal in run(), making the proposal→finding read
        # path symmetric with the finding→proposal write path. Consumed
        # by ProposalExecutor when emitting consequence-log entries
        # (proposal_executor.py:265-266). ADR-015 D7: forward-only —
        # historical proposals predating this field are not backfilled.
        finding_ids = [_entry_id(f) for f in findings]

        proposal = Proposal(
            goal=(
                f"Autonomous remediation: {action_id} "
                f"({len(findings)} violation(s) — rules: {', '.join(rules)})"
            ),
            actions=[
                ProposalAction(
                    action_id=action_id,
                    parameters={
                        "write": True,
                        "file_path": affected_files[0] if affected_files else None,
                    },
                    order=0,
                )
            ],
            scope=ProposalScope(files=affected_files),
            created_by="violation_remediator_worker",
            constitutional_constraints={
                "source": "blackboard_findings",
                "rules": rules,
                "affected_files_count": len(affected_files),
                "finding_ids": finding_ids,
            },
        )

        # compute_risk() sets approval_required correctly based on CORE's actual
        # risk model: "safe" / "moderate" / "dangerous". The previous code compared
        # against "high"/"critical" which don't exist — approval_required was always
        # stuck at False regardless of actual risk level.
        proposal.compute_risk()

        # status remains DRAFT here; the auto-approval path below routes
        # through ProposalStateManager.approve() so approval_authority is
        # recorded on the row (URS NFR.5; ADR-015 D6).

        is_valid, errors = proposal.validate()
        if not is_valid:
            logger.warning(
                "ViolationRemediatorWorker: proposal for '%s' failed validation: %s",
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
                        "ViolationRemediatorWorker: proposal for '%s' auto-approved "
                        "(risk=%s, approval_required=False)",
                        action_id,
                        proposal.risk.overall_risk if proposal.risk else "unknown",
                    )
                else:
                    logger.info(
                        "ViolationRemediatorWorker: proposal for '%s' requires human approval "
                        "(risk=%s) — created in DRAFT",
                        action_id,
                        proposal.risk.overall_risk if proposal.risk else "unknown",
                    )

                await session.commit()
            return proposal_id
        except Exception as e:
            logger.error(
                "ViolationRemediatorWorker: failed to persist proposal for '%s': %s",
                action_id,
                e,
            )
            return None

    # ID: a9b0c1d2-e3f4-5678-abcd-567890123458
    async def _resolve_entries(self, entry_ids: list[str], proposal_id: str) -> int:
        """
        Mark subsumed Blackboard entries as resolved with the subsuming
        proposal_id stored in payload.

        Called only from the dedup-subsume branch of run() — subsumed
        findings close as 'resolved' (not 'deferred_to_proposal') because
        the subsuming proposal does not track them in its scope, so the
        §7/§7a revival contract does not apply. The proposal_id payload
        pointer is the audit linkage per URS Q1.F / ADR-015 D4. The
        happy path (successful proposal creation) uses _defer_to_proposal
        instead so its Finding→Proposal contract is preserved.

        Routes to BlackboardService.resolve_entries_for_proposal — the
        dedicated mirror of defer_entries_to_proposal for this path.
        Returns count of entries successfully resolved.
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import service_registry

        try:
            blackboard_service = await service_registry.get_blackboard_service()
            return await blackboard_service.resolve_entries_for_proposal(
                entry_ids, proposal_id
            )
        except Exception as e:
            logger.error("ViolationRemediatorWorker: failed to resolve entries: %s", e)
            return 0

    # ID: 2f8b4e71-c950-4a6d-b3e8-7f1a5c2d906e
    async def _defer_to_proposal(self, entry_ids: list[str], proposal_id: str) -> int:
        """
        Transition Blackboard entries to 'deferred_to_proposal' and store
        the proposal_id in each entry's payload.

        This is the happy-path terminal transition for findings consumed
        into a newly-created proposal. See CORE-Finding.md §7 row 4 and
        ADR-010.

        Returns count of entries successfully deferred. Fail-soft: if the
        service call raises, logs the error and returns 0 rather than
        propagating — matches the existing pattern of _resolve_entries
        and _release_entries. The caller's `proposals_created` list is
        already populated by the time this runs, so a revival-layer
        failure here does not reverse the proposal creation.
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
                "ViolationRemediatorWorker: failed to defer entries to proposal %s: %s",
                proposal_id,
                e,
            )
            return 0

    # ID: d2e3f4a5-b6c7-8901-defa-890123456781
    async def _release_entries(self, entry_ids: list[str]) -> int:
        """
        Release claimed Blackboard entries back to open by id.
        Used when proposal creation fails and findings need to be retry-eligible
        on the next run. Returns count of entries successfully released.
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import service_registry

        try:
            blackboard_service = await service_registry.get_blackboard_service()
            return await blackboard_service.release_claimed_entries(entry_ids)
        except Exception as e:
            logger.error("ViolationRemediatorWorker: failed to release entries: %s", e)
            return 0

    # ID: b0c1d2e3-f4a5-6789-bcde-678901234569
    async def _release_unmappable(self, findings: list[dict[str, Any]]) -> int:
        """
        Release claimed findings that have no registered remediation action
        back to open status so another worker or a future registry update
        can pick them up.
        """
        if not findings:
            return 0

        entry_ids = [_entry_id(f) for f in findings]
        return await self._release_entries(entry_ids)

    # ID: c1d2e3f4-a5b6-7890-cdef-789012345670
    async def _mark_delegated(self, findings: list[dict[str, Any]]) -> int:
        """
        Mark delegated findings as indeterminate — they require human decision.
        Returns count of entries successfully marked.
        """
        if not findings:
            return 0

        from body.services.service_registry import service_registry

        entry_ids = [_entry_id(f) for f in findings]
        try:
            blackboard_service = await service_registry.get_blackboard_service()
            return await blackboard_service.mark_indeterminate(entry_ids)
        except Exception as e:
            logger.error(
                "ViolationRemediatorWorker: failed to mark delegated entries: %s", e
            )
            return 0
