# src/will/workers/violation_remediator.py
"""
ViolationRemediatorWorker — closes the autonomous audit loop by converting
open audit.violation findings into Proposals and transitioning each
consumed entry to its appropriate terminal state.

Constitutional role: acting worker, remediation phase.
Declaration:        .intent/workers/violation_remediator.yaml

Loop position:
  AuditViolationSensor → Blackboard
                       → ViolationRemediatorWorker (THIS)
                       → Proposal (one per (action, file) — ADR-035 D1)
                       → ProposalConsumerWorker → ProposalExecutor
                       → on failure: ProposalStateManager.mark_failed
                                     revives the deferred findings (§7a)

Design constraints: no LLM, no file writes, dedup against active proposals
on the (ref_id, file_path) key (ADR-035 D2). Findings are deferred AFTER
the proposal is persisted. Safe (approval_required=False) proposals are
created in APPROVED status so the consumer worker can execute without a
separate approval step.

Terminal-state semantics are documented on each collaborator function:
- Proposal creation and active-proposal indexing — see
  violation_remediator_proposal.py (ADR-035, ADR-010, ADR-038).
- Blackboard transitions (resolve / defer / release / release_unmappable /
  mark_delegated) — see violation_remediator_blackboard.py
  (ADR-010, ADR-015 D4).
"""

from __future__ import annotations

from typing import Any

from shared.infrastructure.intent.vocabulary_projection import (
    VocabularyProjectionError,
    load_vocabulary_projection,
)
from shared.logger import getLogger
from shared.workers.base import Worker
from will.workers.circuit_breaker import load_circuit_breaker_config, trip
from will.workers.violation_remediator_blackboard import (
    defer_to_proposal,
    load_open_findings,
    mark_delegated,
    release_entries,
    release_unmappable,
    resolve_entries,
)
from will.workers.violation_remediator_proposal import (
    check_circuit_breaker,
    create_proposal,
    get_active_proposal_id_by_action_file,
)


logger = getLogger(__name__)

_FINDING_SUBJECT_PREFIX = "audit.violation::"


def _entry_id(finding: dict[str, Any]) -> str:
    """Extract blackboard entry id ('id' or 'entry_id'); raise on contract violation."""
    value = finding.get("id") or finding.get("entry_id")
    if value is None:
        raise ValueError(f"Finding has neither 'id' nor 'entry_id': {finding!r}")
    return str(value)


def _rules_of(findings: list[dict[str, Any]]) -> list[str]:
    """Deduplicated rule list from findings — used in completion report."""
    return list(
        {
            f["payload"].get("check_id") or f["payload"].get("rule", "unknown")
            for f in findings
        }
    )


# ID: b4c5d6e7-f8a9-0123-bcde-f12345678904
class ViolationRemediatorWorker(Worker):
    """
    Acting worker that converts Blackboard violation findings into proposals.

    Reads open audit.violation findings, maps each rule to a remediation
    action via .intent/ remediation map, groups by (action, file) per
    ADR-035 D1, deduplicates against active proposals on the same
    (action, file) unit, creates per-finding proposals, transitions the
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
        """One audit-loop cycle: load → group → dedup → propose → transition → report."""
        projection = load_vocabulary_projection()
        if isinstance(projection, VocabularyProjectionError):
            logger.error(
                "ViolationRemediatorWorker: skipping cycle — vocabulary projection broken: %s",
                projection.reason,
            )
            await self.post_finding(
                "governance.instrument_degraded",
                {
                    "instrument": "vocabulary_projection",
                    "reason": projection.reason,
                    "worker": self.declaration_name,
                },
            )
            return

        open_findings = await self._load_open_findings()

        if not open_findings:
            await self.post_heartbeat()
            logger.info("ViolationRemediatorWorker: no open violation findings")
            return

        logger.info(
            "ViolationRemediatorWorker: %d open findings to process",
            len(open_findings),
        )

        remediation_map = self._get_remediation_map()

        action_groups: dict[tuple[str, str | None], list[dict[str, Any]]] = {}
        ref_kinds: dict[str, str] = {}
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
                ref_id = entry["ref_id"]
                ref_kind = entry["ref_kind"]
                if ref_kind == "flow":
                    key = (ref_id, None)
                else:
                    file_path = finding["payload"].get("file_path") or None
                    key = (ref_id, file_path)
                action_groups.setdefault(key, []).append(finding)
                ref_kinds[ref_id] = ref_kind
            else:
                unmappable.append(finding)
                logger.debug(
                    "ViolationRemediatorWorker: no remediation mapping for rule '%s'",
                    rule,
                )

        active_proposal_ids = await self._get_active_proposal_id_by_action_file()
        cb_config = load_circuit_breaker_config()

        proposals_created: list[str] = []
        proposals_skipped: list[str] = []
        proposals_circuit_broken: list[str] = []
        entries_deferred: int = 0
        entries_resolved_dedup: int = 0
        entries_released_after_failure: int = 0
        entries_circuit_broken: int = 0

        for (ref_id, file_path), findings in action_groups.items():
            ref_kind = ref_kinds[ref_id]
            entry_ids = [_entry_id(f) for f in findings]
            group_label = f"{ref_id}::{file_path or '<no-file>'}"

            subsuming_proposal_id = active_proposal_ids.get((ref_id, file_path))
            if subsuming_proposal_id:
                resolved = await self._resolve_entries(entry_ids, subsuming_proposal_id)
                entries_resolved_dedup += resolved
                proposals_skipped.append(group_label)
                logger.info(
                    "ViolationRemediatorWorker: skipping '%s' — active proposal "
                    "%s exists; resolved %d subsumed finding(s) with proposal_id "
                    "linkage",
                    group_label,
                    subsuming_proposal_id,
                    resolved,
                )
                continue

            (
                cb_count,
                cb_signature,
                cb_last_pid,
                cb_last_reason,
            ) = await self._check_circuit_breaker(
                ref_id=ref_id,
                ref_kind=ref_kind,
                file_path=file_path,
                config=cb_config,
            )
            if cb_count >= cb_config.threshold_n:
                await trip(
                    worker=self,
                    ref_id=ref_id,
                    ref_kind=ref_kind,
                    file_path=file_path,
                    findings=findings,
                    count=cb_count,
                    signature=cb_signature,
                    last_proposal_id=cb_last_pid,
                    last_failure_reason=cb_last_reason,
                    mark_delegated=self._mark_delegated,
                )
                proposals_circuit_broken.append(group_label)
                entries_circuit_broken += len(entry_ids)
                continue

            proposal_id = await self._create_proposal(ref_id, ref_kind, findings)

            if proposal_id:
                proposals_created.append(group_label)
                deferred = await self._defer_to_proposal(entry_ids, proposal_id)
                entries_deferred += deferred
                logger.info(
                    "ViolationRemediatorWorker: created proposal '%s' for %s "
                    "'%s' (%d findings, %d entries deferred to proposal)",
                    proposal_id,
                    ref_kind,
                    group_label,
                    len(findings),
                    deferred,
                )
            else:
                released = await self._release_entries(entry_ids)
                entries_released_after_failure += released
                logger.warning(
                    "ViolationRemediatorWorker: proposal for '%s' not created; "
                    "released %d finding(s) back to open",
                    group_label,
                    released,
                )

        entries_released = await self._release_unmappable(unmappable)
        if entries_released:
            logger.info(
                "ViolationRemediatorWorker: released %d unmappable findings back to open",
                entries_released,
            )

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

        await self.post_report(
            subject="violation_remediator.completed",
            payload={
                "open_findings": len(open_findings),
                "unmappable": len(unmappable),
                "action_groups": len(action_groups),
                "proposals_created": len(proposals_created),
                "proposals_skipped_dedup": len(proposals_skipped),
                "proposals_circuit_broken": len(proposals_circuit_broken),
                "entries_deferred": entries_deferred,
                "entries_resolved_dedup": entries_resolved_dedup,
                "entries_released_after_failure": entries_released_after_failure,
                "entries_released": entries_released,
                "entries_delegated": entries_delegated,
                "entries_circuit_broken": entries_circuit_broken,
                "created_actions": proposals_created,
                "skipped_actions": proposals_skipped,
                "circuit_broken_actions": proposals_circuit_broken,
                "unmappable_rules": _rules_of(unmappable),
                "delegated": len(delegate),
                "delegated_rules": _rules_of(delegate),
            },
        )

        logger.info(
            "ViolationRemediatorWorker: done — %d proposals created "
            "(%d entries deferred), %d skipped (dedup, %d subsumed entries "
            "resolved), %d circuit-broken (%d entries delegated), "
            "%d unmappable findings, %d entries released after failure",
            len(proposals_created),
            entries_deferred,
            len(proposals_skipped),
            entries_resolved_dedup,
            len(proposals_circuit_broken),
            entries_circuit_broken,
            len(unmappable),
            entries_released_after_failure,
        )

    # -------------------------------------------------------------------------
    # Private helpers — collaborator-module shims. Kept as bound methods on
    # the class so tests can patch/call them (worker._create_proposal etc.);
    # each shim is a one-line delegation to the corresponding free function.
    # -------------------------------------------------------------------------

    async def _blackboard_service(self) -> Any:
        from body.services.service_registry import service_registry

        return await service_registry.get_blackboard_service()

    # ID: d6e7f8a9-b0c1-2345-defa-234567890125
    async def _load_open_findings(self) -> list[dict[str, Any]]:
        return await load_open_findings(
            await self._blackboard_service(),
            prefix=f"{_FINDING_SUBJECT_PREFIX}%",
            claimed_by=self._worker_uuid,
            remediation_map=self._get_remediation_map(),
        )

    # ID: 8a7c5e91-2b4f-4d63-9e07-1a3c5d8b2f04
    async def _get_active_proposal_id_by_action_file(
        self,
    ) -> dict[tuple[str, str | None], str]:
        return await get_active_proposal_id_by_action_file()

    # ID: f8a9b0c1-d2e3-4567-fabc-456789012347
    async def _create_proposal(
        self, ref_id: str, ref_kind: str, findings: list[dict[str, Any]]
    ) -> str | None:
        return await create_proposal(ref_id, ref_kind, findings)

    # ID: a9b0c1d2-e3f4-5678-abcd-567890123458
    async def _resolve_entries(self, entry_ids: list[str], proposal_id: str) -> int:
        return await resolve_entries(
            await self._blackboard_service(), entry_ids, proposal_id
        )

    # ID: 2f8b4e71-c950-4a6d-b3e8-7f1a5c2d906e
    async def _defer_to_proposal(self, entry_ids: list[str], proposal_id: str) -> int:
        return await defer_to_proposal(
            await self._blackboard_service(), entry_ids, proposal_id
        )

    # ID: d2e3f4a5-b6c7-8901-defa-890123456781
    async def _release_entries(self, entry_ids: list[str]) -> int:
        return await release_entries(await self._blackboard_service(), entry_ids)

    # ID: b0c1d2e3-f4a5-6789-bcde-678901234569
    async def _release_unmappable(self, findings: list[dict[str, Any]]) -> int:
        return await release_unmappable(await self._blackboard_service(), findings)

    # ID: e16afa44-6fde-4782-9879-e4953b997e74
    async def _check_circuit_breaker(
        self,
        *,
        ref_id: str,
        ref_kind: str,
        file_path: str | None,
        config: Any,
    ) -> tuple[int, str | None, str | None, str | None]:
        return await check_circuit_breaker(
            ref_id=ref_id, ref_kind=ref_kind, file_path=file_path, config=config
        )

    # ID: c1d2e3f4-a5b6-7890-cdef-789012345670
    async def _mark_delegated(self, findings: list[dict[str, Any]]) -> int:
        return await mark_delegated(await self._blackboard_service(), findings)
