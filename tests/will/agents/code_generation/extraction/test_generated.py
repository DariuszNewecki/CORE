from __future__ import annotations

from will.agents.code_generation.extraction import repair_basic_syntax


# ID: dfc448da-9ad0-4ee3-a9f0-e6b98981b346
def test_repair_basic_syntax():
    valid_code = "def foo():\n    return 1\n"
    result = repair_basic_syntax(valid_code)
    assert result == valid_code

    invalid_code = "def foo():\nreturn 1"
    repaired = repair_basic_syntax(invalid_code)
    assert repaired == invalid_code


from will.agents.code_generation.extraction import fallback_extract_python


# ID: dbdde8a1-efcc-4171-b0d0-dbc51ac9b612
def test_fallback_extract_python():
    fence = "`" * 3
    lines = [
        "Here is the code you asked for:",
        fence + "python",
        "def add(a, b):",
        "    return a + b",
        fence,
    ]
    text = "\n".join(lines)

    result = fallback_extract_python(text)

    assert result is not None
    assert "def add(a, b):" in result
    assert "return a + b" in result

    assert fallback_extract_python("") is None
