"""Per-symbol breaker: exhausted lineages delegate once; time never re-arms.

ADR-104 D9 as amended 2026-10-03, applied to the ADR-133 D4 per-symbol cap.
Found on knowledge_source_check.py: both symbols failed test generation three
times (acceptance gate: unbound name 'rule_id'); the old breaker counted
failures in the last 24 hours, skipped the symbol for that cycle, released the
file's finding, and would retry once the failures aged out — never reaching
the governor.
"""

from __future__ import annotations

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

from tests.will.workers.test_test_remediator_circuit_breaker import (
    _CAP_N,
    _SOURCE_FILE,
    _make_worker,
    _patch_operations,
)


_GAPS = [
    {"name": "Check", "kind": "class", "signature": "class Check"},
    {"name": "Check.verify", "kind": "method", "signature": "def verify(self)"},
]
_REASON = "[code.tests.no_unresolved_free_names] Name: 'rule_id' at line 25."


async def _run(lineage):  # type: ignore[no-untyped-def]
    worker = _make_worker()
    gap_result = MagicMock(ok=True, data={"gaps": _GAPS, "test_file": "t.py"})
    patches = _patch_operations(
        **{
            "will.workers.test_remediator.worker._query_symbol_failure_lineage": AsyncMock(
                side_effect=lineage
            ),
            "body.evaluators.test_gap_evaluator.TestGapEvaluator": MagicMock(
                return_value=MagicMock(execute=AsyncMock(return_value=gap_result))
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
    return worker, patches


async def test_three_failed_attempts_delegate_once_with_the_failure() -> None:
    worker, patches = await _run(lambda f, s: (3, _REASON))

    delegate = patches["will.workers.test_remediator.worker._delegate_capped_findings"]
    delegate.assert_awaited_once()
    entry_ids, count, delegation = delegate.await_args.args
    assert entry_ids == ["entry-id-1"] and count == 3
    assert delegation["reason"] == "failure_cap_delegated"
    assert delegation["source_file"] == _SOURCE_FILE
    assert delegation["symbol_name"] == "Check"
    assert delegation["attempted_actions"] == "flow.build_test_for_symbol"
    assert delegation["attempt_count"] == 3
    assert delegation["detail"] == _REASON
    assert [c["symbol_name"] for c in delegation["capped_symbols"]] == [
        "Check",
        "Check.verify",
    ]
    # Delegated, not released back to the claim pool, and no new proposal.
    patches["will.workers.test_remediator.worker._release_entries"].assert_not_awaited()
    patches[
        "will.workers.test_remediator.worker._create_symbol_proposal"
    ].assert_not_awaited()
    worker.post_observation.assert_awaited_once()  # type: ignore[attr-defined]


async def test_a_still_workable_symbol_keeps_the_file_autonomous() -> None:
    """One capped symbol does not delegate the file while another can still
    be generated; the capped one is skipped, the other proposed."""
    _worker, patches = await _run(
        lambda f, s: (3, _REASON) if s == "Check" else (0, None)
    )
    patches[
        "will.workers.test_remediator.worker._delegate_capped_findings"
    ].assert_not_awaited()
    create = patches["will.workers.test_remediator.worker._create_symbol_proposal"]
    create.assert_awaited_once()
    assert create.await_args.kwargs["symbol_name"] == "Check.verify"


async def test_repeat_observation_does_not_duplicate_the_delegated_work() -> None:
    """The delegated finding (indeterminate) stays in the runner's dedup set,
    so the next detection of the same missing test posts nothing new."""
    from will.workers.test_runner_sensor import TestRunnerSensor

    sensor = TestRunnerSensor()
    sensor.post_heartbeat = AsyncMock()
    sensor.post_report = AsyncMock()
    sensor.post_artifact_finding = AsyncMock()
    subject = f"python::test.runner.missing::{_SOURCE_FILE}"
    bb = AsyncMock()
    bb.fetch_open_findings.return_value = [
        {"id": "cov-1", "payload": {"source_file": _SOURCE_FILE}}
    ]
    bb.fetch_active_finding_subjects_by_prefix.return_value = {subject}
    bb.adjudicate_awaiting_reaudit_findings.return_value = {
        "released_subjects": [],
        "resolved_subjects": [],
    }
    bb.fetch_awaiting_reaudit_subjects_by_prefix.return_value = set()
    with (
        patch("body.services.service_registry.service_registry") as registry,
        patch(
            "will.workers.test_runner_sensor.load_test_coverage_config", return_value={}
        ),
        patch(
            "will.workers.test_runner_sensor.uncovered_source_files", return_value=set()
        ),
        patch(
            "will.workers.test_runner_sensor.source_to_test_path",
            return_value="tests/does/not/exist/test_generated.py",
        ),
    ):
        registry.get_blackboard_service = AsyncMock(return_value=bb)
        await sensor.run()

    sensor.post_artifact_finding.assert_not_awaited()
