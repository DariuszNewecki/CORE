"""#773 T5.3 regression tests: TestRemediatorWorker no longer defers findings
to any symbol proposal, since neither finding type it consumes carries
symbol identity reliable enough to map to one specific proposal.

Investigation (recorded on #773 and in worker.py's module docstring)
disproved the "defer to the correct sibling proposal" premise the original
fan-out design assumed:

- `python::test.runner.missing` is file-level by construction (payload has
  no symbol identity at all).
- `python::test.runner.failure`'s `test_name` only exact-matches a symbol
  for auto-generated tests, and even then TestGapEvaluator's presence-based
  covered/gap split excludes that symbol from `gaps` -- no proposal is ever
  created for it here.

The correction is elimination of the false "defer to first proposal"
attribution, not fan-out infrastructure the persisted data can't honestly
support. See #844 for future failing-test remediation design.

No real DB needed -- all collaborators are mocked, following the pattern in
test_test_remediator_circuit_breaker.py.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch


_SOURCE_FILE = "src/foo/bar.py"
_CAP_N = 3


def _make_worker() -> object:
    from will.workers.test_remediator.worker import TestRemediatorWorker

    w = object.__new__(TestRemediatorWorker)
    w._declaration = {}
    w._core_context = MagicMock()
    w._worker_uuid = "worker-uuid-test"
    w.post_heartbeat = AsyncMock()
    w.post_report = AsyncMock()
    w.post_observation = AsyncMock()
    return w


def _patch_operations(*, gaps: list[dict[str, str]], active_symbol_proposals=None, **overrides):  # type: ignore[no-untyped-def]
    """Same shape as test_test_remediator_circuit_breaker.py's helper, with
    `gaps` and `active_symbol_proposals` exposed as direct parameters since
    these tests vary them per scenario."""
    _gap_result = MagicMock()
    _gap_result.ok = True
    _gap_result.data = {
        "gaps": gaps,
        "test_file": "tests/foo/test_bar.py",
        "covered_count": 0,
    }
    defaults = {
        "will.workers.test_remediator.worker._get_active_symbol_proposals": AsyncMock(
            return_value=active_symbol_proposals or set()
        ),
        "will.workers.test_remediator.worker._query_source_file_attempt_count": AsyncMock(
            return_value=0
        ),
        "will.workers.test_remediator.worker._query_recent_symbol_failures": AsyncMock(
            return_value=0
        ),
        "will.workers.test_remediator.worker._abandon_capped_findings": AsyncMock(
            return_value=[]
        ),
        "will.workers.test_remediator.worker._inherit_attempt_count": AsyncMock(),
        "will.workers.test_remediator.worker._release_entries": AsyncMock(
            side_effect=lambda entry_ids: len(entry_ids)
        ),
        "body.evaluators.test_gap_evaluator.TestGapEvaluator": MagicMock(
            return_value=MagicMock(execute=AsyncMock(return_value=_gap_result))
        ),
    }
    defaults.update(overrides)
    return defaults


async def _run_with_patches(worker, findings: list[dict], patches: dict) -> None:
    with contextlib.ExitStack() as stack:
        stack.enter_context(
            patch(
                "will.workers.test_remediator.worker._load_open_findings",
                AsyncMock(return_value=findings),
            )
        )
        stack.enter_context(
            patch(
                "shared.infrastructure.intent.operational_config.load_operational_config",
                return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=_CAP_N)),
            )
        )
        for target, mock in patches.items():
            stack.enter_context(patch(target, mock))
        await worker.run()  # type: ignore[attr-defined]


async def test_multi_symbol_missing_finding_creates_both_proposals_and_releases() -> None:
    """A file-level `.missing` finding with two untested symbols: both
    symbol proposals get created, but the finding is released -- not
    deferred to either one, since it isn't about either symbol
    specifically."""
    worker = _make_worker()
    findings = [
        {
            "id": "entry-missing-1",
            "payload": {"source_file": _SOURCE_FILE, "test_file": "tests/foo/test_bar.py"},
        }
    ]
    gaps = [
        {"name": "foo", "kind": "function", "signature": "def foo()"},
        {"name": "bar", "kind": "function", "signature": "def bar()"},
    ]
    create_mock = AsyncMock(side_effect=["proposal-foo", "proposal-bar"])
    patches = _patch_operations(
        gaps=gaps,
        **{
            "will.workers.test_remediator.worker._create_symbol_proposal": create_mock,
        },
    )

    await _run_with_patches(worker, findings, patches)

    assert create_mock.await_count == 2
    called_symbols = {c.kwargs["symbol_name"] for c in create_mock.await_args_list}
    assert called_symbols == {"foo", "bar"}

    patches["will.workers.test_remediator.worker._release_entries"].assert_awaited_once_with(
        ["entry-missing-1"]
    )

    report_payload = worker.post_report.await_args.kwargs["payload"]  # type: ignore[attr-defined]
    assert report_payload["entries_deferred"] == 0
    assert report_payload["entries_released"] == 1
    assert set(report_payload["created_proposals"]) == {
        f"{_SOURCE_FILE}::foo",
        f"{_SOURCE_FILE}::bar",
    }


async def test_failure_finding_with_convention_matched_name_is_still_released() -> None:
    """A `.failure` finding whose test_name happens to exact-match a gap
    symbol name is NOT special-cased -- no deferral is attempted even
    though a naive name-strip would "succeed". Convention-matched failure
    findings are outside flow.build_test_for_symbol's scope (#844)."""
    worker = _make_worker()
    findings = [
        {
            "id": "entry-failure-matched",
            "payload": {
                "source_file": _SOURCE_FILE,
                "test_file": "tests/foo/test_bar.py",
                "test_name": "test_foo",
            },
        }
    ]
    gaps = [{"name": "foo", "kind": "function", "signature": "def foo()"}]
    create_mock = AsyncMock(return_value="proposal-foo")
    patches = _patch_operations(
        gaps=gaps,
        **{
            "will.workers.test_remediator.worker._create_symbol_proposal": create_mock,
        },
    )

    await _run_with_patches(worker, findings, patches)

    create_mock.assert_awaited_once()
    patches["will.workers.test_remediator.worker._release_entries"].assert_awaited_once_with(
        ["entry-failure-matched"]
    )
    report_payload = worker.post_report.await_args.kwargs["payload"]  # type: ignore[attr-defined]
    assert report_payload["entries_deferred"] == 0


async def test_failure_finding_with_non_matched_name_is_released() -> None:
    """A `.failure` finding whose test_name has no relationship to any gap
    symbol is released -- no inferred identity, no proposal linkage."""
    worker = _make_worker()
    findings = [
        {
            "id": "entry-failure-unmatched",
            "payload": {
                "source_file": _SOURCE_FILE,
                "test_file": "tests/foo/test_bar.py",
                "test_name": "test_something_entirely_unrelated_with_many_words",
            },
        }
    ]
    gaps = [{"name": "foo", "kind": "function", "signature": "def foo()"}]
    create_mock = AsyncMock(return_value="proposal-foo")
    patches = _patch_operations(
        gaps=gaps,
        **{
            "will.workers.test_remediator.worker._create_symbol_proposal": create_mock,
        },
    )

    await _run_with_patches(worker, findings, patches)

    create_mock.assert_awaited_once()
    patches["will.workers.test_remediator.worker._release_entries"].assert_awaited_once_with(
        ["entry-failure-unmatched"]
    )


async def test_reevaluation_after_proposal_created_does_not_recreate_or_hot_loop() -> None:
    """Two consecutive cycles for the same source_file/finding:

    Cycle 1: no active proposals yet -> creates one symbol proposal ->
    releases the finding (not deferred).
    Cycle 2 (simulating the released finding reclaimed on the next run):
    _get_active_symbol_proposals now reflects the proposal created in
    cycle 1 -> the existing dedup check skips re-creating it -> the
    finding is released again, not stuck or duplicated. This is the
    convergence property that prevents a hot processing loop: after
    exactly one release/reclaim round-trip, no further proposal-creation
    work happens for this symbol, only a (cheap) dedup-skip + release.
    """
    finding = {
        "id": "entry-reeval-1",
        "payload": {"source_file": _SOURCE_FILE, "test_file": "tests/foo/test_bar.py"},
    }
    gaps = [{"name": "foo", "kind": "function", "signature": "def foo()"}]

    # --- Cycle 1: no active proposals yet ---
    worker1 = _make_worker()
    create_mock_1 = AsyncMock(return_value="proposal-foo")
    patches_1 = _patch_operations(
        gaps=gaps,
        active_symbol_proposals=set(),
        **{"will.workers.test_remediator.worker._create_symbol_proposal": create_mock_1},
    )
    await _run_with_patches(worker1, [finding], patches_1)

    create_mock_1.assert_awaited_once()
    patches_1["will.workers.test_remediator.worker._release_entries"].assert_awaited_once_with(
        ["entry-reeval-1"]
    )

    # --- Cycle 2: the proposal from cycle 1 is now active/visible ---
    worker2 = _make_worker()
    create_mock_2 = AsyncMock()
    patches_2 = _patch_operations(
        gaps=gaps,
        active_symbol_proposals={(_SOURCE_FILE, "foo")},
        **{"will.workers.test_remediator.worker._create_symbol_proposal": create_mock_2},
    )
    await _run_with_patches(worker2, [finding], patches_2)

    create_mock_2.assert_not_awaited()
    patches_2["will.workers.test_remediator.worker._release_entries"].assert_awaited_once_with(
        ["entry-reeval-1"]
    )
    report_payload_2 = worker2.post_report.await_args.kwargs["payload"]  # type: ignore[attr-defined]
    assert report_payload_2["symbols_skipped_dedup"] == 1
    assert report_payload_2["proposals_created"] == 0
