# tests/body/quality/test_coverage_analyzer__subprocess_routing.py
"""CoverageAnalyzer runs pytest through the sanctioned subprocess surface.

Covers the routing onto ``shared.utils.subprocess_utils.run_command``
(governance.dangerous_execution_primitives): the configured timeout is
passed through, a timeout is reported as before, and the term-output
fallback still parses the (now stripped) stdout.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from body.quality import coverage_analyzer
from body.quality.coverage_analyzer import CoverageAnalyzer
from shared.utils.subprocess_utils import SubprocessResult, SubprocessTimeoutError


_RUN = "body.quality.coverage_analyzer.run_command"


def _ok(stdout: str = "") -> SubprocessResult:
    return SubprocessResult(stdout=stdout, stderr="", returncode=0)


def test_get_module_coverage_reads_coverage_json(tmp_path: Path) -> None:
    (tmp_path / "coverage.json").write_text(
        json.dumps({"files": {"src/a.py": {"summary": {"percent_covered": 50.123}}}})
    )
    with patch(_RUN, return_value=_ok()) as run:
        result = CoverageAnalyzer(tmp_path).get_module_coverage()
    assert result == {"src/a.py": 50.12}
    args, kwargs = run.call_args
    assert args[0][:3] == ["poetry", "run", "pytest"]
    assert kwargs["cwd"] == tmp_path
    assert kwargs["timeout"] == coverage_analyzer._CFG.collect_timeout_sec


def test_get_module_coverage_timeout_returns_empty(tmp_path: Path) -> None:
    with patch(_RUN, side_effect=SubprocessTimeoutError("t", exit_code=124)):
        assert CoverageAnalyzer(tmp_path).get_module_coverage() == {}
