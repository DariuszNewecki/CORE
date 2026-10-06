# src/will/remediation/finding_state.py
"""
Finding-state helpers for ViolationExecutorWorker's unmapped-rule path.

Extracted from ViolationExecutorWorker (ADR-095 modularity.class_too_large,
governor inbox) as a pure move: claim, release, abandon, inherited
attempt-count query and cap delegation of audit-violation findings. Each
function is a thin wrapper over BlackboardService obtained from
service_registry — status UPDATEs and reads only. No function here INSERTs
a blackboard row: posting stays on the Worker (architecture.blackboard.
worker_only_inserts), so _post_blast_bound_finding remains on the worker.

Every function swallows service errors and logs them, returning a safe
default — the same contract the worker methods had.

LAYER: will/remediation — non-Worker helper. Imports no GitService
(architecture.boundary.remediation_write_access).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: dfc11acf-c293-4b55-b9fa-882c7b699ebe
async def claim_unmapped_findings(
    mapped_rule_ids: set[str], *, claimed_by: UUID, limit: int
) -> list[dict[str, Any]]:
    """Atomically claim open audit-violation findings for unmapped rules."""
    try:
        from body.services.service_registry import service_registry
        from shared.infrastructure.intent.audit_namespaces import (
            audit_violation_like_patterns,
        )
        from will.audit_violation.filter import is_autonomously_remediable_target

        svc = await service_registry.get_blackboard_service()
        claimed = await svc.claim_unmapped_violation_findings(
            mapped_rule_ids=mapped_rule_ids,
            patterns=audit_violation_like_patterns(),
            limit=limit,
            claimed_by=claimed_by,
        )
        # The ceremony rewrites Python source only; a finding on any other
        # target goes to the governor instead of failing the ceremony.
        non_remediable = [
            f
            for f in claimed
            if not is_autonomously_remediable_target(
                str((f.get("payload") or {}).get("file_path") or ".py")
            )
        ]
        if non_remediable:
            await svc.mark_indeterminate([str(f["id"]) for f in non_remediable])
        return [f for f in claimed if f not in non_remediable]
    except Exception as exc:
        logger.error(
            "ViolationExecutorWorker: claim_unmapped_violation_findings failed — %s",
            exc,
        )
        return []


# ID: 84ef02d8-0ea1-4d5f-be0a-3f84b73134c4
async def release_findings(findings: list[dict[str, Any]]) -> None:
    """Release claimed findings back to open status."""
    try:
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        entry_ids = [str(f["id"]) for f in findings]
        await svc.release_claimed_entries(entry_ids)
    except Exception as exc:
        logger.error(
            "ViolationExecutorWorker: release_claimed_entries failed — %s", exc
        )


# ID: 5c8b0734-b58f-49f8-b294-c926e87eda7c
async def abandon_findings(findings: list[dict[str, Any]]) -> None:
    """Abandon findings after an unrecoverable ceremony failure.

    Increments remediation_attempt_count so the circuit breaker can detect
    exhaustion across finding-renewal cycles (ADR-104 D9 unmapped-rule path).
    """
    try:
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        entry_ids = [str(f["id"]) for f in findings]
        await svc.abandon_entries_and_increment_attempt_count(entry_ids)
    except Exception as exc:
        logger.error(
            "ViolationExecutorWorker: abandon_entries_and_increment failed — %s",
            exc,
        )


# ID: 1f2e12a7-87a3-40be-9524-d60744a44d9d
async def query_file_attempt_count(file_path: str) -> int:
    """Return the highest remediation_attempt_count from abandoned findings
    for this file_path. Returns 0 on error or when no abandoned findings exist."""
    try:
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.query_max_attempt_count_by_file_path(file_path)
    except Exception as exc:
        logger.warning(
            "ViolationExecutorWorker: could not query inherited count "
            "for '%s': %s — defaulting to 0",
            file_path,
            exc,
        )
        return 0


# ID: 00084f67-3d11-4cb3-8269-d3c3fb7f25ef
async def delegate_capped_findings(
    entry_ids: list[str], count: int, file_path: str
) -> None:
    """Delegate findings at the remediation cap to the governor, stamping
    count and the last ceremony failure for this file (ADR-104 D9 as
    amended 2026-10-03)."""
    try:
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        last = await svc.fetch_latest_report_payload(
            f"audit.remediation.failed::{file_path}"
        )
        await svc.delegate_remediation_capped_findings(
            entry_ids,
            count,
            {
                "reason": "failure_cap_delegated",
                "detail": (last or {}).get("reason")
                or "LLM remediation ceremony attempts exhausted for this file",
                "attempted_actions": "llm_remediation_ceremony",
                "attempt_count": count,
            },
        )
    except Exception as exc:
        logger.error(
            "ViolationExecutorWorker: delegate_capped_findings failed — %s", exc
        )
