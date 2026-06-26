# tests/body/services/test_coherence_service_cleanup_verbs.py

"""Integration tests: CoherenceService cleanup verbs (issue #496 / ADR-067 D6).

Covers ``repair_unreviewed_counts`` and ``supersede_run``. All cases
exercise the live test DB so the SQL is real, not mocked. Direct UPDATEs
on the candidates table simulate the off-path mutation that produced the
2026-05-31 drift this work fixes.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.coherence_service import CoherenceService
from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session

pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Bind the registry to the test DB session factory."""
    service_registry.prime(get_session)


async def _seed_candidate(
    service: CoherenceService,
    run_id: str,
    claim: str,
) -> str:
    return await service.add_candidate(
        run_id=run_id,
        relation="R1_SCOPED",
        documents=["a.md", "b.md"],
        claim=claim,
        rationale="cleanup-verbs test fixture",
    )


async def _off_path_dismiss(
    session: AsyncSession,
    candidate_id: str,
    note: str = "off-path",
) -> None:
    """Mimic the off-path bulk-dismiss that caused the 2026-05-31 drift.

    Writes triage_decision/triage_note/triaged_at directly, deliberately
    bypassing ``triage_candidate`` so the parent run's denormalized
    ``unreviewed_count`` is left untouched.
    """
    await session.execute(
        text(
            "UPDATE core.coherence_candidates "
            "SET triage_decision = 'dismissed', "
            "    triage_note = :note, "
            "    triaged_at = now() "
            "WHERE candidate_id = :cid"
        ),
        {"cid": candidate_id, "note": note},
    )
    await session.commit()


async def _run_row(session: AsyncSession, run_id: str) -> dict:
    result = await session.execute(
        text(
            "SELECT run_status, candidate_count, unreviewed_count "
            "FROM core.coherence_runs WHERE run_id = :rid"
        ),
        {"rid": run_id},
    )
    row = result.fetchone()
    assert row is not None, f"run {run_id} not found"
    return {
        "run_status": row[0],
        "candidate_count": int(row[1]),
        "unreviewed_count": int(row[2]),
    }


async def _delete_run(session: AsyncSession, run_id: str) -> None:
    await session.execute(
        text("DELETE FROM core.coherence_candidates WHERE run_id = :rid"),
        {"rid": run_id},
    )
    await session.execute(
        text("DELETE FROM core.coherence_runs WHERE run_id = :rid"),
        {"rid": run_id},
    )
    await session.commit()


# --- repair_unreviewed_counts -------------------------------------------------


async def test_repair_counts_corrects_off_path_drift(
    db_session: AsyncSession,
) -> None:
    """Off-path dismissal leaves unreviewed_count overcounted; repair fixes it."""
    service = CoherenceService(db_session)
    run_id = await service.create_run(trigger="manual")
    try:
        c1 = await _seed_candidate(service, run_id, "claim-1")
        await _seed_candidate(service, run_id, "claim-2")
        await _seed_candidate(service, run_id, "claim-3")

        # Dismiss one candidate off-path; unreviewed_count stays at 3.
        await _off_path_dismiss(db_session, c1)
        before = await _run_row(db_session, run_id)
        assert before["unreviewed_count"] == 3
        assert before["run_status"] == "open"

        deltas = await service.repair_unreviewed_counts()

        ours = [d for d in deltas if d["run_id"] == run_id]
        assert len(ours) == 1
        assert ours[0]["old_count"] == 3
        assert ours[0]["new_count"] == 2
        assert ours[0]["closed"] is False

        after = await _run_row(db_session, run_id)
        assert after["unreviewed_count"] == 2
        assert after["run_status"] == "open"
    finally:
        await _delete_run(db_session, run_id)


async def test_repair_counts_closes_run_when_all_off_path_triaged(
    db_session: AsyncSession,
) -> None:
    """A run whose candidates were all dismissed off-path is closed by repair."""
    service = CoherenceService(db_session)
    run_id = await service.create_run(trigger="manual")
    try:
        c1 = await _seed_candidate(service, run_id, "claim-1")
        c2 = await _seed_candidate(service, run_id, "claim-2")
        await _off_path_dismiss(db_session, c1)
        await _off_path_dismiss(db_session, c2)

        deltas = await service.repair_unreviewed_counts()
        ours = next(d for d in deltas if d["run_id"] == run_id)
        assert ours["new_count"] == 0
        assert ours["closed"] is True

        after = await _run_row(db_session, run_id)
        assert after["unreviewed_count"] == 0
        assert after["run_status"] == "closed"
    finally:
        await _delete_run(db_session, run_id)


async def test_repair_counts_is_idempotent_on_clean_run(
    db_session: AsyncSession,
) -> None:
    """A run already in sync repairs to itself with delta = 0."""
    service = CoherenceService(db_session)
    run_id = await service.create_run(trigger="manual")
    try:
        await _seed_candidate(service, run_id, "claim-1")

        first = await service.repair_unreviewed_counts()
        second = await service.repair_unreviewed_counts()

        ours_first = next(d for d in first if d["run_id"] == run_id)
        ours_second = next(d for d in second if d["run_id"] == run_id)
        assert ours_first["old_count"] == ours_first["new_count"] == 1
        assert ours_second["old_count"] == ours_second["new_count"] == 1
        assert ours_first["closed"] is False
        assert ours_second["closed"] is False
    finally:
        await _delete_run(db_session, run_id)


# --- supersede_run ------------------------------------------------------------


async def test_supersede_dismisses_and_closes_old_run(
    db_session: AsyncSession,
) -> None:
    """End-to-end happy path: old's unreviewed candidates dismissed with note."""
    service = CoherenceService(db_session)
    old_id = await service.create_run(trigger="manual")
    canonical_id = await service.create_run(trigger="manual")
    try:
        for n in range(3):
            await _seed_candidate(service, old_id, f"old-claim-{n}")
        await _seed_candidate(service, canonical_id, "canonical-claim")

        note = "superseded by canonical full run (test fixture)"
        result = await service.supersede_run(
            old_run_id=old_id,
            canonical_run_id=canonical_id,
            note=note,
        )

        assert result["dismissed_count"] == 3
        assert result["old_run_closed"] is True
        assert result["canonical_old_count"] == 1
        assert result["canonical_new_count"] == 1
        # Canonical was created after old → no warning expected.
        assert result["canonical_age_warning"] is False

        old_after = await _run_row(db_session, old_id)
        assert old_after["run_status"] == "closed"
        assert old_after["unreviewed_count"] == 0

        # Every dismissed candidate carries the note.
        rows = await db_session.execute(
            text(
                "SELECT triage_decision, triage_note "
                "FROM core.coherence_candidates WHERE run_id = :rid"
            ),
            {"rid": old_id},
        )
        for triage_decision, triage_note in rows.fetchall():
            assert triage_decision == "dismissed"
            assert triage_note == note
    finally:
        await _delete_run(db_session, old_id)
        await _delete_run(db_session, canonical_id)


async def test_supersede_rejects_missing_runs(db_session: AsyncSession) -> None:
    service = CoherenceService(db_session)
    real_id = await service.create_run(trigger="manual")
    try:
        # Missing canonical.
        with pytest.raises(ValueError, match="canonical_run_id not found"):
            await service.supersede_run(
                old_run_id=real_id,
                canonical_run_id="00000000-0000-0000-0000-000000000000",
                note="x",
            )
        # Missing old.
        with pytest.raises(ValueError, match="old_run_id not found"):
            await service.supersede_run(
                old_run_id="00000000-0000-0000-0000-000000000000",
                canonical_run_id=real_id,
                note="x",
            )
    finally:
        await _delete_run(db_session, real_id)


async def test_supersede_rejects_already_closed_old_run(
    db_session: AsyncSession,
) -> None:
    service = CoherenceService(db_session)
    old_id = await service.create_run(trigger="manual")
    canonical_id = await service.create_run(trigger="manual")
    try:
        # Manually close the old run so the open-guard fires.
        await db_session.execute(
            text(
                "UPDATE core.coherence_runs SET run_status = 'closed' "
                "WHERE run_id = :rid"
            ),
            {"rid": old_id},
        )
        await db_session.commit()

        with pytest.raises(ValueError, match="is not open"):
            await service.supersede_run(
                old_run_id=old_id,
                canonical_run_id=canonical_id,
                note="x",
            )
    finally:
        await _delete_run(db_session, old_id)
        await _delete_run(db_session, canonical_id)


async def test_supersede_age_warning_when_canonical_not_newer(
    db_session: AsyncSession,
) -> None:
    """Canonical not newer than old → result flags warning but proceeds."""
    service = CoherenceService(db_session)
    canonical_id = await service.create_run(trigger="manual")
    old_id = await service.create_run(trigger="manual")  # created after canonical
    try:
        await _seed_candidate(service, old_id, "old-claim")

        result = await service.supersede_run(
            old_run_id=old_id,
            canonical_run_id=canonical_id,
            note="ordering deliberately inverted",
        )

        assert result["canonical_age_warning"] is True
        assert result["dismissed_count"] == 1
        old_after = await _run_row(db_session, old_id)
        assert old_after["run_status"] == "closed"
    finally:
        await _delete_run(db_session, old_id)
        await _delete_run(db_session, canonical_id)


async def test_supersede_repairs_canonical_count_drift(
    db_session: AsyncSession,
) -> None:
    """Canonical's own drift is repaired as part of supersede."""
    service = CoherenceService(db_session)
    old_id = await service.create_run(trigger="manual")
    canonical_id = await service.create_run(trigger="manual")
    try:
        await _seed_candidate(service, old_id, "old-claim")
        c_canonical = await _seed_candidate(service, canonical_id, "canonical-claim")
        # Off-path dismiss on canonical drifts its count to 1 (true count: 0).
        await _off_path_dismiss(db_session, c_canonical)

        before = await _run_row(db_session, canonical_id)
        assert before["unreviewed_count"] == 1

        result = await service.supersede_run(
            old_run_id=old_id,
            canonical_run_id=canonical_id,
            note="cleanup with canonical drift",
        )

        assert result["canonical_old_count"] == 1
        assert result["canonical_new_count"] == 0

        after = await _run_row(db_session, canonical_id)
        assert after["unreviewed_count"] == 0
    finally:
        await _delete_run(db_session, old_id)
        await _delete_run(db_session, canonical_id)
