# src/will/test_generation/test_extractor.py

"""
Test Code Extractor

Purpose:
- Extract individual test functions from generated test files.
- Enable saving only passing tests when some tests fail.

Constitutional Alignment:
- Surgical Precision: Extract only what passed validation.
- Code Preservation: Maintain proper imports and fixtures.
"""

from __future__ import annotations

import ast


# ID: 3c8f5a2b-1d4e-4f6a-9c7d-8e9f0a1b2c3d
class TestCodeExtractor:
    """Extract individual test functions from test code."""

    # ID: 57bf5b9d-80f9-4ca0-9a82-00323d12cd46
    def extract_passing_tests(
        self, full_code: str, passing_test_names: list[str]
    ) -> str | None:
        """
        Extract only passing tests from full test code.

        Args:
            full_code: Complete test file content
            passing_test_names: List of test function names that passed
                               (e.g., ['test_one', 'TestClass::test_method'])

        Returns:
            Code containing only passing tests with necessary imports/fixtures,
            or None if extraction fails.
        """
        if not passing_test_names:
            return None

        try:
            tree = ast.parse(full_code)
        except SyntaxError:
            return None

        # Separate module-level code from test definitions
        imports = []
        fixtures = []
        classes_with_tests = {}  # class_name -> (class_node, passing_methods)
        standalone_tests = []

        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                imports.append(node)

            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                # Check if it's a fixture or standalone test
                if self._is_fixture(node):
                    fixtures.append(node)
                elif self._should_include_function(node.name, passing_test_names):
                    standalone_tests.append(node)

            elif isinstance(node, ast.ClassDef):
                # Extract passing methods from test classes
                passing_methods = []
                for item in node.body:
                    if isinstance(item, ast.FunctionDef):
                        full_name = f"{node.name}::{item.name}"
                        if self._should_include_function(
                            item.name, passing_test_names, full_name
                        ):
                            passing_methods.append(item)

                if passing_methods:
                    classes_with_tests[node.name] = (node, passing_methods)

        # Reconstruct code with only passing tests
        if not standalone_tests and not classes_with_tests:
            return None

        new_body = []
        new_body.extend(imports)
        new_body.extend(fixtures)

        # Add test classes with only passing methods
        for class_name, (class_node, passing_methods) in classes_with_tests.items():
            # Create new class with only passing methods
            new_class = ast.ClassDef(
                name=class_node.name,
                bases=class_node.bases,
                keywords=class_node.keywords,
                body=passing_methods,
                decorator_list=class_node.decorator_list,
            )
            new_body.append(new_class)

        # Add standalone passing tests
        new_body.extend(standalone_tests)

        new_tree = ast.Module(body=new_body, type_ignores=[])
        return ast.unparse(new_tree)

    def _is_fixture(self, node: ast.FunctionDef) -> bool:
        """Check if function is a pytest fixture."""
        for decorator in node.decorator_list:
            if isinstance(decorator, ast.Name) and decorator.id == "fixture":
                return True
            if isinstance(decorator, ast.Attribute) and decorator.attr == "fixture":
                return True
        return False

    def _should_include_function(
        self, func_name: str, passing_names: list[str], full_name: str | None = None
    ) -> bool:
        """
        Check if function should be included based on passing test names.

        Args:
            func_name: Simple function name (e.g., 'test_one')
            passing_names: List of passing test identifiers
            full_name: Optional qualified name (e.g., 'TestClass::test_method')
        """
        # Check simple name
        if func_name in passing_names:
            return True

        # Check qualified name (for class methods)
        if full_name and full_name in passing_names:
            return True

        # Handle nested class notation (TestClass::test_method)
        for passing_name in passing_names:
            if "::" in passing_name:
                _, method = passing_name.rsplit("::", 1)
                if method == func_name:
                    return True

        return False
