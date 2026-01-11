"""AUTO-GENERATED TEST (PROMOTED)
- Source: src/body/analyzers/symbol_extractor.py
- Symbol: SymbolMetadata
- Status: verified_in_sandbox
- Generated: 2026-01-11 02:46:17
"""

import pytest
from body.analyzers.symbol_extractor import SymbolMetadata

# SymbolMetadata is a dataclass-like class, not async (no async def __init__)
# All test functions will be regular def, not async


def test_symbol_metadata_initialization():
    """Test basic initialization with all fields."""
    metadata = SymbolMetadata(
        name="test_function",
        qualname="TestClass.test_function",
        symbol_path="/path/to/file.py::TestClass.test_function",
        type="function",
        line_number=42,
        docstring="This is a test function.",
        is_public=True,
        complexity="medium",
        parameters=["self", "arg1", "arg2"],
        decorators=["@pytest.mark.parametrize", "@decorator"]
    )

    assert metadata.name == "test_function"
    assert metadata.qualname == "TestClass.test_function"
    assert metadata.symbol_path == "/path/to/file.py::TestClass.test_function"
    assert metadata.type == "function"
    assert metadata.line_number == 42
    assert metadata.docstring == "This is a test function."
    assert metadata.is_public == True
    assert metadata.complexity == "medium"
    assert metadata.parameters == ["self", "arg1", "arg2"]
    assert metadata.decorators == ["@pytest.mark.parametrize", "@decorator"]


def test_symbol_metadata_with_none_docstring():
    """Test initialization with None docstring."""
    metadata = SymbolMetadata(
        name="private_func",
        qualname="_private_func",
        symbol_path="/src/module.py::_private_func",
        type="function",
        line_number=10,
        docstring=None,
        is_public=False,
        complexity="low",
        parameters=[],
        decorators=[]
    )

    assert metadata.docstring is None
    assert metadata.is_public == False
    assert metadata.parameters == []
    assert metadata.decorators == []


def test_symbol_metadata_async_function_type():
    """Test with async_function type."""
    metadata = SymbolMetadata(
        name="async_task",
        qualname="async_task",
        symbol_path="/app/tasks.py::async_task",
        type="async_function",
        line_number=5,
        docstring="Async task docstring",
        is_public=True,
        complexity="high",
        parameters=["session", "data"],
        decorators=["@asynccontextmanager"]
    )

    assert metadata.type == "async_function"
    assert metadata.complexity == "high"
    assert metadata.parameters == ["session", "data"]


def test_symbol_metadata_class_type():
    """Test with class type."""
    metadata = SymbolMetadata(
        name="TestClass",
        qualname="TestClass",
        symbol_path="/tests/test_module.py::TestClass",
        type="class",
        line_number=1,
        docstring="Test class documentation",
        is_public=True,
        complexity="medium",
        parameters=[],  # Classes typically have empty parameters
        decorators=["@dataclass", "@pytest.fixture"]
    )

    assert metadata.type == "class"
    assert metadata.parameters == []
    assert len(metadata.decorators) == 2


def test_symbol_metadata_empty_strings():
    """Test with empty strings in fields that allow them."""
    metadata = SymbolMetadata(
        name="",
        qualname="",
        symbol_path=".py::",
        type="function",
        line_number=0,
        docstring="",
        is_public=False,
        complexity="low",
        parameters=[],
        decorators=[]
    )

    assert metadata.name == ""
    assert metadata.qualname == ""
    assert metadata.symbol_path == ".py::"
    assert metadata.docstring == ""
    assert metadata.complexity == "low"


def test_symbol_metadata_with_unicode():
    """Test with Unicode characters in string fields."""
    metadata = SymbolMetadata(
        name="café",
        qualname="Module.café",
        symbol_path="/path/with spaces/file.py::Module.café",
        type="function",
        line_number=100,
        docstring="Function with Unicode… character",
        is_public=True,
        complexity="medium",
        parameters=["param1", "param2"],
        decorators=["@decorator"]
    )

    assert metadata.name == "café"
    assert metadata.qualname == "Module.café"
    assert "spaces" in metadata.symbol_path
    assert "…" in metadata.docstring  # Using Unicode ellipsis, not three dots


def test_symbol_metadata_equality():
    """Test that two instances with same values are equal."""
    metadata1 = SymbolMetadata(
        name="func",
        qualname="func",
        symbol_path="/test.py::func",
        type="function",
        line_number=1,
        docstring="Test",
        is_public=True,
        complexity="low",
        parameters=[],
        decorators=[]
    )

    metadata2 = SymbolMetadata(
        name="func",
        qualname="func",
        symbol_path="/test.py::func",
        type="function",
        line_number=1,
        docstring="Test",
        is_public=True,
        complexity="low",
        parameters=[],
        decorators=[]
    )

    # Compare individual fields
    assert metadata1.name == metadata2.name
    assert metadata1.qualname == metadata2.qualname
    assert metadata1.symbol_path == metadata2.symbol_path
    assert metadata1.type == metadata2.type
    assert metadata1.line_number == metadata2.line_number
    assert metadata1.docstring == metadata2.docstring
    assert metadata1.is_public == metadata2.is_public
    assert metadata1.complexity == metadata2.complexity
    assert metadata1.parameters == metadata2.parameters
    assert metadata1.decorators == metadata2.decorators


def test_symbol_metadata_different_values():
    """Test that instances with different values are not equal."""
    metadata1 = SymbolMetadata(
        name="func1",
        qualname="func1",
        symbol_path="/test.py::func1",
        type="function",
        line_number=1,
        docstring="Test1",
        is_public=True,
        complexity="low",
        parameters=["a"],
        decorators=["@dec1"]
    )

    metadata2 = SymbolMetadata(
        name="func2",
        qualname="func2",
        symbol_path="/test.py::func2",
        type="function",
        line_number=2,
        docstring="Test2",
        is_public=False,
        complexity="high",
        parameters=["a", "b"],
        decorators=["@dec2"]
    )

    assert metadata1.name != metadata2.name
    assert metadata1.qualname != metadata2.qualname
    assert metadata1.symbol_path != metadata2.symbol_path
    assert metadata1.line_number != metadata2.line_number
    assert metadata1.docstring != metadata2.docstring
    assert metadata1.is_public != metadata2.is_public
    assert metadata1.complexity != metadata2.complexity
    assert metadata1.parameters != metadata2.parameters
    assert metadata1.decorators != metadata2.decorators
