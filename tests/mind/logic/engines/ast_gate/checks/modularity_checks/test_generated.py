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


from unittest.mock import patch


# ID: 9c16cd94-b903-4b15-84dc-1f57f5342dc4
def test_ModularityChecker_check_single_responsibility() -> None:
    checker = ModularityChecker.__new__(ModularityChecker)
    file_path = Path("src/example.py")
    params: dict = {"threshold": 5}
    expected = [{"check": "refactor_score", "score": 0.1}]

    mock_result = MagicMock(return_value=expected)
    with patch.object(
        ModularityChecker,
        "check_refactor_score",
        mock_result,
    ):
        result = ModularityChecker.check_single_responsibility(
            checker, file_path, params
        )

    assert result == expected
    mock_result.assert_called_once_with(file_path, params)





# ID: 2aaae31b-0f2b-409b-8578-0c4d43af6321
def test_ModularityChecker_check_needs_refactor(tmp_path: Path) -> None:
    file_path = tmp_path / "sample.py"
    file_path.write_text("import os\nimport sys\n", encoding="utf-8")

    checker = ModularityChecker()

    checker._extract_imports = MagicMock(return_value=["os", "sys"])
    checker._identify_concerns = MagicMock(
        return_value=["filesystem", "system", "network", "database"]
    )

    params = {"max_concerns": 3}
    result = checker.check_needs_refactor(file_path, params)

    assert isinstance(result, list)
    assert len(result) == 1
    finding = result[0]
    assert finding["rule_id"] == "modularity.needs_refactor"
    assert finding["file"] == str(file_path)
    assert finding["details"]["concern_count"] == 4
    assert finding["details"]["max_concerns"] == 3
    assert finding["details"]["concerns"] == [
        "filesystem",
        "system",
        "network",
        "database",
    ]
