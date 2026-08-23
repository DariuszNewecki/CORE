# src/shared/models/validated_remediation_candidate.py
"""
ValidatedRemediationCandidate — the frozen, privileged-construction contract
between a passed ``assisted.validate_diff`` run and a human-gated DRAFT
proposal (ADR-154 D2).

The bytes validated, reviewed and approved must be exactly the bytes
executed. This dataclass is the immutable handoff object: probabilistic
generation -> deterministic validated candidate -> immutable proposal
payload -> human authorization -> deterministic execution.

Construction is privileged: only
``body.services.validated_candidate_service.build_validated_candidate`` may
construct one, and only from a persisted, successful ``assisted.validate_diff``
run recorded in ``core.fix_runs`` — never from a caller-supplied
``validation_results``. Callers outside the trusted validation service
should never instantiate this type directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
# ID: 63e37ea9-1970-4e24-beee-93da7d5c07cb
class ValidatedRemediationCandidate:
    """An immutable record of a cleared ``assisted.validate_diff`` run.

    See ADR-154 D2. Every field is derived from the persisted
    ``core.fix_runs`` row of the named validation run — never asserted by a
    caller.

    Attributes:
        candidate_id: Fresh identifier minted at construction time.
        patch: The exact unified diff that was validated.
        patch_digest: sha256 of ``patch`` — binds approval to these exact
            bytes (ADR-109 mechanism §4).
        production_set: The touched repo-relative paths the validation run
            observed (the eventual commit set, ADR-101 D2).
        validated_base_sha: The exact commit SHA of the hermetic worktree
            ``assisted.validate_diff`` actually validated against — not a
            later read of production HEAD.
        validation_checks: The check names the validation run declared.
        validation_results: The recorded ``{check: bool}`` verdict map.
        finding_ids: The canonical Blackboard finding ID(s) this candidate
            backs.
        rule_ids: The rule ID(s) those findings fired on.
        created_at: When this candidate was constructed.
    """

    candidate_id: str
    patch: str
    patch_digest: str
    production_set: list[str]
    validated_base_sha: str
    validation_checks: list[str]
    validation_results: dict[str, bool]
    finding_ids: list[str]
    rule_ids: list[str]
    created_at: datetime


# ID: 39a1984b-2e62-476c-81d7-beda8aedf80c
class CandidateConstructionError(Exception):
    """Raised when a ``ValidatedRemediationCandidate`` cannot be constructed.

    Signals a precondition failure on the named validation run (unknown run,
    wrong action, not a passing/completed verdict, patch-byte mismatch, or
    missing base-SHA evidence) — the caller should surface this verbatim
    rather than treat it as a server fault.
    """
