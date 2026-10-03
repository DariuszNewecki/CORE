"""ADR-133 D4 no-gap path hands test.runner.missing back to re-audit (2026-10-03).

Traced loop (var/reports/test-coverage-loop-trace-20261003.md): a
``test.runner.missing`` finding whose governed test file had since been
written was claimed by TestRemediatorWorker every ~60 s, the gap evaluator
correctly found no gaps, and the finding was released back to ``open`` —
where no adjudication path ever looks — so it was re-claimed forever (72
rows, 2,334 cycles for one file in two days). The no-gap path now returns the
finding to ``awaiting_reaudit``, and TestRunnerSensor's existing quarantine
drain decides: resolve when the source is covered, reopen when still missing.
``test.runner.failure`` keeps the release path (a separate lifecycle case).
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tests.will.workers.test_test_remediator_circuit_breaker import (
    _CAP_N,
    _make_worker,
    _patch_operations,
)


_MISSING = {
    "id": "m-1",
    "subject": "python::test.runner.missing::src/foo/bar.py",
    "payload": {"source_file": "src/foo/bar.py"},
}
_FAILURE = {
    "id": "f-1",
    "subject": "python::test.runner.failure::src/foo/bar.py",
    "payload": {"source_file": "src/foo/bar.py"},
}


async def _run_no_gap(findings: list[dict]) -> dict:  # type: ignore[type-arg]
    worker = _make_worker()
    complete = MagicMock(ok=True, data={"gaps": [], "covered_count": 2})
    patches = _patch_operations(
        **{
            "will.workers.test_remediator.worker._load_open_findings": AsyncMock(
                return_value=findings
            ),
            "will.workers.test_remediator.worker._return_for_reaudit": AsyncMock(
                side_effect=lambda ids: len(ids)
            ),
            "will.workers.test_remediator.worker._release_entries": AsyncMock(
                side_effect=lambda ids: len(ids)
            ),
            "body.evaluators.test_gap_evaluator.TestGapEvaluator": MagicMock(
                return_value=MagicMock(execute=AsyncMock(return_value=complete))
            ),
        }
    )
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "shared.infrastructure.intent.operational_config.load_operational_config",
                return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=_CAP_N)),
            )
        )
        for target, mock in patches.items():
            stack.enter_context(patch(target, mock))
        await worker.run()  # type: ignore[attr-defined]
    return patches


async def test_no_gap_returns_missing_finding_for_reaudit_not_open() -> None:
    patches = await _run_no_gap([_MISSING])
    patches[
        "will.workers.test_remediator.worker._return_for_reaudit"
    ].assert_awaited_once_with(["m-1"])
    patches[
        "will.workers.test_remediator.worker._release_entries"
    ].assert_awaited_once_with([])


async def test_no_gap_leaves_failure_findings_on_the_release_path() -> None:
    patches = await _run_no_gap([_MISSING, _FAILURE])
    patches[
        "will.workers.test_remediator.worker._return_for_reaudit"
    ].assert_awaited_once_with(["m-1"])
    patches[
        "will.workers.test_remediator.worker._release_entries"
    ].assert_awaited_once_with(["f-1"])


@pytest.mark.asyncio
async def test_runner_drain_resolves_covered_and_keeps_still_missing() -> None:
    """The existing drain: a quarantined missing-finding whose source is now
    covered is absent from current_subjects (so it is resolved); one still
    uncovered stays current (so it is reopened)."""
    from will.workers.test_runner_sensor import TestRunnerSensor

    sensor = TestRunnerSensor()
    sensor.post_report = AsyncMock()
    bb = AsyncMock()
    bb.adjudicate_awaiting_reaudit_findings.return_value = {
        "released_subjects": [],
        "resolved_subjects": [],
    }
    bb.fetch_awaiting_reaudit_subjects_by_prefix.return_value = set()
    with (
        patch("body.services.service_registry.service_registry") as registry,
        patch(
            "will.workers.test_runner_sensor.uncovered_source_files",
            return_value={"src/still_missing.py"},
        ),
    ):
        registry.get_blackboard_service = AsyncMock(return_value=bb)
        await sensor._adjudicate_test_quarantine({})

    kwargs = bb.adjudicate_awaiting_reaudit_findings.await_args_list[0].kwargs
    assert kwargs["subject_prefix"] == "python::test.runner.missing"
    current = kwargs["current_violation_subjects"]
    assert "python::test.runner.missing::src/still_missing.py" in current
    assert "python::test.runner.missing::src/foo/bar.py" not in current


@pytest.mark.asyncio
async def test_service_transition_carries_the_reaudit_guard() -> None:
    from contextlib import asynccontextmanager

    from body.services.blackboard_service import BlackboardService
    from body.services.service_registry import ServiceRegistry

    @asynccontextmanager
    async def _ctx(obj):  # type: ignore[no-untyped-def]
        yield obj

    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(rowcount=1))
    session.begin = MagicMock(return_value=_ctx(None))
    with patch.object(ServiceRegistry, "session", return_value=_ctx(session)):
        n = await BlackboardService().return_claimed_entries_for_reaudit(["m-1"])
    assert n == 1
    sql = str(session.execute.await_args.args[0])
    assert "SET status = 'awaiting_reaudit'" in sql
    assert "resolution_mechanism = 'reaudit'" in sql
    assert "status = 'claimed'" in sql
