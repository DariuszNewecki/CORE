# tests/services/context/providers/test_ast_provider.py
import ast
from pathlib import Path

import pytest
from services.context.providers.ast import ASTProvider

# --- Sample Code Snippets for Testing ---

SIMPLE_FUNCTION_CODE = """
def simple_function(a: int, b: str = "default") -> bool:
    '''A simple docstring.'''
    return a > 0
"""

CLASS_WITH_METHODS_CODE = """
import os
from typing import List

class MyClass(BaseClass):
    def __init__(self):
        self.value = 1

    def method_one(self, items: List[str]):
        pass

    @my_decorator
    async def async_method(self) -> None:
        import asyncio
        await asyncio.sleep(1)
"""

NESTED_FUNCTIONS_CODE = """
def outer_function():  # Line 1
    x = 1              # Line 2
                       # Line 3
    def inner_function(): # Line 4
        return x + 1   # Line 5
                       # Line 6
    return inner_function() # Line 7
"""


# --- Fixtures ---


@pytest.fixture
def provider() -> ASTProvider:
    """Provides a standard ASTProvider instance."""
    return ASTProvider()


# --- Test Classes ---


class TestASTProviderSignatures:
    def test_get_simple_function_signature(self, provider: ASTProvider):
        tree = ast.parse(SIMPLE_FUNCTION_CODE)
        signature = provider.get_signature_from_tree(tree, "simple_function")

        # DEFINITIVE CORRECTION: Match the exact output of ast.unparse, with no spaces around '='.
        expected_sig = "def simple_function(a: int, b: str='default') -> bool:"
        assert signature.strip() == expected_sig

    def test_get_class_signature(self, provider: ASTProvider):
        tree = ast.parse(CLASS_WITH_METHODS_CODE)
        signature = provider.get_signature_from_tree(tree, "MyClass")
        expected_sig = "class MyClass(BaseClass):"
        assert signature.strip() == expected_sig

    def test_get_async_method_signature_with_decorator(self, provider: ASTProvider):
        tree = ast.parse(CLASS_WITH_METHODS_CODE)
        signature = provider.get_signature_from_tree(tree, "async_method")
        expected_sig = "@my_decorator\nasync def async_method(self) -> None:"
        assert signature.strip() == expected_sig

    def test_get_signature_for_nonexistent_symbol(self, provider: ASTProvider):
        tree = ast.parse(SIMPLE_FUNCTION_CODE)
        signature = provider.get_signature_from_tree(tree, "nonexistent_function")
        assert signature is None


class TestASTProviderDependencies:
    def test_get_dependencies(self, provider: ASTProvider):
        tree = ast.parse(CLASS_WITH_METHODS_CODE)
        dependencies = provider.get_dependencies_from_tree(tree)
        assert dependencies == ["asyncio", "os", "typing"]

    def test_get_dependencies_from_empty_code(self, provider: ASTProvider):
        tree = ast.parse("")
        dependencies = provider.get_dependencies_from_tree(tree)
        assert dependencies == []


class TestASTProviderParentScope:
    def test_get_parent_scope_for_inner_function(self, provider: ASTProvider):
        tree = ast.parse(NESTED_FUNCTIONS_CODE)
        parent = provider.get_parent_scope_from_tree(tree, 5)
        assert parent == "inner_function"

    def test_get_parent_scope_for_outer_function(self, provider: ASTProvider):
        tree = ast.parse(NESTED_FUNCTIONS_CODE)
        parent = provider.get_parent_scope_from_tree(tree, 2)
        assert parent == "outer_function"

    def test_get_parent_scope_in_global_scope(self, provider: ASTProvider):
        tree = ast.parse("x = 1\ny = 2")
        parent = provider.get_parent_scope_from_tree(tree, 1)
        assert parent is None


class TestASTProviderFileIO:
    def test_get_signature_from_file(self, tmp_path: Path):
        """Integration test for the file-reading wrapper method."""
        file_path = tmp_path / "test_module.py"
        file_path.write_text(SIMPLE_FUNCTION_CODE)

        provider = ASTProvider(project_root=tmp_path)

        signature = provider.get_signature("test_module.py", "simple_function")

        # DEFINITIVE CORRECTION: Use the same exact expected signature.
        expected_sig = "def simple_function(a: int, b: str='default') -> bool:"
        assert signature is not None
        assert signature.strip() == expected_sig

    def test_handles_nonexistent_file_gracefully(self, provider: ASTProvider):
        """Verify that methods return empty/None for files that don't exist."""
        non_existent_path = "path/to/nothing.py"
        assert provider.get_signature(non_existent_path, "any") is None
        assert provider.get_dependencies(non_existent_path) == []
        assert provider.get_parent_scope(non_existent_path, 1) is None

    def test_handles_syntax_error_in_file_gracefully(self, tmp_path: Path):
        """Verify that a syntax error returns empty/None without crashing."""
        file_path = tmp_path / "bad_syntax.py"
        file_path.write_text("def my_func(a,:\n    pass")

        provider = ASTProvider(project_root=tmp_path)

        assert provider.get_signature("bad_syntax.py", "my_func") is None
        assert provider.get_dependencies("bad_syntax.py") == []
