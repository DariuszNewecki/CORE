from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch


# ID: cbae5392-26d7-4fa3-8927-3ef69ce9107e
async def test_normalize_audit_findings():
    from will.audit_violation.normalizer import normalize_audit_findings

    core_context = MagicMock()
    auditor_context = MagicMock()
    auditor_context.load_knowledge_graph = AsyncMock()
    auditor_context.symbols_map = {}
    core_context.auditor_context = auditor_context

    raw_findings = [
        {
            "file_path": "src/foo/bar.py",
            "message": "bad thing",
            "severity": "error",
            "line_number": 10,
            "check_id": "RULE-1",
            "context": {"symbol_a": "Foo.bar"},
        },
        {
            "message": "no path",
            "context": {"symbol_a": "Baz.qux"},
        },
    ]

    mock_session = MagicMock()
    mock_registry = MagicMock()
    mock_registry.session.return_value.__aenter__ = AsyncMock(return_value=mock_session)
    mock_registry.session.return_value.__aexit__ = AsyncMock(return_value=False)

    with (
        patch("body.services.service_registry.service_registry", mock_registry),
        patch(
            "mind.governance.filtered_audit.run_filtered_audit",
            AsyncMock(return_value=(raw_findings, None, None)),
        ),
    ):
        result = await normalize_audit_findings(core_context, "RULE", ["RULE-1"])

    assert len(result) == 2
    assert result[0]["file_path"] == "src/foo/bar.py"
    assert result[0]["message"] == "bad thing"
    assert result[0]["severity"] == "error"
    assert result[0]["line_number"] == 10
    assert result[0]["rule_id"] == "RULE-1"

    assert result[1]["file_path"] == "__symbol_pair__Baz.qux"
    assert result[1]["message"] == "no path"
    assert result[1]["severity"] == "warning"
    assert result[1]["rule_id"] == "RULE"
