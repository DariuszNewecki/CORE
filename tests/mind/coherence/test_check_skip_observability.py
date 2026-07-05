# tests/mind/coherence/test_check_skip_observability.py
"""Tests for CCC skip-state observability — closes #624.

Verifies that SAMECONCERN and R1_SCOPED surface an explicit ``status: "skipped"``
entry in the check manifest rather than silently returning zero candidates when:

1. ``claims_service`` is None (not injected).
2. ``is_seeded()`` returns False (collection not bootstrapped — seed gap).

Previously both cases were invisible: either the checks were never added to the
run list (case 1) or they returned an empty list indistinguishable from
``status: "ok", "emitted": 0`` (case 2). The fix uses ``CheckSkipped`` to
propagate the reason through to the manifest.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mind.coherence.checks.base import CheckSkipped


# ── CheckSkipped contract ─────────────────────────────────────────────────────


# ID: 841c8c7a-0260-44ce-b9eb-657dc7c865e3
def test_checkskipped_is_exception_subclass() -> None:
    """CheckSkipped must be an Exception so it can be raised from run()."""
    assert issubclass(CheckSkipped, Exception)


# ID: 1af27a6d-95ee-4c65-9688-4f544a9592b2
def test_checkskipped_carries_reason() -> None:
    """str(exc) exposes the reason string for manifest recording."""
    exc = CheckSkipped("seed_gap")
    assert str(exc) == "seed_gap"


# ── SameConcernCheck raises CheckSkipped when not seeded ─────────────────────


# ID: 56a1b962-eeb5-43fb-bee0-a308e5e93dad
@pytest.mark.asyncio
async def test_sameconcern_raises_checkskipped_when_not_seeded() -> None:
    """SameConcernCheck.run() raises CheckSkipped('seed_gap') when not seeded."""
    from mind.coherence.checks.sameconcern import SameConcernCheck

    claims_service = AsyncMock()
    claims_service.is_seeded.return_value = False

    check = SameConcernCheck(
        repo_root=Path("/tmp/fake"),
        register=MagicMock(),
        claims_service=claims_service,
        cognitive_service=MagicMock(),
    )

    with pytest.raises(CheckSkipped) as exc_info:
        await check.run()

    assert str(exc_info.value) == "seed_gap"


# ── R1ScopedCheck raises CheckSkipped when not seeded ────────────────────────


# ID: 087bdb23-aa00-40f6-9302-ba9645692ef8
@pytest.mark.asyncio
async def test_r1scoped_raises_checkskipped_when_not_seeded() -> None:
    """R1ScopedCheck.run() raises CheckSkipped('seed_gap') when not seeded.

    We need at least one declared pair (otherwise run() returns [] before
    reaching the is_seeded() gate). We patch _declared_pairs() to return one.
    """
    from mind.coherence.checks.r1_scoped import R1ScopedCheck

    claims_service = AsyncMock()
    claims_service.is_seeded.return_value = False

    check = R1ScopedCheck(
        repo_root=Path("/tmp/fake"),
        register=MagicMock(),
        claims_service=claims_service,
        cognitive_service=MagicMock(),
    )
    # Inject a fake pair so we reach the is_seeded gate.
    check._declared_pairs = MagicMock(
        return_value=[(".specs/decisions/ADR-001.md", ".specs/decisions/ADR-002.md")]
    )

    with pytest.raises(CheckSkipped) as exc_info:
        await check.run()

    assert str(exc_info.value) == "seed_gap"


# ── Checker records explicit skipped status when claims_service is None ───────


# ID: 42ea8f34-c829-4598-ac64-fd55df84c20a
@pytest.mark.asyncio
async def test_checker_records_skipped_when_claims_service_none() -> None:
    """_dispatch_checks() records SAMECONCERN/R1_SCOPED as skipped, not absent.

    When claims_service is None, the old code silently omitted both checks from
    the status dict. Now they must appear with status='skipped'.
    """
    from mind.coherence.checker import CoherenceChecker

    coherence_service = AsyncMock()
    coherence_service.add_candidate = AsyncMock()

    checker = CoherenceChecker(
        cognitive_service=MagicMock(),
        coherence_service=coherence_service,
        repo_root=Path("/tmp/fake"),
        claims_service=None,  # the condition under test
    )

    # Patch all structural checks to return no candidates so we isolate the
    # claims_service=None branch.
    _no_candidates = AsyncMock(return_value=[])

    with (
        patch(
            "mind.coherence.checks.dispatch_parity.DispatchParityCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.row2_grounding.Row2GroundingCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.row3_citation.Row3CitationCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.row4_naming.Row4NamingCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.vocabulary.VocabularyCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.specgap.SpecGapCheck.run",
            new=_no_candidates,
        ),
        patch(
            "shared.infrastructure.intent.intent_repository.get_intent_repository",
            return_value=MagicMock(),
        ),
        patch(
            "shared.governance.coherence_harvester.NormativeMarkerRegister.from_intent",
            return_value=MagicMock(),
        ),
    ):
        status = await checker._dispatch_checks(run_id="test-run-id")

    assert "SAMECONCERN" in status, "SAMECONCERN must appear in status"
    assert "R1_SCOPED" in status, "R1_SCOPED must appear in status"
    assert status["SAMECONCERN"]["status"] == "skipped"
    assert status["R1_SCOPED"]["status"] == "skipped"
    assert status["SAMECONCERN"]["reason"] == "claims_service_not_injected"
    assert status["R1_SCOPED"]["reason"] == "claims_service_not_injected"
    assert status["SAMECONCERN"]["emitted"] == 0
    assert status["R1_SCOPED"]["emitted"] == 0


# ── Checker records skipped (not error) when check raises CheckSkipped ────────


# ID: 8a1059fc-3f8b-4f49-9065-18d1db608b59
@pytest.mark.asyncio
async def test_checker_records_skipped_not_error_for_checkskipped() -> None:
    """When a check raises CheckSkipped, status is 'skipped', not 'error'.

    A 'seed_gap' is a known precondition absence, not an unexpected failure.
    Recording it as 'error' would flood governor dashboards with false alarms.
    """
    from mind.coherence.checker import CoherenceChecker

    coherence_service = AsyncMock()
    coherence_service.add_candidate = AsyncMock()

    claims_service_mock = AsyncMock()
    claims_service_mock.is_seeded.return_value = False

    checker = CoherenceChecker(
        cognitive_service=MagicMock(),
        coherence_service=coherence_service,
        repo_root=Path("/tmp/fake"),
        claims_service=claims_service_mock,
    )

    _no_candidates = AsyncMock(return_value=[])
    _raise_seed_gap = AsyncMock(side_effect=CheckSkipped("seed_gap"))

    with (
        patch(
            "mind.coherence.checks.dispatch_parity.DispatchParityCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.row2_grounding.Row2GroundingCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.row3_citation.Row3CitationCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.row4_naming.Row4NamingCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.vocabulary.VocabularyCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.specgap.SpecGapCheck.run",
            new=_no_candidates,
        ),
        patch(
            "mind.coherence.checks.sameconcern.SameConcernCheck.run",
            new=_raise_seed_gap,
        ),
        patch(
            "mind.coherence.checks.r1_scoped.R1ScopedCheck.run",
            new=_raise_seed_gap,
        ),
        patch(
            "shared.infrastructure.intent.intent_repository.get_intent_repository",
            return_value=MagicMock(),
        ),
        patch(
            "shared.governance.coherence_harvester.NormativeMarkerRegister.from_intent",
            return_value=MagicMock(),
        ),
    ):
        status = await checker._dispatch_checks(run_id="test-run-id")

    assert status["SAMECONCERN"]["status"] == "skipped"
    assert status["R1_SCOPED"]["status"] == "skipped"
    assert status["SAMECONCERN"]["reason"] == "seed_gap"
    assert status["R1_SCOPED"]["reason"] == "seed_gap"
    # Must not be recorded as 'error'.
    assert "error" not in status["SAMECONCERN"]
    assert "error" not in status["R1_SCOPED"]
