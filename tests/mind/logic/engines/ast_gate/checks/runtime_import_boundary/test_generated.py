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
