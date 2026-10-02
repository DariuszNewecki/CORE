from __future__ import annotations

import ast
from pathlib import Path

from mind.logic.engines.ast_gate.checks.runtime_import_boundary import (
    RuntimeImportBoundaryCheck,
)


# ID: 1ce4cd77-2f91-4db9-9ba1-6880eb673ca4
def test_RuntimeImportBoundaryCheck_check() -> None:
    source = "import os\n"
    tree = ast.parse(source)
    filepath = Path("example.py")

    result = RuntimeImportBoundaryCheck.check(
        filepath, tree, {"forbidden": ["mind.internal"]}
    )

    assert result.ok is True
    assert result.violations == []
    assert result.engine_id == "ast_gate:runtime_import_boundary"





# ID: 0fc72dac-4c62-4958-9d71-86cbcd08f3db
def test_RuntimeImportBoundaryCheck():
    source = "from body.services import thing\nimport body.core\n"
    tree = ast.parse(source)
    filepath = Path("src/mind/logic/example.py")

    params = {"forbidden": ["body"]}

    result = RuntimeImportBoundaryCheck.check(filepath, tree, params)

    assert result.ok is False
    assert len(result.violations) == 2
    assert result.engine_id == "ast_gate:runtime_import_boundary"
