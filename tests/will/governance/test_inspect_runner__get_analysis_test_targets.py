# tests/will/governance/test_inspect_runner__get_analysis_test_targets.py

"""Tests for get_analysis_test_targets — /v1/analysis/test-targets.

The route was added (f062c24c) importing body.quality.test_target_classifier,
a module that never existed, so it always answered available=false. It now
runs body.self_healing.test_target_analyzer.TestTargetAnalyzer over src/.

Source: src/will/governance/inspect_runner.py
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import patch

from will.governance.inspect_runner import get_analysis_test_targets


def _context(repo_root):
    return SimpleNamespace(git_service=SimpleNamespace(repo_path=str(repo_root)))


def test_classifies_public_functions_under_src(tmp_path) -> None:
    pkg = tmp_path / "src" / "pkg"
    pkg.mkdir(parents=True)
    (pkg / "plain.py").write_text(
        "def add(a, b):\n    return a + b\n\n\ndef _hidden():\n    return 1\n"
    )
    (pkg / "io.py").write_text(
        "import httpx\n\n\ndef fetch(url):\n    return httpx.get(url)\n"
    )
    (tmp_path / "outside.py").write_text("def ignored():\n    return 0\n")

    result = get_analysis_test_targets(_context(tmp_path))

    assert result["available"] is True
    by_name = {t["name"]: t for t in result["targets"]}
    assert set(by_name) == {"add", "fetch"}
    assert result["count"] == 2
    assert by_name["add"]["classification"] == "SIMPLE"
    assert by_name["add"]["file"] == "src/pkg/plain.py"
    assert by_name["fetch"]["classification"] == "COMPLEX"
    assert by_name["fetch"]["reason"] == "File involves I/O operations"
    assert set(by_name["add"]) == {
        "file",
        "name",
        "complexity",
        "classification",
        "reason",
    }


def test_failure_returns_generic_error_without_exception_text(tmp_path) -> None:
    with (
        patch(
            "body.self_healing.test_target_analyzer.TestTargetAnalyzer.analyze_file",
            side_effect=RuntimeError("/etc/shadow: permission denied"),
        ),
        patch("will.governance.inspect_runner.logger") as mock_logger,
    ):
        (tmp_path / "src").mkdir()
        (tmp_path / "src" / "m.py").write_text("def f():\n    return 1\n")
        result = get_analysis_test_targets(_context(tmp_path))

    assert result["available"] is False
    assert result["targets"] == []
    assert "shadow" not in result["error"]
    mock_logger.warning.assert_called_once()
