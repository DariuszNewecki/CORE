"""ADR-091 D2 Revision B — verify each surviving direct post_finding caller
classifies its emission with resolution_mechanism='self_resolve'.

These are posting-side tests per Revision B (h): they assert that each call
site supplies the new keyword-only field with the value its emitter's
resolver path implies. The full open → resolved integration coverage is
delegated to the resolver path itself (in-Python resolve_entries for two
of the three workers, BlackboardService.resolve_stale_alerts_for_terminal_targets
for blackboard_shop_manager), which is exercised by the workers' production
loops — see the module docstring of each shop manager for the named resolver.

Five tests, one per surviving post_finding(subject, payload, ...) call site:

- WorkerShopManager:                   worker.silent::<uuid>
- BlackboardShopManager:               blackboard.entry_stale::<entry_id>
- ProposalPipelineShopManager:         proposal.stuck_approved::<proposal_id>
                                       proposal.stuck_executing::<proposal_id>
                                       proposal.repeated_failure::<action_id>::<rule_id>

Each test mocks the worker's DB-facing collaborators and post_* helpers,
drives one run() cycle with a synthetic condition seeded, and asserts that
post_finding was awaited with resolution_mechanism='self_resolve'.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from shared.workers.schedule import WorkerScheduleState
from will.workers.blackboard_shop_manager import BlackboardShopManager
from will.workers.proposal_pipeline_shop_manager import ProposalPipelineShopManager
from will.workers.worker_shop_manager import WorkerShopManager


def _self_resolve_kwarg(mock: AsyncMock) -> list[str]:
    """Return the resolution_mechanism kwarg of every await on *mock*."""
    return [call.kwargs.get("resolution_mechanism") for call in mock.await_args_list]


@pytest.mark.asyncio
async def test_worker_shop_manager_classifies_worker_silent_as_self_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = WorkerShopManager()

    silent_uuid = "11111111-1111-1111-1111-111111111111"
    silent_worker = {
        "worker_name": "synthetic_silent_worker",
        "worker_uuid": silent_uuid,
        "seconds_silent": 9999,
    }

    monkeypatch.setattr(
        "will.workers.worker_shop_manager.load_worker_schedule_state",
        lambda: WorkerScheduleState(
            thresholds={silent_uuid: 60},
            active_uuids=frozenset({silent_uuid}),
            fallback_sec=60,
        ),
    )

    post_finding = AsyncMock()
    monkeypatch.setattr(worker, "post_heartbeat", AsyncMock())
    monkeypatch.setattr(
        worker, "_fetch_registered_workers", AsyncMock(return_value=[silent_worker])
    )
    monkeypatch.setattr(worker, "_fetch_existing_findings", AsyncMock(return_value={}))
    monkeypatch.setattr(worker, "post_finding", post_finding)
    monkeypatch.setattr(worker, "post_report", AsyncMock())

    bb_svc = MagicMock()
    bb_svc.resolve_entries = AsyncMock()
    service_registry_mock = MagicMock()
    service_registry_mock.get_blackboard_service = AsyncMock(return_value=bb_svc)
    monkeypatch.setattr(
        "body.services.service_registry.service_registry", service_registry_mock
    )

    await worker.run()

    post_finding.assert_awaited_once()
    kwargs = post_finding.await_args.kwargs
    assert kwargs["subject"] == f"worker.silent::{silent_uuid}"
    assert kwargs["resolution_mechanism"] == "self_resolve"


@pytest.mark.asyncio
async def test_blackboard_shop_manager_classifies_entry_stale_as_self_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker = BlackboardShopManager()

    stale_entry_id = "22222222-2222-2222-2222-222222222222"
    stale_entry = {
        "id": stale_entry_id,
        "entry_type": "claim",
        "subject": "synthetic.subject",
        "worker_uuid": "33333333-3333-3333-3333-333333333333",
        "status": "claimed",
        "age_seconds": 9999,
        "sla_seconds": 3600,
    }

    post_finding = AsyncMock()
    monkeypatch.setattr(worker, "post_heartbeat", AsyncMock())
    monkeypatch.setattr(
        worker, "_sweep_resolved_stale_alerts", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(worker, "_sweep_telemetry_ttl", AsyncMock(return_value=0))
    monkeypatch.setattr(
        worker, "_sweep_delegate_findings_ttl", AsyncMock(return_value=0)
    )
    monkeypatch.setattr(
        worker, "_fetch_stale_entries", AsyncMock(return_value=[stale_entry])
    )
    monkeypatch.setattr(
        worker, "_fetch_existing_findings", AsyncMock(return_value=set())
    )
    monkeypatch.setattr(worker, "_count_active_entries", AsyncMock(return_value=1))
    monkeypatch.setattr(worker, "post_finding", post_finding)
    monkeypatch.setattr(worker, "post_report", AsyncMock())

    await worker.run()

    post_finding.assert_awaited_once()
    kwargs = post_finding.await_args.kwargs
    assert kwargs["subject"] == f"blackboard.entry_stale::{stale_entry_id}"
    assert kwargs["resolution_mechanism"] == "self_resolve"


@pytest.mark.asyncio
async def test_proposal_pipeline_classifies_all_three_subjects_as_self_resolve(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """One run() cycle seeded with all three condition classes; assert that
    every post_finding call carries resolution_mechanism='self_resolve' and
    that the three canonical subject prefixes are covered."""
    worker = ProposalPipelineShopManager()

    stuck_approved_row = {
        "proposal_id": "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
        "approved_at": None,
        "seconds_stuck": 9999,
    }
    stuck_executing_row = {
        "proposal_id": "bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb",
        "execution_started_at": None,
        "seconds_stuck": 9999,
    }
    repeated_failure_row = {
        "action_id": "fix.format",
        "rule_id": "style.formatter_required",
        "failure_count": 7,
        "last_failure_at": None,
        "proposal_ids": ["cccccccc-cccc-cccc-cccc-cccccccccccc"],
    }

    proposal_svc = MagicMock()
    proposal_svc.fetch_stuck_approved = AsyncMock(return_value=[stuck_approved_row])
    proposal_svc.fetch_stuck_executing = AsyncMock(return_value=[stuck_executing_row])
    proposal_svc.fetch_repeated_failures = AsyncMock(
        return_value=[repeated_failure_row]
    )

    blackboard_svc = MagicMock()
    blackboard_svc.resolve_entries = AsyncMock()

    service_registry_mock = MagicMock()
    service_registry_mock.get_proposal_supervision_service = AsyncMock(
        return_value=proposal_svc
    )
    service_registry_mock.get_blackboard_service = AsyncMock(
        return_value=blackboard_svc
    )
    monkeypatch.setattr(
        "body.services.service_registry.service_registry", service_registry_mock
    )

    post_finding = AsyncMock()
    monkeypatch.setattr(worker, "post_heartbeat", AsyncMock())
    monkeypatch.setattr(worker, "_fetch_existing_findings", AsyncMock(return_value={}))
    monkeypatch.setattr(worker, "post_finding", post_finding)
    monkeypatch.setattr(worker, "post_report", AsyncMock())

    await worker.run()

    assert post_finding.await_count == 3
    mechanisms = _self_resolve_kwarg(post_finding)
    assert mechanisms == ["self_resolve", "self_resolve", "self_resolve"]

    subjects = [call.kwargs["subject"] for call in post_finding.await_args_list]
    assert any(s.startswith("proposal.stuck_approved::") for s in subjects)
    assert any(s.startswith("proposal.stuck_executing::") for s in subjects)
    assert any(s.startswith("proposal.repeated_failure::") for s in subjects)


@pytest.mark.asyncio
async def test_post_finding_requires_resolution_mechanism_kwarg() -> None:
    """API contract: post_finding refuses to dispatch without
    resolution_mechanism. Guards against future call sites that forget
    the field and would otherwise silently land as NULL (failing the
    DB CHECK at INSERT-time, but only after reaching the wire — this
    test catches it at parse-and-type-check time)."""
    worker = WorkerShopManager()
    with pytest.raises(TypeError):
        # mypy/pyright would also reject this; the runtime guard is the
        # belt-and-suspenders second check the constitutional contract
        # gets for free from Python's keyword-only-required semantics.
        await worker.post_finding(subject="x", payload={})  # type: ignore[call-arg]


@pytest.mark.asyncio
async def test_post_artifact_finding_auto_supplies_reaudit_mechanism(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The typed-parameter wrapper for artifact findings supplies
    resolution_mechanism='reaudit' automatically; callers of
    post_artifact_finding do not classify per Revision B (b). Verifies
    the wrapper position is intact and the existing sensors that
    migrated in Phases 1-6 do not need to be revisited."""
    worker = WorkerShopManager()

    # The worker_shop_manager declaration does not declare an
    # artifact_type scope — that exercises the Phase 1 transition
    # allowance branch (debug log, no validation). Sufficient for the
    # wrapper-passthrough contract under test.
    captured = AsyncMock()
    monkeypatch.setattr(worker, "post_finding", captured)

    await worker.post_artifact_finding(
        artifact_type="python",
        sub_namespace="audit.violation",
        identity_key_value="example::3",
        payload={"rule": "example"},
    )

    captured.assert_awaited_once()
    kwargs = captured.await_args.kwargs
    assert kwargs["subject"] == "python::audit.violation::example::3"
    assert kwargs["resolution_mechanism"] == "reaudit"
