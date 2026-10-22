from __future__ import annotations

from unittest.mock import MagicMock

from mind.governance.finding_processor import process_findings_with_downgrade


# ID: 329bd15b-c3ef-43e3-876d-aed478726354
def test_process_findings_with_downgrade():
    findings = [
        {
            "rule_id": "dead-rule-1",
            "symbol_key": "mod.symbol_one",
            "severity": "error",
        },
        {
            "rule_id": "dead-rule-1",
            "symbol_key": "mod.symbol_two",
            "severity": "warn",
        },
        {
            "rule_id": "other-rule",
            "symbol_key": "mod.symbol_three",
            "severity": "error",
        },
    ]

    symbol_index = {
        "mod.symbol_one": {
            "entry_point_type": "cli",
            "pattern_name": "main_cli",
            "entry_point_justification": "We export the CLI.",
        },
        "mod.symbol_two": {
            "entry_point_type": "not_allowed",
            "pattern_name": "",
            "entry_point_justification": "",
        },
        "mod.symbol_three": {
            "entry_point_type": "cli",
            "pattern_name": "other",
            "entry_point_justification": "Justification here.",
        },
    }

    allow_list = MagicMock()
    allow_list.__contains__ = MagicMock(side_effect=lambda x: x == "cli")

    dead_rule_ids = ["dead-rule-1", " other ", ""]

    processed, auto_ignored = process_findings_with_downgrade(
        findings=findings,
        symbol_index=symbol_index,
        allow_list=allow_list,
        dead_rule_ids=dead_rule_ids,
        downgrade_to="info",
    )

    assert len(processed) == 3
    assert processed == findings

    assert findings[0]["severity"] == "info"
    assert findings[1]["severity"] == "warn"
    assert findings[2]["severity"] == "error"

    assert len(auto_ignored) == 1
    ignored = auto_ignored[0]
    assert ignored["symbol_key"] == "mod.symbol_one"
    assert ignored["entry_point_type"] == "cli"
    assert ignored["pattern_name"] == "main_cli"
    assert ignored["justification"] == "We export the CLI."
    assert ignored["original_rule_id"] == "dead-rule-1"
    assert ignored["downgraded_to"] == "info"


from mind.governance.finding_processor import safe_symbol_meta


# ID: be6febd4-18ac-455e-8596-50fbd3c1477d
def test_safe_symbol_meta():
    symbol_index = {
        "sym_alpha": {"kind": "function", "line": 42},
        "sym_beta": {"kind": "class", "line": 7},
    }

    result = safe_symbol_meta(symbol_index, "sym_alpha")
    assert result == {"kind": "function", "line": 42}

    # Missing key falls back to empty mapping
    assert safe_symbol_meta(symbol_index, "sym_missing") == {}

    # Falsy stored value (None) also falls back to empty mapping
    symbol_index_with_none = {"sym_gamma": None}
    assert safe_symbol_meta(symbol_index_with_none, "sym_gamma") == {}
