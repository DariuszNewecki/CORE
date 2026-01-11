"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/body/evaluators/pattern_evaluator.py
- Symbol: format_violations
- Status: 1 tests passed, some failed
- Passing tests: test_format_violations_empty_list
- Generated: 2026-01-11 03:18:55
"""

from body.evaluators.pattern_evaluator import format_violations


def test_format_violations_empty_list():
    """Test that an empty violations list returns the success message."""
    result = format_violations([])
    expected = "✅ No pattern violations found!"
    assert result == expected
