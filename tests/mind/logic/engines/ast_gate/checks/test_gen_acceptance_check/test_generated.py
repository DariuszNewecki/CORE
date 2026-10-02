from __future__ import annotations

import ast
from pathlib import Path

from mind.logic.engines.ast_gate.checks.test_gen_acceptance_check import (
    TestGenAcceptanceCheck,
)


# ID: 3351c82a-2984-45b3-b674-dd766705186f
def test_TestGenAcceptanceCheck_check() -> None:
    tree = ast.parse("CompositeAcceptanceCondition(conditions=[1, 2])")
    file_path = Path("/tmp/example.py")

    result = TestGenAcceptanceCheck.check(tree, file_path)

    assert isinstance(result, list)
