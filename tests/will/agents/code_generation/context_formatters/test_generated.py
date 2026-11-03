from __future__ import annotations

from will.agents.code_generation.context_formatters import format_similar_symbols


# ID: ec2c0508-cabd-45cd-afbd-e986309f7dbc
def test_format_similar_symbols():
    long_code = "x = 1\n" * 20
    short_code = "x = 1"

    items = [
        {
            "item_type": "code",
            "name": "foo",
            "summary": "A summary.",
            "content": long_code,
        },
        {
            "item_type": "code",
            "name": "short",
            "summary": "Too short.",
            "content": short_code,
        },
        {
            "item_type": "doc",
            "name": "ignored",
            "content": long_code,
        },
        {
            "item_type": "code",
            "name": "empty",
            "content": "",
        },
    ]

    result = format_similar_symbols(items)

    assert "### foo" in result
    assert "A summary." in result
    assert long_code[:500] in result
    assert "short" not in result
    assert "ignored" not in result
    assert "empty" not in result

    assert format_similar_symbols([]) == "No similar implementations found"


from will.agents.code_generation.context_formatters import format_dependencies


# ID: 803a8625-6bef-4903-95b8-ef1d42ee578d
def test_format_dependencies():
    items = [
        {
            "item_type": "code",
            "name": "foo",
            "path": "pkg/foo.py",
            "signature": "foo(x: int) -> str",
        },
        {"item_type": "symbol", "name": "bar", "path": "pkg/bar.py", "signature": ""},
        {"item_type": "doc", "name": "ignored", "path": "doc.md", "signature": ""},
        {
            "item_type": "code",
            "name": "foo",
            "path": "pkg/dupe.py",
            "signature": "dupe()",
        },
    ]

    result = format_dependencies(items)

    assert "- `foo` from `pkg/foo.py`" in result
    assert "Signature: `foo(x: int) -> str`" in result
    assert "- `bar` from `pkg/bar.py`" in result
    assert "ignored" not in result
    assert "pkg/dupe.py" not in result
    assert result.count("`foo`") == 1
