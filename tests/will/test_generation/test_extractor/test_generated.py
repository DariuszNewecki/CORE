from __future__ import annotations

from unittest.mock import MagicMock

from will.test_generation.test_extractor import TestCodeExtractor


# ID: 1c947235-6ef0-4ab8-a9e1-3167bb039c7f
def test_TestCodeExtractor_extract_passing_tests():
    extractor = TestCodeExtractor()
    extractor._is_fixture = MagicMock(return_value=False)
    extractor._should_include_function = MagicMock(
        side_effect=lambda name, passing, full_name=None: (
            (full_name if full_name else name) in passing
        )
    )

    full_code = (
        "import pytest\n"
        "\n"
        "def test_one():\n"
        "    assert True\n"
        "\n"
        "def test_two():\n"
        "    assert True\n"
        "\n"
        "class TestThing:\n"
        "    def test_method_a(self):\n"
        "        assert True\n"
        "\n"
        "    def test_method_b(self):\n"
        "        assert True\n"
    )

    result = extractor.extract_passing_tests(
        full_code, ["test_one", "TestThing::test_method_a"]
    )

    assert result is not None
    assert "import pytest" in result
    assert "def test_one" in result
    assert "def test_two" not in result
    assert "class TestThing" in result
    assert "def test_method_a" in result
    assert "def test_method_b" not in result


import ast


# ID: c9a613e1-2168-4cf2-9220-b4abd4e00fd2
def test_TestCodeExtractor():
    extractor = TestCodeExtractor()

    full_code = """
import pytest


@pytest.fixture
# ID: 205a4c3f-9cdc-4b53-8fbc-cf103624d363
def sample_fixture():
    return 42


# ID: 81be45ca-18b9-4dd2-8575-0a5c0e97e68e
def test_passing(sample_fixture):
    assert sample_fixture == 42


# ID: 958f15b2-20c9-4179-bde5-49587e01ff56
def test_failing():
    assert False


# ID: cc8a5407-e10c-4d3f-8945-8a27e461c94b
class TestSomething:
    # ID: ef327a6b-3dbf-41cf-85db-e714886d90d0
    def test_method_passing(self):
        assert True

    # ID: 4e8adaed-10cc-45b7-ae10-e70b82992a97
    def test_method_failing(self):
        assert False
"""

    passing_names = ["test_passing", "TestSomething::test_method_passing"]

    result = extractor.extract_passing_tests(full_code, passing_names)

    assert result is not None
    parsed = ast.parse(result)

    top_level_names = []
    for node in parsed.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            top_level_names.append(node.name)
        elif isinstance(node, ast.ClassDef):
            top_level_names.append(node.name)

    assert "test_passing" in top_level_names
    assert "test_failing" not in top_level_names
    assert "TestSomething" in top_level_names

    class_node = next(
        node
        for node in parsed.body
        if isinstance(node, ast.ClassDef) and node.name == "TestSomething"
    )
    method_names = [
        item.name for item in class_node.body if isinstance(item, ast.FunctionDef)
    ]
    assert "test_method_passing" in method_names
    assert "test_method_failing" not in method_names

    import_nodes = [
        node for node in parsed.body if isinstance(node, (ast.Import, ast.ImportFrom))
    ]
    assert import_nodes
