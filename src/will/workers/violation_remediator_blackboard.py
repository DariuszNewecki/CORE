# src/will/workers/violation_remediator_blackboard.py
"""
Blackboard operations for ViolationRemediatorWorker.

Collaborator module. Owns the claim-time loader and the five terminal
transitions for findings:

- load_open_findings: claim open audit-violation findings (subject set
  derived from `audit_violation_like_patterns()` per ADR-091 D5 Phase 3);
  immediately release any whose rule has no remediation mapping so they
  don't stay parked at 'claimed'.
- resolve_entries: dedup-subsume path. Mark subsumed entries 'resolved'
  with the subsuming proposal_id on payload (URS Q1.F / ADR-015 D4).
  Status is 'resolved' rather than 'deferred_to_proposal' because the
  subsuming proposal does not track the subsumed entries in its scope,
  so the §7a revival contract does not apply.
- defer_to_proposal: happy path (ADR-010 / CORE-Finding.md §7 row 4).
  Transition entries to 'deferred_to_proposal' with proposal_id on
  payload — the linkage ProposalStateManager.mark_failed reads to
  revive findings if the proposal later fails.
- release_entries: rollback when proposal creation fails. Returns
  claimed entries to 'open' so the next cycle can retry cleanly.
- release_unmappable: same release path, driven from a list of finding
  dicts whose rule has no remediation map entry.
- mark_delegated: terminal 'indeterminate' for entries whose rule is
  DELEGATE — non-automatable, awaiting governor decision.

Implements:
  ADR-010    — Finding→Proposal linkage and the §7/§7a revival contract
  ADR-015 D4 — dedup-subsume payload pointer (audit linkage)

Every function takes the BlackboardService instance as its first
argument so the module is unit-testable against a stub service without
monkeypatching service_registry, and service-acquisition (and any
caching) lives on the caller side. Each transition is fail-soft: a
service-call exception is logged and the function returns 0 — a
service hiccup never reverses the worker's upstream accounting.

LAYER: will/workers — internal collaborator of ViolationRemediatorWorker.
No database access, no file writes, no LLM calls.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)


def _entry_id(finding: dict[str, Any]) -> str:
    """Extract the blackboard-entry id from a finding dict.

    Mirrors the helper in violation_remediator_proposal so this module is
    self-contained; both raise ValueError on a contract violation rather
    than silently propagating None to the SQL layer.
    """
    value = finding.get("id") or finding.get("entry_id")
    if value is None:
        raise ValueError(f"Finding has neither 'id' nor 'entry_id': {finding!r}")
    return str(value)


# ID: 87787044-a1a2-4e07-b2dc-197c8e9598c7
async def load_open_findings(
    service: Any,
    *,
    patterns: list[str],
    claimed_by: Any,
    remediation_map: dict[str, Any],
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Claim open audit-violation findings and filter to those with a remediation mapping.

    Atomically claims up to *limit* findings whose subject matches any of
    *patterns* (SQL LIKE patterns, typically the value of
    ``audit_violation_like_patterns()`` per ADR-091 D5 Phase 3), then
    partitions them by whether *remediation_map* has an entry for the rule.
    Mappable findings are returned. Unmappable ids are released back to
    'open' inside this call so they don't stay parked at 'claimed' across
    cycles.

    Fail-soft: a claim-time exception returns an empty list; a release-
    time exception is logged but does not propagate (the mappable
    findings the caller will work on are unaffected).
    """
    try:
        claimed = await service.claim_findings_by_patterns(
            patterns=patterns,
            limit=limit,
            claimed_by=claimed_by,
        )
    except Exception as e:
        logger.error("ViolationRemediatorWorker: failed to load findings: %s", e)
        return []

    if not claimed:
        return []

    mappable: list[dict[str, Any]] = []
    unmappable_ids: list[str] = []
    for finding in claimed:
        rule = finding["payload"].get("check_id") or finding["payload"].get("rule", "")
        if remediation_map.get(rule):
            mappable.append(finding)
        else:
            unmappable_ids.append(_entry_id(finding))

    if unmappable_ids:
        try:
            released = await service.release_claimed_entries(unmappable_ids)
            logger.info(
                "ViolationRemediatorWorker: released %d/%d unmappable findings "
                "at claim time",
                released,
                len(unmappable_ids),
            )
        except Exception as e:
            logger.error(
                "ViolationRemediatorWorker: failed to release unmappable "
                "findings at claim time: %s",
                e,
            )

    return mappable


# ID: 270f785d-0bab-418f-8c0d-2a919de92e9b
async def resolve_entries(
    service: Any,
    entry_ids: list[str],
    proposal_id: str,
) -> int:
    """Mark subsumed entries 'resolved' with the subsuming proposal_id on payload.

    Used by the dedup-subsume branch — see ADR-015 D4. Routes to
    BlackboardService.resolve_entries_for_proposal, the dedicated mirror of
    defer_entries_to_proposal for this path.

    Returns count of entries resolved. Fail-soft on service error.
    """
    if not entry_ids:
        return 0
    try:
        return await service.resolve_entries_for_proposal(entry_ids, proposal_id)
    except Exception as e:
        logger.error("ViolationRemediatorWorker: failed to resolve entries: %s", e)
        return 0


# ID: 145f905f-b1ac-4616-9bcc-6a4f0159afda
async def defer_to_proposal(
    service: Any,
    entry_ids: list[str],
    proposal_id: str,
) -> int:
    """Transition entries to 'deferred_to_proposal' with proposal_id on payload.

    Happy-path terminal transition for findings consumed into a newly-
    created proposal — CORE-Finding.md §7 row 4 and ADR-010. The §7a
    revival contract in ProposalStateManager.mark_failed depends on this
    linkage.

    Returns count of entries deferred. Fail-soft: a revival-layer failure
    here does not reverse the caller's proposal_created accounting.
    """
    if not entry_ids:
        return 0
    try:
        return await service.defer_entries_to_proposal(entry_ids, proposal_id)
    except Exception as e:
        logger.error(
            "ViolationRemediatorWorker: failed to defer entries to proposal %s: %s",
            proposal_id,
            e,
        )
        return 0


# ID: 2f3a6a63-bb19-410a-9497-1433e0811bf9
async def release_entries(service: Any, entry_ids: list[str]) -> int:
    """Release claimed entries back to 'open' by id.

    Used when proposal creation fails and findings need to be retry-
    eligible on the next run. Returns count of entries released.
    Fail-soft on service error.
    """
    if not entry_ids:
        return 0
    try:
        return await service.release_claimed_entries(entry_ids)
    except Exception as e:
        logger.error("ViolationRemediatorWorker: failed to release entries: %s", e)
        return 0


# ID: 75f8df09-f542-43fc-8506-85b7a1059be1
async def release_unmappable(service: Any, findings: list[dict[str, Any]]) -> int:
    """Release claimed findings whose rule has no remediation mapping.

    Resolves entry ids and delegates to release_entries — same release
    path, different driver (list of finding dicts rather than ids).
    """
    if not findings:
        return 0
    entry_ids = [_entry_id(f) for f in findings]
    return await release_entries(service, entry_ids)


# ID: 3a2edb4b-98c1-4ab5-ad7e-8f4c31d6bcdd
async def mark_delegated(service: Any, findings: list[dict[str, Any]]) -> int:
    """Mark DELEGATE findings 'indeterminate' — awaiting governor decision.

    Terminal transition for non-automatable findings. Returns count of
    entries marked. Fail-soft on service error.
    """
    if not findings:
        return 0
    entry_ids = [_entry_id(f) for f in findings]
    try:
        return await service.mark_indeterminate(entry_ids)
    except Exception as e:
        logger.error(
            "ViolationRemediatorWorker: failed to mark delegated entries: %s", e
        )
        return 0
