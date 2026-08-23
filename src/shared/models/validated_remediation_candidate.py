# src/shared/models/validated_remediation_candidate.py
"""
ValidatedRemediationCandidate — the frozen, privileged-construction contract
between a passed ``assisted.validate_diff`` run and a human-gated DRAFT
proposal (ADR-154 D2).

The bytes validated, reviewed and approved must be exactly the bytes
executed. This dataclass is the immutable handoff object: probabilistic
generation -> deterministic validated candidate -> immutable proposal
payload -> human authorization -> deterministic execution.

Construction is privileged, and this is structurally enforced, not merely
documented: the dataclass requires a ``_construction_token`` matching the
module-private ``_CONSTRUCTOR_TOKEN`` object below. Only
``body.services.validated_candidate_service.build_validated_candidate``
holds a reference to that token; any other construction attempt — with no
token, the wrong object, or a caller-manufactured stand-in — raises
``CandidateConstructionError`` at construction time. This closes the gap a
plain frozen dataclass leaves open: ``frozen=True`` alone gives immutability
after construction, not privileged construction itself.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


# ID: 39a1984b-2e62-476c-81d7-beda8aedf80c
class CandidateConstructionError(Exception):
    """Raised when a ``ValidatedRemediationCandidate`` cannot be constructed.

    Signals a precondition failure on the named validation run (unknown run,
    wrong action, not a passing/completed verdict, patch-byte mismatch,
    missing base-SHA evidence) or a construction attempt made without the
    privileged token — the caller should surface this verbatim rather than
    treat it as a server fault.
    """


class _ConstructorToken:
    """Opaque, unforgeable marker. Equality is identity — a caller cannot
    manufacture an equivalent instance; only whoever holds the real
    ``_CONSTRUCTOR_TOKEN`` object can pass the guard below."""


_CONSTRUCTOR_TOKEN = _ConstructorToken()
"""The privileged-construction handshake object (ADR-154 D2). Imported by
``body.services.validated_candidate_service`` only — no other module should
import this name."""


@dataclass(frozen=True)
# ID: 63e37ea9-1970-4e24-beee-93da7d5c07cb
class ValidatedRemediationCandidate:
    """An immutable record of a cleared ``assisted.validate_diff`` run.

    See ADR-154 D2. Every field is derived from the persisted
    ``core.fix_runs`` row of the named validation run — never asserted by a
    caller. Construction itself is gated by ``_construction_token`` (module
    docstring) — omitting it or passing anything but the real
    ``_CONSTRUCTOR_TOKEN`` raises ``CandidateConstructionError``.

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
    _construction_token: object = field(repr=False, compare=False)

    def __post_init__(self) -> None:
        if self._construction_token is not _CONSTRUCTOR_TOKEN:
            raise CandidateConstructionError(
                "ValidatedRemediationCandidate may only be constructed by "
                "body.services.validated_candidate_service."
                "build_validated_candidate (ADR-154 D2 privileged "
                "construction) — no other caller may assert validation "
                "evidence."
            )
