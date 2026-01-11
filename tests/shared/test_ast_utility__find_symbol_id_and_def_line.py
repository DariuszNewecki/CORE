"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/shared/ast_utility.py
- Symbol: find_symbol_id_and_def_line
- Status: 4 tests passed, some failed
- Passing tests: test_find_symbol_id_and_def_line_without_id_tag, test_find_symbol_id_and_def_line_with_invalid_uuid_format, test_find_symbol_id_and_def_line_tag_line_out_of_bounds_negative, test_find_symbol_id_and_def_line_tag_line_out_of_bounds_too_high
- Generated: 2026-01-11 01:09:15
"""

from shared.ast_utility import find_symbol_id_and_def_line


def test_find_symbol_id_and_def_line_without_id_tag():
    source_lines = ["# Some comment", "@decorator", "def my_function():", "    pass"]

    class MockNode:
        pass

    node = MockNode()
    from shared import ast_utility

    original_find_definition_line = ast_utility.find_definition_line
    ast_utility.find_definition_line = lambda n, lines: 3
    result = find_symbol_id_and_def_line(node, source_lines)
    ast_utility.find_definition_line = original_find_definition_line
    assert not result.has_id
    assert result.uuid is None
    assert result.id_tag_line_num is None
    assert result.definition_line_num == 3


def test_find_symbol_id_and_def_line_with_invalid_uuid_format():
    source_lines = ["# ID: not-a-uuid", "@decorator", "def my_function():", "    pass"]

    class MockNode:
        pass

    node = MockNode()
    from shared import ast_utility

    original_find_definition_line = ast_utility.find_definition_line
    ast_utility.find_definition_line = lambda n, lines: 3
    result = find_symbol_id_and_def_line(node, source_lines)
    ast_utility.find_definition_line = original_find_definition_line
    assert not result.has_id
    assert result.uuid is None
    assert result.id_tag_line_num is None
    assert result.definition_line_num == 3


def test_find_symbol_id_and_def_line_tag_line_out_of_bounds_negative():
    source_lines = ["def my_function():", "    pass"]

    class MockNode:
        pass

    node = MockNode()
    from shared import ast_utility

    original_find_definition_line = ast_utility.find_definition_line
    ast_utility.find_definition_line = lambda n, lines: 1
    result = find_symbol_id_and_def_line(node, source_lines)
    ast_utility.find_definition_line = original_find_definition_line
    assert not result.has_id
    assert result.uuid is None
    assert result.id_tag_line_num is None
    assert result.definition_line_num == 1


def test_find_symbol_id_and_def_line_tag_line_out_of_bounds_too_high():
    source_lines = ["def my_function():", "    pass"]

    class MockNode:
        pass

    node = MockNode()
    from shared import ast_utility

    original_find_definition_line = ast_utility.find_definition_line
    ast_utility.find_definition_line = lambda n, lines: 2
    result = find_symbol_id_and_def_line(node, source_lines)
    ast_utility.find_definition_line = original_find_definition_line
    assert not result.has_id
    assert result.uuid is None
    assert result.id_tag_line_num is None
    assert result.definition_line_num == 2
