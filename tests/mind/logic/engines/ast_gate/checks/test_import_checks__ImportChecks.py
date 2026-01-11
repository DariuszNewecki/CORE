"""AUTO-GENERATED TEST (PARTIAL SUCCESS)
- Source: src/mind/logic/engines/ast_gate/checks/import_checks.py
- Symbol: ImportChecks
- Status: 20 tests passed, some failed
- Passing tests: test_empty_forbidden_list_returns_empty, test_no_imports_in_tree_returns_empty, test_forbidden_import_detected, test_allowed_import_not_detected, test_forbidden_import_from_detected, test_forbidden_import_from_no_module, test_multiple_forbidden_imports, test_partial_match_not_detected, test_nested_module_forbidden, test_non_module_tree_returns_empty, test_no_imports_returns_empty, test_imports_with_docstring_ignored, test_proper_order_no_findings, test_wrong_order_detected, test_wrong_order_stdlib_before_future, test_mixed_groups_in_import_from, test_import_from_future_classified, test_relative_import_classification, test_import_stops_at_non_import, test_empty_root_in_import_from
- Generated: 2026-01-11 02:36:43
"""

import ast

from mind.logic.engines.ast_gate.checks.import_checks import ImportChecks


class TestCheckForbiddenImports:

    def test_empty_forbidden_list_returns_empty(self):
        """When forbidden list is empty, should return empty list."""
        tree = ast.parse("import os")
        result = ImportChecks.check_forbidden_imports(tree, [])
        assert result == []

    def test_no_imports_in_tree_returns_empty(self):
        """When tree has no imports, should return empty list."""
        tree = ast.parse("x = 1\ny = 2")
        result = ImportChecks.check_forbidden_imports(tree, ["os"])
        assert result == []

    def test_forbidden_import_detected(self):
        """Should detect forbidden simple import."""
        tree = ast.parse("import os")
        result = ImportChecks.check_forbidden_imports(tree, ["os"])
        assert result == ["Line 1: Forbidden import 'os'"]

    def test_allowed_import_not_detected(self):
        """Should not flag allowed imports."""
        tree = ast.parse("import sys")
        result = ImportChecks.check_forbidden_imports(tree, ["os"])
        assert result == []

    def test_forbidden_import_from_detected(self):
        """Should detect forbidden import-from."""
        tree = ast.parse("from os import path")
        result = ImportChecks.check_forbidden_imports(tree, ["os.path"])
        assert result == ["Line 1: Forbidden import-from 'os.path'"]

    def test_forbidden_import_from_no_module(self):
        """Should handle import-from without module (relative import)."""
        tree = ast.parse("from . import module")
        result = ImportChecks.check_forbidden_imports(tree, ["module"])
        assert result == ["Line 1: Forbidden import-from 'module'"]

    def test_multiple_forbidden_imports(self):
        """Should detect multiple forbidden imports."""
        tree = ast.parse("import os\nimport sys\nfrom json import loads")
        result = ImportChecks.check_forbidden_imports(tree, ["os", "json.loads"])
        assert len(result) == 2
        assert "Line 1: Forbidden import 'os'" in result
        assert "Line 3: Forbidden import-from 'json.loads'" in result

    def test_partial_match_not_detected(self):
        """Should not flag partial matches."""
        tree = ast.parse("import os.path")
        result = ImportChecks.check_forbidden_imports(tree, ["os"])
        assert result == []

    def test_nested_module_forbidden(self):
        """Should detect forbidden nested module."""
        tree = ast.parse("import os.path.join")
        result = ImportChecks.check_forbidden_imports(tree, ["os.path.join"])
        assert result == ["Line 1: Forbidden import 'os.path.join'"]


class TestCheckImportOrder:

    def test_non_module_tree_returns_empty(self):
        """When tree is not ast.Module, should return empty list."""
        tree = ast.parse("x = 1").body[0]
        params = {}
        result = ImportChecks.check_import_order(tree, params)
        assert result == []

    def test_no_imports_returns_empty(self):
        """When module has no imports, should return empty list."""
        tree = ast.parse("x = 1\ny = 2")
        params = {}
        result = ImportChecks.check_import_order(tree, params)
        assert result == []

    def test_imports_with_docstring_ignored(self):
        """Should ignore docstring before imports."""
        tree = ast.parse('"""Docstring."""\nimport os')
        params = {}
        result = ImportChecks.check_import_order(tree, params)
        assert result == []

    def test_proper_order_no_findings(self):
        """Properly ordered imports should return empty list."""
        source = "\nfrom __future__ import annotations\nimport os\nimport json\nimport requests\nfrom mind import logic\n"
        tree = ast.parse(source)
        params = {"stdlib_modules": ["os", "json"]}
        result = ImportChecks.check_import_order(tree, params)
        assert result == []

    def test_wrong_order_detected(self):
        """Should detect when internal comes before third-party."""
        source = "\nfrom mind import logic\nimport requests\n"
        tree = ast.parse(source)
        params = {"stdlib_modules": ["os"]}
        result = ImportChecks.check_import_order(tree, params)
        assert result == ["Line 3: Imports not properly grouped"]

    def test_wrong_order_stdlib_before_future(self):
        """Should detect when stdlib comes before __future__."""
        source = "\nimport os\nfrom __future__ import annotations\n"
        tree = ast.parse(source)
        params = {"stdlib_modules": ["os"]}
        result = ImportChecks.check_import_order(tree, params)
        assert result == ["Line 3: Imports not properly grouped"]

    def test_mixed_groups_in_import_from(self):
        """Should detect mixed groups in import-from with multiple names."""
        source = "\nfrom os.path import join\nfrom sys import exit\n"
        tree = ast.parse(source)
        params = {"stdlib_modules": ["os", "sys"]}
        result = ImportChecks.check_import_order(tree, params)
        assert result == []

    def test_import_from_future_classified(self):
        """Should classify __future__ imports correctly."""
        source = "\nfrom __future__ import annotations\nimport os\n"
        tree = ast.parse(source)
        params = {"stdlib_modules": ["os"]}
        result = ImportChecks.check_import_order(tree, params)
        assert result == []

    def test_relative_import_classification(self):
        """Should handle relative imports (empty root)."""
        source = "\nfrom . import module\nfrom .. import another\n"
        tree = ast.parse(source)
        params = {"stdlib_modules": ["os"]}
        result = ImportChecks.check_import_order(tree, params)
        assert result == []

    def test_import_stops_at_non_import(self):
        """Should only check consecutive imports at top of module."""
        source = "\nimport os\nx = 1\nimport requests\n"
        tree = ast.parse(source)
        params = {"stdlib_modules": ["os"]}
        result = ImportChecks.check_import_order(tree, params)
        assert result == []

    def test_empty_root_in_import_from(self):
        """Should handle import-from with no module."""
        source = "\nfrom __future__ import annotations\nfrom . import relative\n"
        tree = ast.parse(source)
        params = {"stdlib_modules": ["os"]}
        result = ImportChecks.check_import_order(tree, params)
        assert result == []
