"""CommitReachabilityAuditor.run does not call a commit this clone never
held an orphan.

Under ADR-132 D2 the services run on their own clone. After the 2026-10-12
cutover it lacked commits made in the development tree, every
``is_commit_on_branch`` came back False, and each such proposal was posted
as ``governance.edge5.orphan_sha`` with "object not in store" -- a false
alarm for the governor. Absence from the store is not evidence of an
orphan; only a commit the clone holds and no branch contains is one.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from tests.will.workers.test_commit_reachability_auditor__no_commit_skip import (
    _blackboard_with_no_existing,
    _make_worker,
)


async def test_commit_missing_from_the_clone_is_skipped_not_posted() -> None:
    rows = [
        ("pid-elsewhere", "aaaa", "bbbb", "completed"),
        ("pid-real-orphan", "cccc", "dddd", "completed"),
    ]
    worker = _make_worker(rows)
    git = worker._core_context.git_service
    git.has_commit = AsyncMock(side_effect=lambda sha: sha != "bbbb")

    mock_registry = MagicMock()
    mock_registry.get_blackboard_service = AsyncMock(
        return_value=_blackboard_with_no_existing()
    )
    with patch("body.services.service_registry.service_registry", mock_registry):
        await worker.run()

    git.is_commit_on_branch.assert_awaited_once_with("dddd")
    worker.post_observation.assert_awaited_once()
    assert (
        worker.post_observation.await_args.kwargs["subject"]
        == "governance.edge5.orphan_sha::pid-real-orphan"
    )
    report = worker.post_report.await_args.kwargs["payload"]
    assert report["not_in_store_skipped"] == 1
    assert report["checked"] == 1
