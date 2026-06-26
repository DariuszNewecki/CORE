"""
Unit tests for TestRemediatorWorker ADR-104 D9 circuit breaker.

When the inherited remediation_attempt_count for a source_file equals or
exceeds cap_n, the worker MUST abandon findings immediately (no proposal
created, post_observation called for each) and continue to the next
source_file.

When inherited < cap_n the normal proposal-creation path runs.

No real DB needed — all collaborators are mocked.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Worker factory
# ---------------------------------------------------------------------------


def _make_worker() -> object:
    from will.workers.test_remediator.worker import TestRemediatorWorker

    w = object.__new__(TestRemediatorWorker)
    w._declaration = {}
    w._core_context = None
    w._worker_uuid = "worker-uuid-test"
    # Stub blackboard posting methods
    w.post_heartbeat = AsyncMock()
    w.post_report = AsyncMock()
    w.post_observation = AsyncMock()
    return w


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_FINDING = {
    "id": "entry-id-1",
    "payload": {"source_file": "src/foo/bar.py"},
}
_SOURCE_FILE = "src/foo/bar.py"
_CAP_N = 3


def _patch_operations(**overrides):  # type: ignore[no-untyped-def]
    """
    Return a dict of patches for all _operations helpers used by run().
    Callers can override individual mocks via keyword arguments.
    """
    defaults = {
        "will.workers.test_remediator.worker._load_open_findings": AsyncMock(
            return_value=[_FINDING]
        ),
        "will.workers.test_remediator.worker._get_active_build_tests_source_files": AsyncMock(
            return_value=set()
        ),
        "will.workers.test_remediator.worker._query_source_file_attempt_count": AsyncMock(
            return_value=0
        ),
        "will.workers.test_remediator.worker._abandon_capped_findings": AsyncMock(
            return_value=["entry-id-1"]
        ),
        "will.workers.test_remediator.worker._create_proposal": AsyncMock(
            return_value="proposal-id-1"
        ),
        "will.workers.test_remediator.worker._inherit_attempt_count": AsyncMock(),
        "will.workers.test_remediator.worker._defer_to_proposal": AsyncMock(
            return_value=1
        ),
        "will.workers.test_remediator.worker._release_entries": AsyncMock(
            return_value=0
        ),
    }
    defaults.update(overrides)
    return defaults


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


async def test_circuit_breaker_fires_when_inherited_equals_cap() -> None:
    """
    inherited == cap_n (3 == 3) → _abandon_capped_findings called,
    post_observation called for each abandoned entry, _create_proposal NOT called.
    """
    worker = _make_worker()
    patches = _patch_operations(
        **{
            "will.workers.test_remediator.worker._query_source_file_attempt_count": AsyncMock(
                return_value=_CAP_N
            ),
        }
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=_CAP_N)),
        ),
        *[patch(target, mock) for target, mock in patches.items()],
    ):
        await worker.run()  # type: ignore[attr-defined]

    patches["will.workers.test_remediator.worker._abandon_capped_findings"].assert_awaited_once_with(
        ["entry-id-1"], _CAP_N
    )
    worker.post_observation.assert_awaited_once()  # type: ignore[attr-defined]
    call_payload = worker.post_observation.await_args.kwargs["payload"]  # type: ignore[attr-defined]
    assert call_payload["reason"] == "remediation_cap_exhausted_via_inheritance"
    assert call_payload["source_file"] == _SOURCE_FILE
    patches["will.workers.test_remediator.worker._create_proposal"].assert_not_awaited()


async def test_circuit_breaker_fires_when_inherited_exceeds_cap() -> None:
    """
    inherited > cap_n (5 > 3) → same outcome as equals case.
    """
    worker = _make_worker()
    patches = _patch_operations(
        **{
            "will.workers.test_remediator.worker._query_source_file_attempt_count": AsyncMock(
                return_value=5
            ),
        }
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=_CAP_N)),
        ),
        *[patch(target, mock) for target, mock in patches.items()],
    ):
        await worker.run()  # type: ignore[attr-defined]

    patches["will.workers.test_remediator.worker._create_proposal"].assert_not_awaited()
    patches["will.workers.test_remediator.worker._abandon_capped_findings"].assert_awaited_once()


async def test_circuit_breaker_skips_when_inherited_below_cap() -> None:
    """
    inherited < cap_n (2 < 3) → normal path: proposal created, findings deferred.
    """
    worker = _make_worker()
    patches = _patch_operations(
        **{
            "will.workers.test_remediator.worker._query_source_file_attempt_count": AsyncMock(
                return_value=2
            ),
        }
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=_CAP_N)),
        ),
        *[patch(target, mock) for target, mock in patches.items()],
    ):
        await worker.run()  # type: ignore[attr-defined]

    patches["will.workers.test_remediator.worker._abandon_capped_findings"].assert_not_awaited()
    patches["will.workers.test_remediator.worker._create_proposal"].assert_awaited_once()
    patches["will.workers.test_remediator.worker._defer_to_proposal"].assert_awaited_once()


async def test_circuit_breaker_skips_when_no_prior_abandoned_findings() -> None:
    """
    inherited == 0 → normal path with no inheritance step.
    """
    worker = _make_worker()
    patches = _patch_operations(
        **{
            "will.workers.test_remediator.worker._query_source_file_attempt_count": AsyncMock(
                return_value=0
            ),
        }
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=_CAP_N)),
        ),
        *[patch(target, mock) for target, mock in patches.items()],
    ):
        await worker.run()  # type: ignore[attr-defined]

    patches["will.workers.test_remediator.worker._abandon_capped_findings"].assert_not_awaited()
    patches["will.workers.test_remediator.worker._inherit_attempt_count"].assert_not_awaited()
    patches["will.workers.test_remediator.worker._create_proposal"].assert_awaited_once()


async def test_report_includes_proposals_skipped_cap() -> None:
    """proposals_skipped_cap counter appears in the post_report payload."""
    worker = _make_worker()
    patches = _patch_operations(
        **{
            "will.workers.test_remediator.worker._query_source_file_attempt_count": AsyncMock(
                return_value=_CAP_N
            ),
        }
    )

    with (
        patch(
            "shared.infrastructure.intent.operational_config.load_operational_config",
            return_value=MagicMock(blackboard=MagicMock(remediation_cap_n=_CAP_N)),
        ),
        *[patch(target, mock) for target, mock in patches.items()],
    ):
        await worker.run()  # type: ignore[attr-defined]

    report_payload = worker.post_report.await_args.kwargs["payload"]  # type: ignore[attr-defined]
    assert report_payload["proposals_skipped_cap"] == 1
    assert report_payload["proposals_created"] == []
