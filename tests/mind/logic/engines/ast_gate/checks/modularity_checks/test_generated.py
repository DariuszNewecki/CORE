from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker


# ID: 2c5689ba-a081-43f9-a42b-c4bb84a3afdd
def test_ModularityChecker_check_import_coupling() -> None:
    checker = ModularityChecker()
    checker.check_refactor_score = MagicMock(return_value=[{"ok": True}])

    file_path = Path("some/file.py")
    params = {"threshold": 5}

    result = checker.check_import_coupling(file_path, params)

    assert result == [{"ok": True}]
    checker.check_refactor_score.assert_called_once_with(file_path, params)





# ID: 28d734c6-4659-4651-9738-188a700ab637
def test_ModularityChecker_check_semantic_cohesion() -> None:
    checker = ModularityChecker()
    file_path = Path("src/sample_module.py")
    params = {"threshold": 0.8}

    expected = [{"check": "semantic_cohesion", "score": 0.9}]
    checker.check_refactor_score = MagicMock(return_value=expected)

    result = checker.check_semantic_cohesion(file_path, params)

    assert result == expected
    checker.check_refactor_score.assert_called_once_with(file_path, params)
