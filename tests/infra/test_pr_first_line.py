"""A pull request touching host setup or the assistant's hooks must say so in
the first line of its description (governor 2026-10-15)."""

from __future__ import annotations

import importlib.util
import os
import subprocess
import sys
from pathlib import Path

import pytest


REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "infra" / "scripts" / "pr_first_line.py"
_spec = importlib.util.spec_from_file_location("pr_first_line", SCRIPT)
assert _spec and _spec.loader
pfl = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pfl)


@pytest.mark.parametrize(
    "path",
    [
        "infra/systemd/d2/core-api.service",
        "infra/claude-hooks/core-verdict.sh",
        "infra/claude-hooks/settings.json",
        "infra/core-runtime-setup",
        "infra/core-one-path-setup",
        "infra/core-law-setup",
        "infra/core-deploy",
        "infra/core-pipeline",
        "infra/core-sandbox-check",
        "infra/scripts/core-qdrant-backup",
    ],
)
def test_a_host_path_without_the_first_line_fails(path: str) -> None:
    reason = pfl.problem(["src/x.py", path], "Fixes the thing.\n\nHost change: no")
    assert reason and path in reason
    assert pfl.problem([path], "Host change: installs a unit.\n\nDetails.") is None


@pytest.mark.parametrize(
    "path",
    ["src/body/x.py", "infra/scripts/pr_first_line.py", "infra/core-deployer-notes"],
)
def test_other_paths_need_nothing(path: str) -> None:
    assert pfl.problem([path], "") is None


def test_an_empty_description_fails() -> None:
    assert pfl.problem(["infra/core-deploy"], "  \n") is not None


def test_the_script_exits_1_with_an_annotation() -> None:
    run = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)],
        input="infra/core-deploy\n",
        env={**os.environ, "PR_BODY": "no marker"},
        capture_output=True,
        text=True,
    )
    assert run.returncode == 1 and run.stdout.startswith("::error::")
    ok = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)],
        input="infra/core-deploy\n",
        env={**os.environ, "PR_BODY": "Host change: deploy runs setup.\n"},
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0
