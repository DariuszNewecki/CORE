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
