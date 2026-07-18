# tests/will/governance/test_coverage_runner_result_contract.py

"""#813: coverage_runner.py's ok-computation read a "success" key neither
remediation service ever returns — both report outcome via "status". Every
run, win or lose, was persisted as failed. Pins the corrected mapping for
both the single-file and batch paths, independent of the write=false gate
(tests/will/governance/test_coverage_runner_write_gate.py, #809).

#814: the underlying remediation call swapped from
will.self_healing.coverage_remediation_service.remediate_coverage_enhanced
(retired) to will.self_healing.symbol_coverage_remediation's
remediate_file_by_symbol / remediate_batch_by_symbol — same "status"-keyed
contract these tests pin, different producer.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from will.governance.coverage_runner import (
    run_and_persist_coverage_batch,
    run_and_persist_coverage_generation,
)


def _context() -> MagicMock:
    context = MagicMock()
    context.cognitive_service = MagicMock()
    return context


async def test_generation_completed_status_persists_as_completed():
    context = _context()
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    with (
        patch("will.governance.coverage_runner.Path.exists", return_value=True),
        patch("will.governance.coverage_runner.Path.is_file", return_value=True),
        patch(
            "will.governance.coverage_runner.remediate_file_by_symbol",
            new=AsyncMock(return_value={"status": "completed", "test_file": "x"}),
        ),
    ):
        await run_and_persist_coverage_generation(
            context, session, run_id=run_id, target_file="src/foo.py", write=True
        )

    last_params = session.execute.await_args_list[-1].args[1]
    assert last_params["status"] == "completed"
    assert "err" not in last_params


async def test_generation_failed_status_persists_as_failed_with_error():
    context = _context()
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    with (
        patch("will.governance.coverage_runner.Path.exists", return_value=True),
        patch("will.governance.coverage_runner.Path.is_file", return_value=True),
        patch(
            "will.governance.coverage_runner.remediate_file_by_symbol",
            new=AsyncMock(return_value={"status": "failed", "error": "boom"}),
        ),
    ):
        await run_and_persist_coverage_generation(
            context, session, run_id=run_id, target_file="src/foo.py", write=True
        )

    last_params = session.execute.await_args_list[-1].args[1]
    assert last_params["status"] == "failed"
    assert last_params["err"] == "boom"


async def test_batch_completed_status_persists_as_completed_regardless_of_per_file_failures():
    """A batch run where some files failed is still an "ok" batch run — the
    top-level status describes whether the loop executed, not per-file
    outcome (that's in "summary"/"results")."""
    context = _context()
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    with patch(
        "will.governance.coverage_runner.remediate_batch_by_symbol",
        new=AsyncMock(
            return_value={
                "status": "completed",
                "processed": 3,
                "results": [],
                "summary": {"success": 1, "failed": 2, "skipped": 0},
            }
        ),
    ):
        await run_and_persist_coverage_batch(
            context, session, run_id=run_id, batch_priority="all", write=True
        )

    last_params = session.execute.await_args_list[-1].args[1]
    assert last_params["status"] == "completed"
    assert "err" not in last_params


async def test_batch_no_candidates_status_persists_as_completed():
    context = _context()
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    with patch(
        "will.governance.coverage_runner.remediate_batch_by_symbol",
        new=AsyncMock(
            return_value={
                "status": "no_candidates",
                "processed": 0,
                "results": [],
                "summary": {"success": 0, "failed": 0, "skipped": 0},
            }
        ),
    ):
        await run_and_persist_coverage_batch(
            context, session, run_id=run_id, batch_priority="all", write=True
        )

    last_params = session.execute.await_args_list[-1].args[1]
    assert last_params["status"] == "completed"


async def test_batch_unrecognized_status_persists_as_failed():
    context = _context()
    session = AsyncMock()
    session.execute = AsyncMock()
    session.commit = AsyncMock()
    run_id = uuid4()

    with patch(
        "will.governance.coverage_runner.remediate_batch_by_symbol",
        new=AsyncMock(return_value={"raw": "unexpected shape"}),
    ):
        await run_and_persist_coverage_batch(
            context, session, run_id=run_id, batch_priority="all", write=True
        )

    last_params = session.execute.await_args_list[-1].args[1]
    assert last_params["status"] == "failed"
