from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.engines.runtime_gate import RuntimeGateEngine


# ID: 960b0448-d8d1-44e1-8e9c-cca6345c49f3
async def test_RuntimeGateEngine_verify_context() -> None:
    engine = RuntimeGateEngine()
    context = MagicMock()
    params: dict[str, Any] = {"check_type": "worker_process_classification"}

    with patch(
        "mind.logic.engines.runtime_gate._check_worker_process_classification",
        new=AsyncMock(return_value=[]),
    ) as mock_check:
        result = await engine.verify_context(context, params)

    assert result == []
    mock_check.assert_awaited_once_with(context)


from pathlib import Path


# ID: e992534c-06de-4f85-8fad-903ab70050d0
async def test_RuntimeGateEngine():
    engine = RuntimeGateEngine()

    # Happy path 1: per-file dispatch is a contract violation.
    result = await engine.verify(
        Path("foo.py"), {"check_type": "worker_process_classification"}
    )
    assert result.ok is False
    assert "context-level only" in result.message
    assert result.engine_id == engine.engine_id
    assert len(result.violations) == 1

    # Happy path 2: verify_context dispatches to the registered check.
    sentinel = [MagicMock()]
    with patch(
        "mind.logic.engines.runtime_gate._check_worker_process_classification",
        new=AsyncMock(return_value=sentinel),
    ) as mock_check:
        context = MagicMock()
        findings = await engine.verify_context(
            context, {"check_type": "worker_process_classification"}
        )
        mock_check.assert_awaited_once_with(context)
        assert findings is sentinel

    # Happy path 3: unsupported check_type surfaces a HIGH finding.
    with patch(
        "mind.logic.engines.runtime_gate._check_worker_process_classification",
        new=AsyncMock(),
    ) as mock_check:
        findings = await engine.verify_context(MagicMock(), {"check_type": "nope"})
        mock_check.assert_not_awaited()
        assert len(findings) == 1
        assert "unsupported" in findings[0].message


from mind.logic.engines.runtime_gate import heartbeat_retention_hours


# ID: 0810fc55-f44e-4007-b0c3-145c88cf4f75
def test_heartbeat_retention_hours():
    config = MagicMock()
    config.blackboard.telemetry_subject_prefixes = ["worker."]
    config.blackboard.telemetry_ttl_days = 7

    with patch(
        "shared.infrastructure.intent.operational_config.load_operational_config",
        return_value=config,
    ):
        result = heartbeat_retention_hours()

    assert result == 7 * 24.0


from mind.logic.engines.runtime_gate import max_interval_lookback_hours


# ID: 291d1713-a7db-44ca-9488-f641abb5d1e1
def test_max_interval_lookback_hours():
    # Floor case: required window below 24h, so the minimum lookback applies.
    assert max_interval_lookback_hours(60) == 24.0

    # Large declared interval: required window (11 * declared) exceeds the floor.
    declared = 86400  # 24 hours in seconds
    expected = (11 * declared) / 3600.0
    result = max_interval_lookback_hours(declared)
    assert result == expected
    assert result > 24.0





# ID: d5b16773-6eb4-47c8-9d6f-f5141851603b
async def test_RuntimeGateEngine_verify() -> None:
    engine = RuntimeGateEngine.__new__(RuntimeGateEngine)
    engine.engine_id = "runtime_gate"

    file_path = Path("/tmp/example.py")
    params: dict[str, Any] = {"check_type": "some_rule"}

    result = await RuntimeGateEngine.verify(engine, file_path, params)

    assert result.ok is False
    assert "runtime_gate.some_rule is context-level only." in result.message
    assert len(result.violations) == 1
    assert "some_rule" in result.violations[0]
    assert "per-file dispatch" in result.violations[0]
    assert result.engine_id == "runtime_gate"
