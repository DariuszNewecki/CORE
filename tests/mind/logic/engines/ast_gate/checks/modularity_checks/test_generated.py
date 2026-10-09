from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from mind.logic.engines.ast_gate.checks.modularity_checks import ModularityChecker


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


# ID: bc70adf3-3d8b-4854-b791-c9445327a9e2
def test_ModularityChecker_check_class_too_large(tmp_path: Path) -> None:
    max_lines = 40
    body_lines = ["    x = 1"] * (max_lines + 5)
    source = "class BigClass:\n" + "\n".join(body_lines) + "\n"

    file_path = tmp_path / "module.py"
    file_path.write_text(source, encoding="utf-8")

    checker = ModularityChecker()

    with (
        patch(
            "mind.logic.engines.ast_gate.checks.modularity_checks._has_core_role_declaration",
            return_value=False,
        ),
        patch.object(
            checker,
            "_find_dominant_class",
            return_value=("BigClass", max_lines + 5, 0.9),
        ),
    ):
        results = checker.check_class_too_large(file_path, {"max_lines": max_lines})

    assert isinstance(results, list)
    assert len(results) == 1
    finding = results[0]
    assert finding["rule_id"] == "modularity.class_too_large"
    assert finding["file"] == str(file_path)
    assert finding["details"]["max_lines"] == max_lines
    assert finding["details"]["dominant_class_name"] == "BigClass"
    assert finding["details"]["dominant_class_lines"] > max_lines


# ID: 85f5edee-87df-499b-9ef1-c0f7a5bc4aa6
def test_ModularityChecker_check_needs_split():
    checker = ModularityChecker()
    checker._detect_responsibilities = MagicMock(return_value=["responsibility_a"])
    checker._find_dominant_class = MagicMock(return_value=("DominantClass", 100, 0.25))

    lines = []
    for idx in range(500):
        lines.append(f"line_{idx} = {idx}")
    content = "\n".join(lines)

    mock_path = MagicMock(spec=Path)
    mock_path.read_text.return_value = content
    mock_path.__str__.return_value = "/tmp/big_file.py"

    with (
        patch(
            "mind.logic.engines.ast_gate.checks.modularity_checks._has_core_role_declaration",
            return_value=False,
        ),
        patch(
            "mind.logic.engines.ast_gate.checks.modularity_checks.ast.parse"
        ) as mock_parse,
    ):
        mock_parse.return_value = MagicMock()

        result = checker.check_needs_split(mock_path, {"max_lines": 400})

    assert len(result) == 1
    finding = result[0]
    assert finding["rule_id"] == "modularity.needs_split"
    assert finding["file"] == "/tmp/big_file.py"
    assert finding["details"]["lines_of_code"] == 500
    assert finding["details"]["max_lines"] == 400
    assert finding["details"]["responsibility_count"] == 1
    assert finding["details"]["dominant_class_name"] == "DominantClass"
    assert finding["details"]["dominant_class_lines"] == 100
    assert finding["details"]["dominant_class_ratio"] == 0.25


# ID: 82400973-b6dc-4b84-b2dd-8a15c3f0cc52
def test_ModularityChecker_check_refactor_score(tmp_path: Path) -> None:
    source = "import os\nimport sys\n\ndef foo():\n    return 1\n"
    file_path = tmp_path / "sample.py"
    file_path.write_text(source, encoding="utf-8")

    checker = ModularityChecker()

    checker._detect_responsibilities = MagicMock(
        return_value=["resp1", "resp2", "resp3"]
    )
    checker._extract_functions = MagicMock(return_value=["foo"])
    checker._calculate_cohesion = MagicMock(return_value=0.2)
    checker._extract_imports = MagicMock(return_value=["os", "sys", "json", "re"])
    checker._identify_concerns = MagicMock(return_value=["a", "b", "c", "d"])

    findings = checker.check_refactor_score(file_path, {"max_score": 60.0})

    assert isinstance(findings, list)
    for finding in findings:
        assert finding["rule_id"] == "modularity.refactor_score_threshold"
        assert finding["file"] == str(file_path)
        assert finding["severity"] in ("error", "warning")
