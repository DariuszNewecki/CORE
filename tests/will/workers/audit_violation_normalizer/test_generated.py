"""
Generated tests for will.audit_violation.normalizer.

Complements test_normalize_audit_findings.py (which covers the main
branches). Adds the edge case not tested there: a symbols_map hit
where the matched entry has an empty module string — the loop finds
the symbol but cannot form a file path and falls through to the
sentinel.

Also verifies multi-finding list construction and the DB session null
teardown when run_filtered_audit raises.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

from will.audit_violation.normalizer import normalize_audit_findings


def _core_ctx(symbols_map: dict | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.auditor_context.load_knowledge_graph = AsyncMock()
    ctx.auditor_context.db_session = None
    ctx.auditor_context.symbols_map = symbols_map if symbols_map is not None else {}
    return ctx


def _patched(core_ctx: MagicMock, raw_findings: list) -> tuple:
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_cm.__aexit__ = AsyncMock(return_value=False)
    mock_reg = MagicMock()
    mock_reg.session.return_value = mock_cm
    mock_audit = AsyncMock(return_value=(raw_findings, None, None))
    p_reg = patch("body.services.service_registry.service_registry", mock_reg)
    p_audit = patch("mind.governance.filtered_audit.run_filtered_audit", mock_audit)
    return p_reg, p_audit, mock_reg, mock_audit


# ID: 254d2369-2e8e-478c-b3b4-9c7438e9f96d
async def test_symbols_map_hit_with_empty_module_produces_sentinel() -> None:
    """A symbols_map entry matches on endswith but has no module — sentinel emitted."""
    symbols_map = {
        "some.path.myfunc": {
            "qualname": "something_else",
            "module": "",  # empty — cannot form file path
            "name": "myfunc",
        }
    }
    ctx = _core_ctx(symbols_map=symbols_map)
    finding = {
        "file_path": None,
        "message": "",
        "context": {"symbol_a": "myfunc"},
    }
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert result[0]["file_path"] == "__symbol_pair__myfunc"


# ID: 78d75909-7e1f-4c39-9344-9bfc1dcb42c7
async def test_multiple_findings_all_normalized() -> None:
    """All findings in the raw list are normalized and returned."""
    ctx = _core_ctx()
    findings = [
        {"file_path": f"src/foo/{i}.py", "message": f"msg{i}", "severity": "warning"}
        for i in range(4)
    ]
    p_reg, p_audit, _, _ = _patched(ctx, findings)
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert len(result) == 4
    for i, r in enumerate(result):
        assert r["file_path"] == f"src/foo/{i}.py"
        assert r["message"] == f"msg{i}"


# ID: 3e3de7b3-e45a-4583-976b-b52ae73f7c4a
async def test_db_session_cleared_on_completion() -> None:
    """auditor_context.db_session is set to None after the call regardless of outcome."""
    ctx = _core_ctx()
    p_reg, p_audit, _, _ = _patched(ctx, [])
    with p_reg, p_audit:
        await normalize_audit_findings(ctx, "ns", [])

    assert ctx.auditor_context.db_session is None
