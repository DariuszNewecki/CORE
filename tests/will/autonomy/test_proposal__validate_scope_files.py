"""Regression test for issue #191: Proposal.validate() must reject empty
scope.files.

ADR-021 D5 punted execution-time enforcement; commit_paths raises ValueError
on empty scope.files at the very end of the success branch and restore_paths
silently no-ops on the failure branch. The investigation in
https://github.com/DariuszNewecki/CORE/issues/191#issuecomment-4380727235
confirmed no upstream check existed. This validates the empty case is
rejected at construction-validation time so the malformed proposal never
reaches the executor.

Tests check inclusion/exclusion of the specific error message in the
error list rather than asserting overall is_valid — sidesteps entanglement
with the other five checks (action-registry lookup, risk presence, etc.).
"""

from __future__ import annotations

# body.atomic must finish loading before will.autonomy.proposal pulls
# in its registry imports — pre-existing body.atomic ↔ will.autonomy
# circular import surfaces during isolated collection otherwise.
import body.atomic  # noqa: F401  -- import-order side effect, not a usage
from will.autonomy.proposal import _SCOPE_FILES_MAX_ITEMS, Proposal, ProposalScope


_SCOPE_FILES_ERROR = "Proposal must declare at least one file in scope.files"
_BLAST_BOUND_FRAGMENT = "exceeding the constitutional blast bound"


# ID: 620a2441-4bb5-4525-ba38-cfcf6556dc19
def test_validate_rejects_empty_scope_files() -> None:
    """Empty scope.files must add the new check-6 error."""
    proposal = Proposal(
        goal="test",
        actions=[],
        scope=ProposalScope(files=[]),
    )
    _, errors = proposal.validate()
    assert _SCOPE_FILES_ERROR in errors, (
        f"empty scope.files should have triggered check 6; got errors={errors!r}"
    )


# ID: 327b94fc-8f1e-4ec6-9372-6f9c6442a3a7
def test_validate_passes_check_six_when_scope_files_populated() -> None:
    """A non-empty scope.files must NOT add the check-6 error.

    Other checks may still fail (this Proposal has no actions, no risk),
    so we don't assert overall is_valid — only that *our* specific check
    is satisfied.
    """
    proposal = Proposal(
        goal="test",
        actions=[],
        scope=ProposalScope(files=["src/foo.py"]),
    )
    _, errors = proposal.validate()
    assert _SCOPE_FILES_ERROR not in errors, (
        f"non-empty scope.files should not have triggered check 6; "
        f"got errors={errors!r}"
    )


# Check 7 — blast-bound on scope.files (2026-05-24 hardening sweep).
# The bound is constitutionally declared in
# .intent/enforcement/contracts/ProposalScope.json files.maxItems and
# mirrored at the module-level constant _SCOPE_FILES_MAX_ITEMS in
# will.autonomy.proposal. These tests use the constant so they stay in
# sync with the source even if the bound is amended.


# ID: 9c2e4f7a-3b1d-4e8a-9f5c-2d6b7a1e5c83
def test_validate_rejects_scope_files_over_blast_bound() -> None:
    """scope.files above _SCOPE_FILES_MAX_ITEMS must add the check-7 error."""
    too_many = [f"src/f{i}.py" for i in range(_SCOPE_FILES_MAX_ITEMS + 1)]
    proposal = Proposal(
        goal="test",
        actions=[],
        scope=ProposalScope(files=too_many),
    )
    _, errors = proposal.validate()
    matches = [e for e in errors if _BLAST_BOUND_FRAGMENT in e]
    assert matches, (
        f"scope.files of size {_SCOPE_FILES_MAX_ITEMS + 1} should have "
        f"triggered check 7 (blast bound); got errors={errors!r}"
    )


# ID: 4f7c1a9e-8b2d-4e6c-9a3f-1d8b5c7e2a4f
def test_validate_passes_check_seven_at_blast_bound() -> None:
    """scope.files exactly at _SCOPE_FILES_MAX_ITEMS must NOT add the check-7 error.

    The bound is inclusive on the allowed side — a proposal touching exactly
    the maximum declared file count is constitutionally valid; only proposals
    above the bound are refused.
    """
    at_limit = [f"src/f{i}.py" for i in range(_SCOPE_FILES_MAX_ITEMS)]
    proposal = Proposal(
        goal="test",
        actions=[],
        scope=ProposalScope(files=at_limit),
    )
    _, errors = proposal.validate()
    matches = [e for e in errors if _BLAST_BOUND_FRAGMENT in e]
    assert not matches, (
        f"scope.files of size {_SCOPE_FILES_MAX_ITEMS} (== bound) should "
        f"not have triggered check 7; got errors={errors!r}"
    )
