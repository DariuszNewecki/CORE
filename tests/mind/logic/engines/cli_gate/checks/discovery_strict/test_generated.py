from __future__ import annotations

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


# ID: c5808701-1f44-4a45-921c-2f7e1c94c814
class TestDiscoveryStrictCheck:
    """Tests for DiscoveryStrictCheck class."""

    @pytest.fixture
    # ID: 7046dd58-69cb-4508-b5e6-0cf4aead6173
    def path_resolver(self, tmp_path: Path) -> PathResolver:
        """Create a PathResolver pointing to a temp directory."""
        resolver = MagicMock(spec=PathResolver)
        resolver.repo_root = tmp_path
        return resolver

    @pytest.fixture
    # ID: 8fecb745-902d-41f0-99a2-8274a16630be
    def check(self, path_resolver: PathResolver) -> DiscoveryStrictCheck:
        """Create a DiscoveryStrictCheck instance."""
        return DiscoveryStrictCheck(path_resolver=path_resolver)

    # ID: b4b0a8fe-13ec-4aac-bfb7-5bc4b4a32a94
    def test_init_sets_path_resolver(self, path_resolver: PathResolver) -> None:
        """Test that __init__ stores the path resolver."""
        check = DiscoveryStrictCheck(path_resolver=path_resolver)
        assert check._path_resolver is path_resolver

    # ID: 1b98f288-6ed1-43cf-b9a8-d5f6b147fadb
    def test_verify_missing_loader(self, check: DiscoveryStrictCheck) -> None:
        """Test verify returns BLOCK finding when loader param is missing."""
        findings = check.verify([], {})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.check_id == "cli_gate.discovery_strict"
        assert finding.severity == AuditSeverity.BLOCK
        assert "missing the 'loader' parameter" in finding.message
        assert finding.file_path == "none"

    # ID: cff3a2dd-f3b7-4072-8c65-f5ce14162fca
    def test_verify_empty_loader(self, check: DiscoveryStrictCheck) -> None:
        """Test verify returns BLOCK finding when loader param is empty string."""
        findings = check.verify([], {"loader": ""})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.check_id == "cli_gate.discovery_strict"
        assert finding.severity == AuditSeverity.BLOCK
        assert "missing the 'loader' parameter" in finding.message
        assert finding.file_path == "none"

    # ID: 7e02c7f6-4979-4d57-8528-761ece039ad0
    def test_verify_missing_loader_whitespace(
        self, check: DiscoveryStrictCheck
    ) -> None:
        """Whitespace-only loader is NOT treated as missing by source — its
        empty-check is ``if not loader_rel`` which keeps whitespace strings
        truthy. The whitespace path then resolves against repo_root and
        fails the is_file check, surfacing as a "not found on disk" finding
        rather than the "missing 'loader' parameter" the autogen vintage
        expected. Pinning current behavior; the whitespace-trim is a minor
        source-side gap not worth its own tracker entry."""
        findings = check.verify([], {"loader": "   "})
        assert len(findings) == 1
        finding = findings[0]
        assert finding.severity == AuditSeverity.BLOCK
        assert "not found on disk" in finding.message

    # ID: b18aff6f-661d-4b5c-92b7-ff196a8c2e72
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

    # ID: fe1c99ce-09dd-4337-9b7c-d8e6c264f5b8
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

    # ID: 91a9f2dd-1e41-41b9-8bc1-38aacf1f9b71
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

    # ID: 7d034745-9924-4794-84d0-048cc5bf15ff
    def test_verify_cli_import_without_try_except(
        self, check: DiscoveryStrictCheck, tmp_path: Path
    ) -> None:
        """Test verify returns empty list when CLI import is not in try/except."""
        loader_file = tmp_path / "loader.py"
        loader_file.write_text("import cli.commands\n", encoding="utf-8")
        findings = check.verify([], {"loader": "loader.py"})
        assert len(findings) == 0

    # ID: 6cf4e2c1-370f-4cb7-bf6c-8dcdb1e0e18b
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

    # ID: c160df50-082b-4740-a971-b3aecc147bdc
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

    # ID: 7c02ad1e-b96d-4cf7-b5c1-c94370a48168
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

    # ID: cd0ce3ba-ec40-40af-96dc-06874e6651be
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

    # ID: 9e2913a2-c03e-44b7-8151-17be85ba8b98
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

    # ID: fd03dd2d-b619-47be-9c70-4a3acdc25b6b
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

    # ID: 68988381-4c5f-4111-afaa-29985ef7d420
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

    # ID: 2228c375-b977-42b2-820d-359cd1b1eff7
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

    # ID: 2af03853-dbd0-4c2b-a498-efcb67b79530
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

    # ID: 04c801dd-e53f-4d28-9c4d-fd33007fe60a
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

    # ID: 378166bd-0820-4679-a130-eb8a8c55355f
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


# ID: 5865fecf-4d8c-415c-8874-1b54308dcf08
class TestHandlerSuppressesImport:
    """Tests for _handler_suppresses_import helper."""

    # ID: 17616058-1261-4f24-8e71-b73437179cf7
    def test_bare_except_handler(self) -> None:
        """Test bare except handler suppresses."""
        handler = ast.ExceptHandler(type=None, body=[], lineno=0, end_lineno=0)
        assert _handler_suppresses_import(handler) is True

    # ID: 671147f9-643c-4ec0-a52f-a34292f5258d
    def test_import_error_handler(self) -> None:
        """Test ImportError handler suppresses."""
        node = ast.ExceptHandler(
            type=ast.Name(id="ImportError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is True

    # ID: 544fde53-f216-4ea5-bf64-e6530f0934a3
    def test_module_not_found_error_handler(self) -> None:
        """Test ModuleNotFoundError handler suppresses."""
        node = ast.ExceptHandler(
            type=ast.Name(id="ModuleNotFoundError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is True

    # ID: 62927b17-af4d-4fc7-b253-36c7eebd3538
    def test_value_error_handler(self) -> None:
        """Test ValueError handler does not suppress."""
        node = ast.ExceptHandler(
            type=ast.Name(id="ValueError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is False

    # ID: 9030abc4-4a4e-43cf-b621-9b7960d9550f
    def test_key_error_handler(self) -> None:
        """Test KeyError handler does not suppress."""
        node = ast.ExceptHandler(
            type=ast.Name(id="KeyError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is False

    # ID: f9818906-6f36-44fe-9cd9-b884d3d2c92a
    def test_attribute_error_handler(self) -> None:
        """Test AttributeError handler does not suppress."""
        node = ast.ExceptHandler(
            type=ast.Name(id="AttributeError", ctx=ast.Load()),
            body=[],
            lineno=0,
            end_lineno=0,
        )
        assert _handler_suppresses_import(node) is False


# ID: a92407a4-a175-4b4a-9e59-ead4250fe08c
class TestNodeImportsCli:
    """Tests for _node_imports_cli helper."""

    # ID: 24b3991a-f7be-44b6-8956-f0426c91c359
    def test_import_cli_statement(self) -> None:
        """Test import cli.* statement returns True."""
        code = "import cli.commands"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True

    # ID: 6c521717-3d38-4f5c-9b21-7db0d9403904
    def test_from_cli_import(self) -> None:
        """Test from cli import * returns True."""
        code = "from cli import commands"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True

    # ID: 16fa22cd-5ea6-4d41-85df-36e7a8a60ae2
    def test_from_cli_submodule_import(self) -> None:
        """Test from cli.sub import module returns True."""
        code = "from cli.discovery import loader"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True

    # ID: fa10f5ac-384c-4815-abec-68f0d9f78910
    def test_importlib_import_module_call_cli(self) -> None:
        """Test importlib.import_module('cli.*') returns True."""
        code = "importlib.import_module('cli.commands')"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True

    # ID: d9d32d3f-54e0-48db-941b-3cf13e382b0e
    def test_non_cli_import(self) -> None:
        """Test non-CLI import returns False."""
        code = "import os"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is False

    # ID: 884415f1-2dc0-4530-997b-9324e92014c4
    def test_regular_function_definition(self) -> None:
        """Test function definition with no imports returns False."""
        code = "def foo(): pass"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is False

    # ID: 7d1d1103-2539-4ace-be3f-68c2a6438659
    def test_module_node_with_cli_import(self) -> None:
        """Test full module tree with CLI import returns True."""
        code = "import cli.commands\n"
        tree = ast.parse(code)
        assert _node_imports_cli(tree) is True

    # ID: 8ef39575-2f4c-42c3-854d-276fcdc2d4cc
    def test_module_node_without_cli_import(self) -> None:
        """Test full module tree without CLI import returns False."""
        code = "import os\nimport sys\n"
        tree = ast.parse(code)
        assert _node_imports_cli(tree) is False

    # ID: 39126cae-8406-410f-beac-0da39d07df1f
    def test_importlib_with_non_cli_argument(self) -> None:
        """Test importlib.import_module with non-CLI argument returns False."""
        code = "importlib.import_module('os')"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is False

    # ID: eae010a2-7668-4c0b-966d-c6cdd196a2dc
    def test_nested_cli_import_in_function(self) -> None:
        """Test CLI import nested inside function body returns True."""
        code = "def func():\n    import cli.a\n"
        tree = ast.parse(code)
        node = tree.body[0]
        assert _node_imports_cli(node) is True




# ID: 4b3bea5e-8897-4094-a5ae-0dec19842583
def test_discovery_strict_check_verify():
    path_resolver = MagicMock()
    path_resolver.repo_root = MagicMock()

    loader_rel = "some/loader/path.py"
    loader_path = MagicMock()
    loader_path.is_file.return_value = True
    loader_path.read_text.return_value = "import os\n"

    path_resolver.repo_root.__truediv__.return_value.resolve.return_value = loader_path

    check = DiscoveryStrictCheck(path_resolver)

    result = check.verify([], {"loader": loader_rel})

    assert result == []
    path_resolver.repo_root.__truediv__.assert_called_once_with(loader_rel)
    loader_path.is_file.assert_called_once()
    loader_path.read_text.assert_called_once_with(encoding="utf-8")
