from __future__ import annotations

from unittest.mock import patch

from mind.governance.audit_postprocessor import apply_entry_point_downgrade


# ID: db19d3d2-b05a-4711-b76a-e7fc7386aada
def test_apply_entry_point_downgrade():
    findings = [{"rule_id": "dead_public_symbol", "symbol": "foo"}]
    symbol_index = {"foo": {"kind": "function"}}
    expected_findings = [
        {"rule_id": "dead_public_symbol", "symbol": "foo", "severity": "info"}
    ]
    expected_downgrades = [{"symbol": "foo", "reason": "entry_point"}]

    with patch(
        "mind.governance.audit_postprocessor.process_findings_with_downgrade",
        return_value=(expected_findings, expected_downgrades),
    ) as mock_process:
        result_findings, result_downgrades = apply_entry_point_downgrade(
            findings=findings,
            symbol_index=symbol_index,
        )

    assert result_findings == expected_findings
    assert result_downgrades == expected_downgrades
    mock_process.assert_called_once()
    _, kwargs = mock_process.call_args
    assert kwargs["findings"] == findings
    assert kwargs["symbol_index"] == symbol_index
    assert kwargs["downgrade_to"] == "info"
    assert kwargs["allow_list"] is not None
