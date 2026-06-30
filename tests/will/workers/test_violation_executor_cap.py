"""
Unit tests for ViolationExecutorWorker ADR-104 D9 cap mechanism
(unmapped-rule path).

Three behaviours under test:

1. Ceremony failure path: _abandon_findings calls
   abandon_entries_and_increment_attempt_count (NOT bare abandon_entries).

2. Circuit breaker fires: when inherited count >= cap_n before _process_file,
   the file is skipped and findings are abandoned via _abandon_capped_findings.

3. Circuit breaker skips: when inherited count < cap_n, normal ceremony runs.

No DB required — all collaborators are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ---------------------------------------------------------------------------
# Worker factory
# ---------------------------------------------------------------------------


def _make_worker() -> object:
    from will.workers.violation_executor import ViolationExecutorWorker

    w = object.__new__(ViolationExecutorWorker)
    w._ctx = MagicMock()
    w._ctx.git_service = MagicMock()
    w._write = False
    w._files_per_cycle_max = 10
    w._declaration = {}
    w._worker_uuid = "worker-uuid-vex"
    w.post_heartbeat = AsyncMock()
    w.post_report = AsyncMock()
    w._post_entry = AsyncMock()
    return w


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FILE = "src/body/services/some_service.py"
_FINDING = {
    "id": "entry-aaa",
    "payload": {"file_path": _FILE, "rule": "cli.dangerous_explicit"},
}
_CAP_N = 3


def _patch_run(**overrides):  # type: ignore[no-untyped-def]
    """Patch all collaborators consumed by run()."""
    defaults = {
        "will.workers.violation_executor.ViolationExecutorWorker._load_mapped_rule_ids": MagicMock(
            return_value=set()
        ),
        "will.workers.violation_executor.ViolationExecutorWorker._claim_unmapped_findings": AsyncMock(
            return_value=[_FINDING]
        ),
        "will.workers.violation_executor.ViolationExecutorWorker._query_file_attempt_count": AsyncMock(
            return_value=0
        ),
        "will.workers.violation_executor.ViolationExecutorWorker._abandon_capped_findings": AsyncMock(),
        "will.workers.violation_executor.ViolationExecutorWorker._process_file": AsyncMock(
            return_value=(True, ["cli.dangerous_explicit"])
        ),
        "will.workers.violation_executor.ViolationExecutorWorker._surface_candidate": AsyncMock(),
        "will.workers.violation_executor.ViolationExecutorWorker._release_findings": AsyncMock(),
        "will.workers.violation_executor.ViolationExecutorWorker._post_blast_bound_finding": AsyncMock(),
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Test: ceremony failure increments count
# ---------------------------------------------------------------------------


async def test_abandon_findings_uses_increment_method() -> None:
    """
    _abandon_findings calls abandon_entries_and_increment_attempt_count,
    not the plain abandon_entries. Verified by inspecting the mock call on
    the blackboard service returned by service_registry.
    """
    worker = _make_worker()

    mock_svc = AsyncMock()
    mock_svc.abandon_entries_and_increment_attempt_count = AsyncMock()

    with patch(
        "body.services.service_registry.service_registry",
        new=MagicMock(
            get_blackboard_service=AsyncMock(return_value=mock_svc)
        ),
    ):
        await worker._abandon_findings([_FINDING])  # type: ignore[attr-defined]

    mock_svc.abandon_entries_and_increment_attempt_count.assert_awaited_once_with(
        ["entry-aaa"]
    )


# ---------------------------------------------------------------------------
# Test: circuit breaker fires when inherited >= cap
# ---------------------------------------------------------------------------


async def test_circuit_breaker_fires_when_inherited_equals_cap() -> None:
    """
    When _query_file_attempt_count returns cap_n, _abandon_capped_findings is
    called and _process_file is NOT called.
    """
    worker = _make_worker()
    patches = _patch_run(
        **{
            "will.workers.violation_executor.ViolationExecutorWorker._query_file_attempt_count": AsyncMock(
                return_value=_CAP_N
            ),
        }
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(
                blackboard=MagicMock(remediation_cap_n=_CAP_N),
                workers=MagicMock(
                    violation_executor=MagicMock(claim_limit=50)
                ),
            ),
        ),
        *[patch(target, mock) for target, mock in patches.items()],
    ):
        await worker.run()  # type: ignore[attr-defined]

    patches[
        "will.workers.violation_executor.ViolationExecutorWorker._abandon_capped_findings"
    ].assert_awaited_once_with(["entry-aaa"], _CAP_N)
    patches[
        "will.workers.violation_executor.ViolationExecutorWorker._process_file"
    ].assert_not_awaited()


async def test_circuit_breaker_fires_when_inherited_exceeds_cap() -> None:
    """inherited > cap_n → same outcome as equals case."""
    worker = _make_worker()
    patches = _patch_run(
        **{
            "will.workers.violation_executor.ViolationExecutorWorker._query_file_attempt_count": AsyncMock(
                return_value=7
            ),
        }
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(
                blackboard=MagicMock(remediation_cap_n=_CAP_N),
                workers=MagicMock(
                    violation_executor=MagicMock(claim_limit=50)
                ),
            ),
        ),
        *[patch(target, mock) for target, mock in patches.items()],
    ):
        await worker.run()  # type: ignore[attr-defined]

    patches[
        "will.workers.violation_executor.ViolationExecutorWorker._abandon_capped_findings"
    ].assert_awaited_once()
    patches[
        "will.workers.violation_executor.ViolationExecutorWorker._process_file"
    ].assert_not_awaited()


# ---------------------------------------------------------------------------
# Test: circuit breaker skips when count < cap
# ---------------------------------------------------------------------------


async def test_circuit_breaker_skips_when_inherited_below_cap() -> None:
    """
    When inherited < cap_n, the normal ceremony path runs:
    _process_file is called, _abandon_capped_findings is NOT called.
    """
    worker = _make_worker()
    patches = _patch_run(
        **{
            "will.workers.violation_executor.ViolationExecutorWorker._query_file_attempt_count": AsyncMock(
                return_value=2
            ),
        }
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(
                blackboard=MagicMock(remediation_cap_n=_CAP_N),
                workers=MagicMock(
                    violation_executor=MagicMock(claim_limit=50)
                ),
            ),
        ),
        *[patch(target, mock) for target, mock in patches.items()],
    ):
        await worker.run()  # type: ignore[attr-defined]

    patches[
        "will.workers.violation_executor.ViolationExecutorWorker._abandon_capped_findings"
    ].assert_not_awaited()
    patches[
        "will.workers.violation_executor.ViolationExecutorWorker._process_file"
    ].assert_awaited_once()


# ---------------------------------------------------------------------------
# Test: capped counter in report
# ---------------------------------------------------------------------------


async def test_report_includes_capped_counter() -> None:
    """post_report payload includes a 'capped' counter when circuit breaker fires."""
    worker = _make_worker()
    patches = _patch_run(
        **{
            "will.workers.violation_executor.ViolationExecutorWorker._query_file_attempt_count": AsyncMock(
                return_value=_CAP_N
            ),
        }
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(
                blackboard=MagicMock(remediation_cap_n=_CAP_N),
                workers=MagicMock(
                    violation_executor=MagicMock(claim_limit=50)
                ),
            ),
        ),
        *[patch(target, mock) for target, mock in patches.items()],
    ):
        await worker.run()  # type: ignore[attr-defined]

    payload = worker.post_report.await_args.kwargs["payload"]  # type: ignore[attr-defined]
    assert payload["capped"] == 1
    assert payload["succeeded"] == 0
    assert payload["failed"] == 0
