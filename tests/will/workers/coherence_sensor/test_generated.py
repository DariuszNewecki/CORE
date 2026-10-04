from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: 64904dd2-75d3-4019-beae-6aef4b89750f
async def test_CoherenceSensorWorker_run() -> None:
    from will.workers.coherence_sensor import CoherenceSensorWorker

    worker = CoherenceSensorWorker.__new__(CoherenceSensorWorker)
    worker._artifact_type = "python"
    worker._rule_namespace = "coherence.incoherence"
    worker.declaration_name = "coherence_sensor"

    worker.post_heartbeat = AsyncMock()
    worker.post_artifact_finding = AsyncMock()
    worker.post_report = AsyncMock()
    worker._load_lookback_seconds = MagicMock(return_value=3600)

    blackboard_service = MagicMock()
    blackboard_service.fetch_open_finding_subjects_by_prefix = AsyncMock(
        return_value=set()
    )

    row = (
        "proposal-1",
        "check-xyz",
        "/some/file.py",
        "new-finding-id",
    )
    result = MagicMock()
    result.fetchall.return_value = [row]

    session = MagicMock()
    session.execute = AsyncMock(return_value=result)
    session_cm = MagicMock()
    session_cm.__aenter__ = AsyncMock(return_value=session)
    session_cm.__aexit__ = AsyncMock(return_value=False)

    service_registry = MagicMock()
    service_registry.get_blackboard_service = AsyncMock(return_value=blackboard_service)
    service_registry.session = MagicMock(return_value=session_cm)

    with patch("body.services.service_registry.service_registry", service_registry):
        await worker.run()

    worker.post_heartbeat.assert_awaited_once()
    worker.post_artifact_finding.assert_awaited_once()
    worker.post_report.assert_awaited_once()
