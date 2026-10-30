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
