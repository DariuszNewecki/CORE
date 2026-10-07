# tests/shared/infrastructure/validation/test_ruff_linter.py
"""fix_and_lint_code_with_ruff — Ruff is invoked through the sanctioned
subprocess surface (shared.utils.subprocess_utils.run_command).

Source: shared.infrastructure.validation.ruff_linter.fix_and_lint_code_with_ruff
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest

from shared.infrastructure.validation.ruff_linter import fix_and_lint_code_with_ruff
from shared.utils.subprocess_utils import SubprocessResult


_TARGET = "shared.infrastructure.validation.ruff_linter.run_command"


def _repo(tmp_path: Path) -> Path:
    (tmp_path / "var" / "tmp").mkdir(parents=True)
    return tmp_path


# ID: d0763b7c-8603-4e75-96f2-79e9f4de6309
def test_violations_mapped_from_json_output(tmp_path: Path) -> None:
    payload = json.dumps(
        [{"code": "F401", "message": "unused import", "location": {"row": 3}}]
    )
    calls: list[list[str]] = []

    def _fake(args: list[str], *_a: object, **_k: object) -> SubprocessResult:
        calls.append(args)
        out = payload if "json" in args else ""
        return SubprocessResult(stdout=out, stderr="", returncode=0)

    with patch(_TARGET, side_effect=_fake):
        code, violations = fix_and_lint_code_with_ruff(
            "import os\n", _repo(tmp_path), display_filename="mod.py"
        )

    assert code == "import os\n"
    assert [c[:2] for c in calls] == [["ruff", "check"], ["ruff", "check"]]
    assert "--fix" in calls[0]
    assert violations == [
        {
            "rule": "F401",
            "message": "unused import",
            "line": 3,
            "severity": "warning",
            "file": "mod.py",
        }
    ]


# ID: 10dcd323-a628-4bdd-bc29-d64746737815
def test_missing_ruff_executable_reports_tooling_missing(tmp_path: Path) -> None:
    with patch(_TARGET, side_effect=FileNotFoundError("ruff")):
        code, violations = fix_and_lint_code_with_ruff(
            "x = 1\n", _repo(tmp_path), display_filename="mod.py"
        )

    assert code == "x = 1\n"
    assert len(violations) == 1
    assert violations[0]["rule"] == "tooling.missing"
    assert violations[0]["severity"] == "error"


# ID: a32407da-40c2-4d5c-926a-0880e55c654e
def test_empty_output_yields_no_violations(tmp_path: Path) -> None:
    with patch(
        _TARGET, return_value=SubprocessResult(stdout="", stderr="", returncode=0)
    ):
        _, violations = fix_and_lint_code_with_ruff("x = 1\n", _repo(tmp_path))

    assert violations == []


# ID: ad7b7876-3df2-46c4-b9c8-a73f63c9d805
@pytest.mark.skipif(shutil.which("ruff") is None, reason="ruff not on PATH")
def test_real_ruff_reports_an_unfixable_violation(tmp_path: Path) -> None:
    """Against the real binary, not a mock: the JSON pass once used a flag ruff
    rejects (``--format``), exited 2 with empty stdout, and every snippet came
    back clean. The mocked tests above could not see that."""
    _code, violations = fix_and_lint_code_with_ruff(
        "print(undefined_name)\n", _repo(tmp_path), display_filename="mod.py"
    )
    assert [v["rule"] for v in violations] == ["F821"]
    assert violations[0]["file"] == "mod.py"
