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
    _CONSTRUCTOR_TOKEN,
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
    subject_files: list[str] | None = None,
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

    ADR-154 D3 hardening: *rule_ids* must exactly match the set the named
    run actually validated (``data['finding_rules']``, populated by
    ``assisted.validate_diff`` itself — never caller-asserted). Without this
    check a caller could validate rules A+B and construct a candidate
    claiming only A (understating what was checked) or claiming A+C
    (overstating it — C was never validated). Either way the candidate would
    misrepresent the gate ADR-109 approval keys on. *subject_files*, when
    supplied, is checked the same way against the run's persisted
    ``data['subject_files']`` — which original finding subjects the run
    treated as guarded.

    Raises:
        CandidateConstructionError: the named run does not exist, is not an
            ``assisted.validate_diff`` run, did not complete successfully,
            the supplied patch does not match the validated bytes, the run
            recorded no ``validated_base_sha``, or *rule_ids*/*subject_files*
            do not exactly match what the run actually validated.
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

    persisted_rule_ids = set(data.get("finding_rules") or [])
    if set(rule_ids) != persisted_rule_ids:
        raise CandidateConstructionError(
            f"Run {validation_run_id} validated rule set "
            f"{sorted(persisted_rule_ids)!r} but caller supplied "
            f"{sorted(set(rule_ids))!r} — a candidate must claim exactly "
            "the rules the run actually validated, no more and no fewer."
        )

    if subject_files is not None:
        persisted_subject_files = set(data.get("subject_files") or [])
        if set(subject_files) != persisted_subject_files:
            raise CandidateConstructionError(
                f"Run {validation_run_id} validated subject_files "
                f"{sorted(persisted_subject_files)!r} but caller supplied "
                f"{sorted(set(subject_files))!r}."
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
        _construction_token=_CONSTRUCTOR_TOKEN,
    )
