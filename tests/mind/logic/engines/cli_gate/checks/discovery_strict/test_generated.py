import ast
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from mind.logic.engines.cli_gate.checks.discovery_strict import (
    DiscoveryStrictCheck,
    _handler_suppresses_import,
    _node_imports_cli,
)
from shared.models import AuditSeverity
from shared.path_resolver import PathResolver


class TestDiscoveryStrictCheck:
    """Tests for DiscoveryStrictCheck class."""

    @pytest.fixture
    def path_resolver(self, tmp_path: Path) -> PathResolver:
        """Create a PathResolver pointing to a temp directory."""
        resolver = MagicMock(spec=PathResolver)
        resolver.repo_root = tmp_path
        return resolver

    @pytest.fixture
    def check(self, path_resolver: PathResolver) -> DiscoveryStrictCheck:
        """Create a DiscoveryStrictCheck instance."""
        return DiscoveryStrictCheck(path_resolver=path_resolver)

    def test_init_sets_path_resolver(self, path_resolver: PathResolver) -> None:
        """Test that __init__ stores the path resolver."""
        check = DiscoveryStrictCheck(path_resolver=path_resolver)
        assert check._path_resolver is path_resolver

    def test_verify_missing_loader(self, check: DiscoveryStrictCheck) -> None:
        """Test verify returns BLOCK finding when loader param is missing."""
        findings = check.verify([], {})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.check_id == "cli_gate.discovery_strict"
        assert finding.severity == AuditSeverity.BLOCK
        assert "missing the 'loader' parameter" in finding.message
        assert finding.file_path == "none"

    def test_verify_empty_loader(self, check: DiscoveryStrictCheck) -> None:
        """Test verify returns BLOCK finding when loader param is empty string."""
        findings = check.verify([], {"loader": ""})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.check_id == "cli_gate.discovery_strict"
        assert finding.severity == AuditSeverity.BLOCK
        assert "missing the 'loader' parameter" in finding.message
        assert finding.file_path == "none"

    def test_verify_missing_loader_whitespace(
        self, check: DiscoveryStrictCheck
    ) -> None:
        """Test verify returns BLOCK finding when loader is only whitespace."""
        findings = check.verify([], {"loader": "   "})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.severity == AuditSeverity.BLOCK
        assert "missing the 'loader' parameter" in finding.message

    def test_verify_loader_file_not_found(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns BLOCK finding when loader file does not exist."""
        findings = check.verify([], {"loader": "nonexistent.py"})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.check_id == "cli_gate.discovery_strict"
        assert finding.severity == AuditSeverity.BLOCK
        assert "not found on disk" in finding.message
        assert finding.file_path == "nonexistent.py"

    def test_verify_parse_error(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns BLOCK finding when loader file cannot be parsed."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text("invalid python syntax @@@", encoding="utf-8")
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.check_id == "cli_gate.discovery_strict"
        assert finding.severity == AuditSeverity.BLOCK
        assert "could not parse" in finding.message
        assert finding.file_path == "loader.py"

    def test_verify_no_cli_imports(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns empty list when loader has no CLI imports."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "import os\nimport sys\ndef run(): pass\n", encoding="utf-8"
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 0

    def test_verify_cli_import_without_try_except(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns empty list when CLI import is not in try/except."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text("import cli.commands\n", encoding="utf-8")
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 0

    def test_verify_cli_import_in_try_without_handler(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns empty list when try has no except handlers."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n    import cli.commands\nfinally:\n    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 0

    def test_verify_cli_import_in_try_with_non_suppressing_handler(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns empty list when except handler does not suppress imports."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n    import cli.commands\nexcept ValueError:\n    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 0

    def test_verify_cli_import_in_try_with_import_suppressing_handler(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns BLOCK finding when cli import is in try with suppressing handler."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n    import cli.commands\nexcept ImportError:\n    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.severity == AuditSeverity.BLOCK
        assert "CLI import inside try/except ImportError" in finding.message
        assert "discovery must be fail-fast" in finding.message
        assert finding.context["handler"] == "ImportError"
        assert finding.context["loader"] == "loader.py"

    def test_verify_cli_import_in_try_with_bare_except(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns BLOCK finding when cli import is in try with bare except."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n    import cli.commands\nexcept:\n    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.severity == AuditSeverity.BLOCK
        assert "CLI import inside try/except bare/multi" in finding.message
        assert finding.context["handler"] == "bare/multi"

    def test_verify_from_cli_import_in_try(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify detects from-style CLI imports in try blocks."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n    from cli import commands\nexcept ImportError:\n    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 1
        assert findings[0].severity == AuditSeverity.BLOCK

    def test_verify_importlib_import_cli(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify detects importlib.import_module('cli.*') calls."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "import importlib\n"
            "try:\n"
            "    importlib.import_module('cli.commands')\n"
            "except ImportError:\n"
            "    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 1
        assert findings[0].severity == AuditSeverity.BLOCK

    def test_verify_multiple_cli_imports_one_finding_per_block(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns one finding per try/except block, not per import."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n    import cli.a\n    import cli.b\nexcept ImportError:\n    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 1

    def test_verify_multiple_try_blocks(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns one finding per violating try/except block."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n"
            "    import cli.a\n"
            "except ImportError:\n"
            "    pass\n"
            "\n"
            "try:\n"
            "    import cli.b\n"
            "except ImportError:\n"
            "    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 2

    def test_verify_first_suppressing_handler_breaks(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify stops at first suppressing handler in multiple handlers."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n"
            "    import cli.a\n"
            "except ValueError:\n"
            "    pass\n"
            "except ImportError:\n"
            "    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 1
        assert findings[0].context["handler"] == "ImportError"

    def test_verify_non_cli_import_ignored(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify ignores non-CLI imports in try/except."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n    import os\nexcept ImportError:\n    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 0

    def test_verify_no_block_level_import(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify ignores try blocks where body has no cli imports."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text(
            "try:\n    x = 1\nexcept ImportError:\n    pass\n",
            encoding="utf-8",
        )
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 0


class TestHandlerSuppressesImport:
    """Tests for _handler_suppresses_import helper."""

    def test_bare_except_handler(self) -> None:
        """Test bare except handler suppresses."""
        handler = ast.ExceptHandler(type=None, body=[], lineno=0, end_lineno=0)
        assert _handler_suppresses_import(handler) is True

    def test_import_error_handler(self) -> None:
        """Test ImportError handler suppresses."""
        node = ast.ExceptHandler(
            type=ast.Name(id="ImportError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is True

    def test_module_not_found_error_handler(self) -> None:
        """Test ModuleNotFoundError handler suppresses."""
        node = ast.ExceptHandler(
            type=ast.Name(id="ModuleNotFoundError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is True

    def test_value_error_handler(self) -> None:
        """Test ValueError handler does not suppress."""
        node = ast.ExceptHandler(
            type=ast.Name(id="ValueError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is False

    def test_key_error_handler(self) -> None:
        """Test KeyError handler does not suppress."""
        node = ast.ExceptHandler(
            type=ast.Name(id="KeyError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is False

    def test_attribute_error_handler(self) -> None:
        """Test AttributeError handler does not suppress."""
        node = ast.ExceptHandler(
            type=ast.Name(id="AttributeError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is False


class TestNodeImportsCli:
    """Tests for _node_imports_cli helper."""

    def test_import_cli_statement(self) -> None:
        """Test import cli.* statement returns True."""
        code = "import cli.commands"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True

    def test_from_cli_import(self) -> None:
        """Test from cli import * returns True."""
        code = "from cli import commands"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True

    def test_from_cli_submodule_import(self) -> None:
        """Test from cli.sub import module returns True."""
        code = "from cli.discovery import loader"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True

    def test_importlib_import_module_call_cli(self) -> None:
        """Test importlib.import_module('cli.*') returns True."""
        code = "importlib.import_module('cli.commands')"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True

    def test_non_cli_import(self) -> None:
        """Test non-CLI import returns False."""
        code = "import os"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is False

    def test_regular_function_definition(self) -> None:
        """Test function definition with no imports returns False."""
        code = "def foo(): pass"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is False

    def test_module_node_with_cli_import(self) -> None:
        """Test full module tree with CLI import returns True."""
        code = "import cli.commands\n"
        tree = ast.parse(code)
        assert _node_imports_cli(tree) is True

    def test_module_node_without_cli_import(self) -> None:
        """Test full module tree without CLI import returns False."""
        code = "import os\nimport sys\n"
        tree = ast.parse(code)
        assert _node_imports_cli(tree) is False

    def test_importlib_with_non_cli_argument(self) -> None:
        """Test importlib.import_module with non-CLI argument returns False."""
        code = "importlib.import_module('os')"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is False

    def test_nested_cli_import_in_function(self) -> None:
        """Test CLI import nested inside function body returns True."""
        code = "def func():\n    import cli.a\n"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True
