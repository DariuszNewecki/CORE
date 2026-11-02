from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: e6ba3a05-739c-4572-9ebb-a3bd7663dc70
async def test_DeadShimSensor_run() -> None:
    from will.workers.dead_shim_sensor import DeadShimSensor

    sensor = DeadShimSensor()
    sensor.post_heartbeat = AsyncMock()
    sensor.post_finding = AsyncMock()
    sensor.post_report = AsyncMock()

    symbol_svc = MagicMock()
    symbol_svc.fetch_dead_shim_candidates = AsyncMock(
        return_value=[
            {
                "symbol_path": "src/foo/bar.py::baz",
                "module": "src.foo.bar",
                "qualname": "baz",
                "kind": "function",
            },
        ]
    )

    blackboard_svc = MagicMock()
    blackboard_svc.fetch_open_findings = AsyncMock(
        return_value=[
            {
                "subject": "python::modernization.dead_shim::src/foo/old.py::old",
                "id": "entry-1",
            },
        ]
    )
    blackboard_svc.resolve_entries = AsyncMock()

    service_registry = MagicMock()
    service_registry.get_symbol_service = AsyncMock(return_value=symbol_svc)
    service_registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)

    with (
        patch("body.services.service_registry.service_registry", service_registry),
        patch(
            "will.workers.dead_shim_sensor._published_contract_names",
            return_value=set(),
        ),
    ):
        await sensor.run()

    sensor.post_heartbeat.assert_awaited_once()
    symbol_svc.fetch_dead_shim_candidates.assert_awaited_once()

    sensor.post_finding.assert_awaited_once()
    finding_call = sensor.post_finding.await_args
    assert finding_call.kwargs["subject"] == (
        "python::modernization.dead_shim::src/foo/bar.py::baz"
    )

    blackboard_svc.resolve_entries.assert_awaited_once_with(["entry-1"])

    sensor.post_report.assert_awaited_once()
    report_payload = sensor.post_report.await_args.kwargs["payload"]
    assert report_payload["candidates"] == 1
    assert report_payload["posted"] == 1
    assert report_payload["resolved"] == 1



import pytest


@pytest.mark.asyncio
# ID: 99edeacd-f045-4b12-b74b-8a68ce21f36a
async def test_DeadShimSensor():
    from will.workers.dead_shim_sensor import DeadShimSensor

    worker = DeadShimSensor()
    worker.post_heartbeat = AsyncMock()
    worker.post_finding = AsyncMock()
    worker.post_report = AsyncMock()

    candidate = {
        "symbol_path": "src/orchestration/foo.py",
        "module": "orchestration.foo",
        "qualname": "bar",
        "kind": "function",
    }

    symbol_svc = MagicMock()
    symbol_svc.fetch_dead_shim_candidates = AsyncMock(return_value=[candidate])

    blackboard_svc = MagicMock()
    blackboard_svc.fetch_open_findings = AsyncMock(return_value=[])
    blackboard_svc.resolve_entries = AsyncMock()

    service_registry = MagicMock()
    service_registry.get_symbol_service = AsyncMock(return_value=symbol_svc)
    service_registry.get_blackboard_service = AsyncMock(return_value=blackboard_svc)

    with (
        patch("body.services.service_registry.service_registry", service_registry),
        patch(
            "will.workers.dead_shim_sensor._published_contract_names",
            return_value=set(),
        ),
    ):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    symbol_svc.fetch_dead_shim_candidates.assert_awaited_once()
    blackboard_svc.fetch_open_findings.assert_awaited_once()
    worker.post_finding.assert_awaited_once()
    worker.post_report.assert_awaited_once()
