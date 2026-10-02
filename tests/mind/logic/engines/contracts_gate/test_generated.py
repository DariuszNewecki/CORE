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
