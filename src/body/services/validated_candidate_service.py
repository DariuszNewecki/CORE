# src/body/services/validated_candidate_service.py
"""
Trusted validation / candidate-construction service (ADR-154 D2).

The single privileged constructor of ``ValidatedRemediationCandidate``. This
is the Body-owned home of the check that used to live inline in
``api.v1.lane_routes.propose_diff``: re-read the persisted verdict of a named
``assisted.validate_diff`` run from ``core.fix_runs`` — never trust a
caller's claim that validation passed — confirm the submitted patch matches
the exact bytes that were validated, and only then hand back an immutable
candidate.

Layer: body/services — infrastructure service. Session opened via
ServiceRegistry.session(), same pattern as
``will.autonomy.violation_remediator_proposal``. No LLM calls, no file
writes.
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

from sqlalchemy import text

from body.services.service_registry import service_registry
from shared.logger import getLogger
from shared.models.validated_remediation_candidate import (
    CandidateConstructionError,
    ValidatedRemediationCandidate,
)


logger = getLogger(__name__)

_VALIDATE_ACTION_ID = "assisted.validate_diff"


# ID: fa587c6c-9968-4215-85b1-3ec4e537702d
async def build_validated_candidate(
    *,
    finding_ids: list[str],
    rule_ids: list[str],
    patch: str,
    validation_run_id: str,
) -> ValidatedRemediationCandidate:
    """Construct a ``ValidatedRemediationCandidate`` from a passed validation run.

    The only sanctioned way to obtain a ``ValidatedRemediationCandidate``.
    Re-reads ``core.fix_runs`` for *validation_run_id*, verifies the row is a
    completed, passing ``assisted.validate_diff`` run, confirms *patch*'s
    sha256 matches the digest recorded at validation time (ADR-109 mechanism
    §4 — an agent who edits the diff after validating cannot ride a stale
    PASS), and requires the run to have recorded ``validated_base_sha`` —
    the exact commit SHA of the hermetic worktree the run validated against
    (ADR-154 D2), not a later read of production HEAD.

    Raises:
        CandidateConstructionError: the named run does not exist, is not an
            ``assisted.validate_diff`` run, did not complete successfully,
            the supplied patch does not match the validated bytes, or the
            run recorded no ``validated_base_sha``.
    """
    async with service_registry.session() as session:
        row = (
            (
                await session.execute(
                    text(
                        """
                    SELECT fix_id, status, result
                      FROM core.fix_runs
                     WHERE id = cast(:rid as uuid)
                    """
                    ),
                    {"rid": validation_run_id},
                )
            )
            .mappings()
            .first()
        )

    if row is None:
        raise CandidateConstructionError(f"Unknown validation run: {validation_run_id}")
    if row["fix_id"] != _VALIDATE_ACTION_ID:
        raise CandidateConstructionError(
            f"Run {validation_run_id} is not an {_VALIDATE_ACTION_ID} run "
            f"(was {row['fix_id']!r})."
        )

    result: dict[str, Any] = row["result"] or {}
    data: dict[str, Any] = result.get("data") or {}
    if row["status"] != "completed" or not result.get("ok"):
        raise CandidateConstructionError(
            "Validation did not pass; diff is not approvable. Re-run "
            "assisted.validate_diff on the current patch."
        )

    submitted_sha = hashlib.sha256(patch.encode("utf-8")).hexdigest()
    recorded_sha = data.get("patch_sha256")
    if recorded_sha != submitted_sha:
        raise CandidateConstructionError(
            "Submitted patch does not match the validated diff; "
            "re-run validation on the current patch."
        )

    validated_base_sha = data.get("validated_base_sha")
    if not validated_base_sha:
        raise CandidateConstructionError(
            f"Validation run {validation_run_id} recorded no "
            "validated_base_sha; cannot bind approval to a base commit."
        )

    validation_results: dict[str, bool] = data.get("validation_results") or {}

    logger.info(
        "validated_candidate: constructed from run %s (base_sha=%s, "
        "production_set=%d file(s), findings=%d)",
        validation_run_id,
        validated_base_sha,
        len(data.get("production_set") or []),
        len(finding_ids),
    )

    return ValidatedRemediationCandidate(
        candidate_id=str(uuid4()),
        patch=patch,
        patch_digest=submitted_sha,
        production_set=list(data.get("production_set") or []),
        validated_base_sha=validated_base_sha,
        validation_checks=list(validation_results.keys()),
        validation_results=validation_results,
        finding_ids=list(finding_ids),
        rule_ids=list(rule_ids),
        created_at=datetime.now(UTC),
    )
