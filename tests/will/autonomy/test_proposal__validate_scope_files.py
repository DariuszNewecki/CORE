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
from will.autonomy.proposal import Proposal, ProposalScope


_SCOPE_FILES_ERROR = "Proposal must declare at least one file in scope.files"


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
