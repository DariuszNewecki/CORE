"""Regression test for #549 — workflow_gate checks silent-skip on tool absence.

The F-10.3 Action ships a slim Docker image without mypy / pytest /
pip-audit / ruff / black. Before #549, each gate that depended on
one of these tools would emit a `[Errno 2] No such file or directory`
violation, which got rendered as an inline annotation with
``file_path="System"``. Seven of the 18-annotation budget on the
demo PR was burned on this noise.

The fix: detect ``FileNotFoundError`` at the check level and return
an empty violation list (silent skip with a debug log). Annotation
budget is preserved for actionable consumer findings.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from mind.logic.engines.workflow_gate.checks.import_resolution import (
    ImportResolutionCheck,
)
from mind.logic.engines.workflow_gate.checks.linter import LinterComplianceCheck
from mind.logic.engines.workflow_gate.checks.quality import QualityGateCheck
from mind.logic.engines.workflow_gate.checks.ruff_format import RuffFormatCheck


def _path_resolver(tmp_path: str = "/repo") -> MagicMock:
    pr = MagicMock()
    pr.repo_root = tmp_path
    pr.src_root = tmp_path + "/src"
    return pr


def test_quality_gate_silent_skips_when_tool_missing() -> None:
    """QualityGateCheck (mypy/pytest/pip-audit wrapper) returns [] on FileNotFoundError.

    The catch-all `except Exception` branch previously absorbed
    FileNotFoundError and emitted "Gate <check> error: [Errno 2]..."
    as a violation. The fix adds an explicit FileNotFoundError branch
    above the catch-all that silent-skips.
    """
    check = QualityGateCheck(
        _path_resolver(),
        "mypy_check",
        ["mypy", "src/", "--ignore-missing-imports"],
    )

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "mypy"),
    ):
        result = asyncio.run(check.verify(None, {}))

    assert result == [], (
        f"QualityGateCheck must silent-skip on missing tool; got {result}"
    )


def test_quality_gate_still_emits_other_errors() -> None:
    """Non-FileNotFoundError exceptions still surface as violations.

    Defensive — the silent-skip is scoped to tool absence. Real
    failures (timeout, permission, OOM, etc.) must still reach the
    operator.
    """
    check = QualityGateCheck(_path_resolver(), "pytest_check", ["pytest", "-q"])

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=RuntimeError("subprocess kernel oops"),
    ):
        result = asyncio.run(check.verify(None, {}))

    assert len(result) == 1
    assert "pytest_check" in result[0]
    assert "subprocess kernel oops" in result[0]


def test_import_resolution_silent_skips_when_ruff_missing() -> None:
    """ImportResolutionCheck returns [] on FileNotFoundError instead of "ruff not found"."""
    check = ImportResolutionCheck()

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "ruff"),
    ):
        result = asyncio.run(check.verify(None, {}))

    assert result == [], f"Expected silent skip; got {result}"


def test_ruff_format_silent_skips_when_ruff_missing() -> None:
    """RuffFormatCheck returns [] on FileNotFoundError."""
    check = RuffFormatCheck()

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "ruff"),
    ):
        result = asyncio.run(check.verify(None, {}))

    assert result == [], f"Expected silent skip; got {result}"


def test_linter_compliance_silent_skips_when_both_tools_missing() -> None:
    """LinterComplianceCheck runs ruff THEN black; both FileNotFoundError → []."""
    check = LinterComplianceCheck()

    with patch(
        "asyncio.create_subprocess_exec",
        side_effect=FileNotFoundError(2, "No such file or directory", "ruff"),
    ):
        result = asyncio.run(check.verify(None, {}))

    assert result == [], f"Expected silent skip; got {result}"


def test_linter_compliance_silent_skips_ruff_then_runs_black_on_mixed_absence() -> None:
    """If ruff is missing but black is present, only the ruff section silent-skips.

    Ruff's FileNotFoundError is caught → no violation emitted.
    Black then runs successfully (mocked rc=0) → no violation.
    Net: empty violation list.
    """
    check = LinterComplianceCheck()

    call_count = {"n": 0}

    async def fake_exec(*args, **kwargs):
        call_count["n"] += 1
        if call_count["n"] == 1:
            # First call (ruff) → FileNotFoundError
            raise FileNotFoundError(2, "No such file or directory", "ruff")
        # Second call (black) → fake successful subprocess
        proc = MagicMock()
        proc.communicate = AsyncMock(return_value=(b"", b""))
        proc.returncode = 0
        return proc

    with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
        result = asyncio.run(check.verify(None, {}))

    assert result == [], f"Expected empty violations (ruff skip + black pass); got {result}"
    assert call_count["n"] == 2, "Expected both subprocess calls to be attempted"
