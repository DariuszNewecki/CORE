"""CommitReachabilityAuditor.run skips rows that produced no commit.

A proposal that ends in CommitOutcome.NOTHING_TO_COMMIT still gets a
consequence row, with post_execution_sha == pre_execution_sha == HEAD at
the time. That sha is not an Edge 5 link (ADR-019 D3: Execution -> file
changes) -- if a human later rebases HEAD away, nothing the proposal
produced was lost. Five such rows were flagged as orphans on 2026-09-14
after an operator rebase; this pins the exemption.

No real DB or git required -- service_registry, the consequence log and
GitService are mocked, mirroring the sibling
test_commit_authorship_audit_worker_*.py pattern.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.workers.commit_reachability_auditor import CommitReachabilityAuditor


def _make_worker(
    rows: list[tuple[str, str | None, str, str | None]],
) -> CommitReachabilityAuditor:
    """Bypass Worker.__init__ (reads .intent/) -- wire mocks by hand."""
    w = object.__new__(CommitReachabilityAuditor)
    w._declaration = {}
    w._max_interval = 3600
    w.post_heartbeat = AsyncMock()
    w.post_observation = AsyncMock()
    w.post_report = AsyncMock()

    consequence_svc = AsyncMock()
    consequence_svc.get_all_shas_with_status = AsyncMock(return_value=rows)

    git_service = AsyncMock()
    # Every sha is unreachable in this fixture -- the only thing that decides
    # whether a finding is posted is the pre == post exemption.
    git_service.is_commit_on_branch = AsyncMock(return_value=False)
    git_service.get_commit_meta = AsyncMock(return_value={"commit_subject": "x"})

    core_context = MagicMock()
    core_context.registry.get_consequence_log_service = AsyncMock(
        return_value=consequence_svc
    )
    core_context.git_service = git_service
    w._core_context = core_context
    return w


def _blackboard_with_no_existing() -> AsyncMock:
    bb = AsyncMock()
    bb.fetch_active_finding_subjects_by_prefix = AsyncMock(return_value=set())
    bb.fetch_resolved_finding_subjects_by_prefix = AsyncMock(return_value=set())
    bb.fetch_abandoned_finding_subjects_by_prefix = AsyncMock(return_value=set())
    return bb


async def test_run_skips_nothing_to_commit_rows_and_reports_count() -> None:
    """pre == post rows never reach the reachability check or post a finding;
    pre != post unreachable rows still do. The report carries the skip count."""
    rows = [
        ("pid-nothing-1", "aaaa", "aaaa", "completed"),
        ("pid-nothing-2", "bbbb", "bbbb", "completed"),
        ("pid-real-orphan", "cccc", "dddd", "completed"),
    ]
    worker = _make_worker(rows)

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(
        return_value=_blackboard_with_no_existing()
    )
    with patch("body.services.service_registry.service_registry", mock_registry):
        await worker.run()

    git = worker._core_context.git_service
    git.is_commit_on_branch.assert_awaited_once_with("dddd")

    worker.post_observation.assert_awaited_once()
    call = worker.post_observation.await_args
    assert call.kwargs["subject"] == "governance.edge5.orphan_sha::pid-real-orphan"
    assert call.kwargs["payload"]["orphan_sha"] == "dddd"
    assert call.kwargs["status"] == "indeterminate"

    report = worker.post_report.await_args.kwargs["payload"]
    assert report == {
        "checked": 1,
        "orphans_detected": 1,
        "suppressed": 0,
        "no_commit_skipped": 2,
    }


async def test_run_null_pre_sha_is_not_treated_as_no_commit() -> None:
    """A row with no pre sha (reaper-reconstructed, ADR-148 D7) is still
    audited -- None != post, so the exemption must not swallow it."""
    worker = _make_worker([("pid-reconstructed", None, "eeee", "completed")])

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(
        return_value=_blackboard_with_no_existing()
    )
    with patch("body.services.service_registry.service_registry", mock_registry):
        await worker.run()

    worker.post_observation.assert_awaited_once()
    assert worker.post_report.await_args.kwargs["payload"]["no_commit_skipped"] == 0
