from __future__ import annotations

from mind.governance.audit_report_writer import build_auto_ignored_markdown


# ID: 748ba78d-7105-4af2-b64b-2a2cf6ffda32
def test_build_auto_ignored_markdown() -> None:
    timestamp = "2024-01-15T10:30:00Z"
    auto_ignored = [
        {
            "entry_point_type": "function",
            "pattern_name": "test_",
            "symbol_key": "mod.b",
        },
        {
            "entry_point_type": "function",
            "pattern_name": "test_",
            "symbol_key": "mod.a",
        },
        {
            "entry_point_type": "class",
            "pattern_name": "Fixture_",
            "symbol_key": "mod.C",
        },
    ]

    result = build_auto_ignored_markdown(timestamp, auto_ignored)

    assert isinstance(result, str)
    assert result.startswith("# Audit Auto-Ignored Symbols")
    assert f"- Generated: `{timestamp}`" in result
    assert "- Total auto-ignored: **3**" in result
    # group headings sorted
    assert "## class" in result
    assert "## function" in result
    assert result.index("## class") < result.index("## function")
    # pattern counts and sorted symbols
    assert "### Pattern: Fixture_  _(n=1)_" in result
    assert "### Pattern: test_  _(n=2)_" in result
    assert result.index("- `mod.a`") < result.index("- `mod.b`")
    assert result.endswith("\n")
