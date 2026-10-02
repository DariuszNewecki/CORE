from __future__ import annotations

from unittest.mock import MagicMock, patch

from mind.logic.engines.contracts_gate import ContractsGateEngine


# ID: e9927b14-eb09-4e9c-b08e-6e876805a3b6
async def test_ContractsGateEngine_verify_context():
    engine = ContractsGateEngine()
    engine.engine_id = "contracts_gate"

    context = MagicMock()
    params = {"check_type": "layer_scope_coherence"}

    expected_findings = [MagicMock(), MagicMock()]

    with patch(
        "mind.logic.engines.contracts_gate._check_layer_scope_coherence",
        return_value=expected_findings,
    ) as mock_check:
        result = await engine.verify_context(context, params)

    mock_check.assert_called_once_with(context)
    assert result == expected_findings


from pathlib import Path


# ID: 074594b1-2fca-48a8-ba85-98352e304344
async def test_contracts_gate_engine_verify() -> None:
    engine = ContractsGateEngine()
    engine.engine_id = "contracts_gate"

    file_path = Path("/tmp/some_file.py")
    params = {"check_type": "some_check"}

    result = await engine.verify(file_path, params)

    assert result.ok is False
    assert "contracts_gate.some_check is context-level only." in result.message
    assert result.engine_id == "contracts_gate"
    assert len(result.violations) == 1
    assert "some_check" in result.violations[0]


import asyncio


# ID: f8f61296-6370-41de-88e4-b34c1ac388c7
def test_ContractsGateEngine():
    engine = ContractsGateEngine()

    params = {"check_type": "layer_scope_coherence"}

    result = asyncio.run(engine.verify(Path("/tmp/some_file.py"), params))

    assert result.ok is False
    assert "layer_scope_coherence" in result.message
    assert result.engine_id == engine.engine_id
    assert len(result.violations) == 1
    assert "layer_scope_coherence" in result.violations[0]
