from __future__ import annotations

import ast
from unittest.mock import MagicMock, patch

from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks


# ID: c0d93e92-3262-42fb-add1-0f8eb06204d0
def test_PurityChecks_check_future_annotations() -> None:
    tree_with = ast.parse("from __future__ import annotations\n")
    tree_without = ast.parse("x = 1\n")

    with patch.object(
        PurityChecks, "check_future_annotations", return_value=[]
    ) as mock_check:
        result = PurityChecks.check_future_annotations(MagicMock())
        assert result == []
        mock_check.assert_called_once()


# ID: aab90f68-493b-4956-8629-feeaba4330d1
def test_PurityChecks_check_tempfile_default_dir():
    tree = ast.parse("import tempfile\ntempfile.gettempdir()\n")

    with (
        patch(
            "mind.logic.engines.ast_gate.checks.purity_checks.ASTHelpers.build_import_alias_map",
            return_value={},
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.purity_checks.ASTHelpers.full_attr_name",
            return_value="tempfile.gettempdir",
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.purity_checks.ASTHelpers.resolve_qualified_name",
            return_value="tempfile.gettempdir",
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.purity_checks.ASTHelpers.lineno",
            return_value=2,
        ),
    ):
        result = PurityChecks.check_tempfile_default_dir(tree)

    assert isinstance(result, list)
    assert len(result) == 1
    assert "tempfile.gettempdir" in result[0]


from types import SimpleNamespace


# ID: 92ba5847-4c2e-43bf-9d5c-94bd3a1226d8
def test_PurityChecks_check_no_direct_writes():
    taxonomy = SimpleNamespace(
        all_entries=[
            SimpleNamespace(
                op_class="write",
                name="write_text",
                match="leaf",
                namespace="watched",
                predicate=None,
            ),
        ]
    )

    tree = ast.parse(
        "def f():\n    path.write_text('hi')\n    return path.read_text()\n"
    )

    violations = PurityChecks.check_no_direct_writes(tree, taxonomy)

    assert isinstance(violations, list)
    assert len(violations) == 1
    assert "write_text" in violations[0]
    assert "Direct write detected" in violations[0]
    assert "Use FileHandler" in violations[0]


from pathlib import Path


# ID: 97fc26a2-ec3d-4815-8e2f-7c1357e305ca
def test_PurityChecks_check_action_pattern() -> None:
    source = (
        "from somewhere import register_action, atomic_action\n"
        "\n"
        "@register_action\n"
        "@atomic_action\n"
        "def do_thing(write: bool = False) -> None:\n"
        "    return None\n"
    )
    tree = ast.parse(source)
    file_path = Path("src/body/atomic/thing.py")

    violations = PurityChecks.check_action_pattern(tree, file_path)

    assert violations == []
    assert isinstance(violations, list)


# ID: 7faed252-7470-4d0b-b3f7-66811bd6147c
def test_PurityChecks_check_forbidden_imports_and_calls():
    source = (
        "import rich.console\n"
        "from rich.table import Table\n"
        "Console()\n"
        "console.print('hi')\n"
        "Table()\n"
        "import os\n"
        "os.getcwd()\n"
    )
    tree = ast.parse(source)

    forbidden_imports = ["rich.console", "rich.table"]
    forbidden_calls = ["Console", "console.print", "Table"]

    violations = PurityChecks.check_forbidden_imports_and_calls(
        tree,
        forbidden_imports,
        forbidden_calls,
    )

    assert isinstance(violations, list)
    assert len(violations) == 5

    joined = "\n".join(violations)
    assert "Forbidden import 'rich.console'" in joined
    assert "Forbidden import-from 'rich.table'" in joined
    assert "Forbidden call 'Console()'" in joined
    assert "Forbidden call 'console.print()'" in joined
    assert "Forbidden call 'Table()'" in joined

    assert "os" not in joined
    assert "getcwd" not in joined


# ID: 35a63760-e10d-4ef3-89e4-b54b77cd67c8
def test_check_decorator_args() -> None:
    source = (
        "import something\n"
        "\n"
        "@my_decorator(required_one=True, required_two=1)\n"
        "def my_function():\n"
        "    return 1\n"
    )
    tree = ast.parse(source)

    violations = PurityChecks.check_decorator_args(
        tree, "my_decorator", ["required_one", "required_two"]
    )

    assert violations == []





# ID: 507b6cd6-06bb-4531-92af-34614d983532
def test_PurityChecks_check_no_print_statements():
    source = "print('hello world')\n"
    tree = ast.parse(source)

    result = PurityChecks.check_no_print_statements(tree)

    assert result == ["Line 1: Replace print() with logger."]
