"""
Unit tests for normalize_audit_findings in audit_violation_normalizer.

Both service_registry and run_filtered_audit are lazy-imported inside
the function body, so they must be patched at their source modules
(body.services.service_registry.service_registry and
mind.governance.filtered_audit.run_filtered_audit) rather than at the
importer's namespace.

Coverage: dict vs object finding normalisation, all file-path fallback
branches (ctx.file_path, ctx.file, ctx.module_path, symbols_map qualname,
symbols_map endswith, sentinel), DB session lifecycle, and rule_id
resolution.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from will.workers.audit_violation_normalizer import normalize_audit_findings

pytestmark = [pytest.mark.integration]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _core_ctx(symbols_map: dict | None = None) -> MagicMock:
    ctx = MagicMock()
    ctx.auditor_context.load_knowledge_graph = AsyncMock()
    ctx.auditor_context.db_session = None
    ctx.auditor_context.symbols_map = symbols_map if symbols_map is not None else {}
    return ctx


def _patched(core_ctx: MagicMock, raw_findings: list) -> tuple:
    """Return (patch_reg, patch_audit) context managers wired to raw_findings."""
    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=MagicMock())
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_reg = MagicMock()
    mock_reg.session.return_value = mock_cm

    mock_audit = AsyncMock(return_value=(raw_findings, None, None))

    p_reg = patch("body.services.service_registry.service_registry", mock_reg)
    p_audit = patch("mind.governance.filtered_audit.run_filtered_audit", mock_audit)
    return p_reg, p_audit, mock_reg, mock_audit


# ---------------------------------------------------------------------------
# Dict findings
# ---------------------------------------------------------------------------


# ID: 60384674-fdfc-42bc-b206-983c3fc3ba08
async def test_dict_finding_all_fields_normalised():
    ctx = _core_ctx()
    finding = {
        "file_path": "src/body/foo.py",
        "message": "violation msg",
        "severity": "error",
        "line_number": 42,
        "check_id": "my.rule",
        "context": {"k": "v"},
    }
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", ["my.rule"])

    assert len(result) == 1
    r = result[0]
    assert r["file_path"] == "src/body/foo.py"
    assert r["message"] == "violation msg"
    assert r["severity"] == "error"
    assert r["line_number"] == 42
    assert r["rule_id"] == "my.rule"
    assert r["context"] == {"k": "v"}


# ID: 5da14fed-1f71-4b84-b3f0-0b857c1752f5
async def test_dict_finding_no_check_id_falls_back_to_rule_namespace():
    ctx = _core_ctx()
    finding = {"file_path": "src/x.py", "message": "m", "severity": "warning"}
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "fallback.ns", [])

    assert result[0]["rule_id"] == "fallback.ns"


# ID: f6423abb-0699-4f63-828b-3171877c8ff7
async def test_empty_findings_returns_empty_list():
    ctx = _core_ctx()
    p_reg, p_audit, _, _ = _patched(ctx, [])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert result == []


# ---------------------------------------------------------------------------
# Object findings
# ---------------------------------------------------------------------------


# ID: 2b178d18-6b0d-48e1-82a3-185f4046b806
async def test_object_finding_all_attrs_normalised():
    ctx = _core_ctx()
    obj = MagicMock()
    obj.file_path = "src/body/bar.py"
    obj.message = "obj msg"
    obj.severity = "error"
    obj.line_number = 7
    obj.check_id = "obj.rule"
    obj.context = {"a": 1}
    p_reg, p_audit, _, _ = _patched(ctx, [obj])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", ["obj.rule"])

    r = result[0]
    assert r["file_path"] == "src/body/bar.py"
    assert r["message"] == "obj msg"
    assert r["severity"] == "error"
    assert r["line_number"] == 7
    assert r["rule_id"] == "obj.rule"
    assert r["context"] == {"a": 1}


# ID: 99fa0172-3ad5-4d11-b525-b83b24c1a358
async def test_object_finding_missing_optional_attrs_uses_defaults():
    ctx = _core_ctx()
    obj = MagicMock(spec=[])  # no attributes at all
    p_reg, p_audit, _, _ = _patched(ctx, [obj])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "default.ns", [])

    r = result[0]
    assert r["message"] == ""
    assert r["severity"] == "warning"
    assert r["line_number"] is None
    assert r["rule_id"] == "default.ns"


# ---------------------------------------------------------------------------
# File-path fallback branches
# ---------------------------------------------------------------------------


# ID: f46b6d1f-0a77-4e2f-be49-53ee3fe9fdcb
async def test_file_path_recovered_from_ctx_file_path():
    ctx = _core_ctx()
    finding = {
        "file_path": None,
        "message": "",
        "context": {"file_path": "src/recovered.py"},
    }
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert result[0]["file_path"] == "src/recovered.py"


# ID: db99afce-3c07-4155-b8eb-28e40f80a94a
async def test_file_path_recovered_from_ctx_file():
    ctx = _core_ctx()
    finding = {
        "file_path": None,
        "message": "",
        "context": {"file": "src/via_file.py"},
    }
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert result[0]["file_path"] == "src/via_file.py"


# ID: b824d881-2b2b-4033-8730-0481a101bd56
async def test_file_path_recovered_from_ctx_module_path():
    ctx = _core_ctx()
    finding = {
        "file_path": None,
        "message": "",
        "context": {"module_path": "src/via_module.py"},
    }
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert result[0]["file_path"] == "src/via_module.py"


# ID: c81509c2-d38d-406f-b5e7-60e7ec1c1f68
async def test_file_path_recovered_from_symbols_map_qualname_match():
    symbols_map = {
        "body.foo.MyClass": {
            "qualname": "MyClass",
            "module": "body.foo",
            "name": "MyClass",
        }
    }
    ctx = _core_ctx(symbols_map=symbols_map)
    finding = {
        "file_path": None,
        "message": "",
        "context": {"symbol_a": "MyClass"},
    }
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert result[0]["file_path"] == "src/body/foo.py"


# ID: 91f8d1dd-cb8f-4909-a5ff-11cd46b36ce6
async def test_file_path_recovered_from_symbols_map_endswith_match():
    symbols_map = {
        "body.bar.helper": {
            "qualname": "something_else",
            "module": "body.bar",
            "name": "helper",
        }
    }
    ctx = _core_ctx(symbols_map=symbols_map)
    finding = {
        "file_path": None,
        "message": "",
        "context": {"symbol_a": "helper"},
    }
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert result[0]["file_path"] == "src/body/bar.py"


# ID: 0277d88b-a9ad-43eb-a7db-bfc9cd9388d4
async def test_file_path_sentinel_when_no_recovery_possible():
    ctx = _core_ctx(symbols_map={})
    finding = {
        "file_path": None,
        "message": "",
        "context": {"symbol_a": "orphan_sym"},
    }
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert result[0]["file_path"] == "__symbol_pair__orphan_sym"


# ID: f087b8bd-5b3b-4b30-b89b-a83a979cbc97
async def test_file_path_sentinel_unknown_when_no_symbol_a():
    ctx = _core_ctx()
    finding = {"file_path": None, "message": "", "context": {}}
    p_reg, p_audit, _, _ = _patched(ctx, [finding])
    with p_reg, p_audit:
        result = await normalize_audit_findings(ctx, "ns", [])

    assert result[0]["file_path"] == "__symbol_pair__unknown"


# ---------------------------------------------------------------------------
# Session lifecycle
# ---------------------------------------------------------------------------


# ID: 9cea2d5d-c8f3-4f6f-836b-1d2ad8f36c99
async def test_db_session_set_during_call_and_cleared_after():
    ctx = _core_ctx()
    fake_session = MagicMock()
    captured: dict = {}

    mock_cm = AsyncMock()
    mock_cm.__aenter__ = AsyncMock(return_value=fake_session)
    mock_cm.__aexit__ = AsyncMock(return_value=False)

    mock_reg = MagicMock()
    mock_reg.session.return_value = mock_cm

    async def _capture(auditor_context, rule_ids):
        captured["session"] = auditor_context.db_session
        return ([], None, None)

    with (
        patch("body.services.service_registry.service_registry", mock_reg),
        patch("mind.governance.filtered_audit.run_filtered_audit", side_effect=_capture),
    ):
        await normalize_audit_findings(ctx, "ns", [])

    assert captured["session"] is fake_session
    assert ctx.auditor_context.db_session is None


# ---------------------------------------------------------------------------
# rule_ids forwarding
# ---------------------------------------------------------------------------


# ID: b092db9f-1492-4316-b12a-8d146eba70b2
async def test_rule_ids_forwarded_to_filtered_audit():
    ctx = _core_ctx()
    p_reg, p_audit, _, mock_audit = _patched(ctx, [])
    rule_ids = ["rule.one", "rule.two"]
    with p_reg, p_audit:
        await normalize_audit_findings(ctx, "ns", rule_ids)

    mock_audit.assert_called_once()
    _, kwargs = mock_audit.call_args
    assert kwargs["rule_ids"] == rule_ids
