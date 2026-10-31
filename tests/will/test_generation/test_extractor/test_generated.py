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
