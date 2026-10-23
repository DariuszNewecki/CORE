"""core-test-gen-pr.sh: opens the pull request for CORE's generated tests (#1252).

The real script runs against a fake `gh` on PATH that records every call and
answers from environment variables: how many files core/test-gen changes
against main, and which pull request is already open.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[2] / "infra/scripts/core-test-gen-pr.sh"

FAKE_GH = """#!/bin/bash
echo "$*" >> "$GH_CALLS"
case "$1 $2" in
  "api repos/"*) [ "$FAKE_FILES" = missing ] && exit 1; echo "$FAKE_FILES" ;;
  "pr list") if [ -f "$GH_CALLS.created" ]; then echo 77; else echo "$FAKE_OPEN"; fi ;;
  "pr create") touch "$GH_CALLS.created"; echo https://github.com/o/r/pull/77 ;;
  "pr merge") ;;
esac
"""


def _run(tmp_path: Path, files: str, open_pr: str = "") -> tuple[str, list[str]]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    (bin_dir / "gh").write_text(FAKE_GH)
    (bin_dir / "gh").chmod(0o755)
    calls = tmp_path / "calls"
    env = {
        "PATH": f"{bin_dir}:{os.environ['PATH']}",
        "GH_CALLS": str(calls),
        "FAKE_FILES": files,
        "FAKE_OPEN": open_pr,
    }
    out = subprocess.run(
        ["bash", str(SCRIPT)], env=env, capture_output=True, text=True, check=True
    ).stdout
    return out, calls.read_text().splitlines() if calls.exists() else []


def test_new_tests_without_a_pull_request_get_one_with_auto_merge(tmp_path) -> None:
    out, calls = _run(tmp_path, files="2")
    assert "opened #77 (2 files)" in out
    assert any(
        c.startswith(
            "pr create --repo DariuszNewecki/CORE --base main --head core/test-gen"
        )
        for c in calls
    )
    assert "pr merge --repo DariuszNewecki/CORE --auto --merge 77" in calls


def test_an_open_pull_request_is_not_opened_twice(tmp_path) -> None:
    out, calls = _run(tmp_path, files="2", open_pr="51")
    assert "#51 already open" in out
    assert not any(c.startswith("pr create") for c in calls)
    assert "pr merge --repo DariuszNewecki/CORE --auto --merge 51" in calls


def test_nothing_to_deliver_does_nothing(tmp_path) -> None:
    # After main is merged back in, the branch is "ahead" by merge commits
    # alone: only changed files count.
    for files in ("0", "missing"):
        sub = tmp_path / files
        sub.mkdir()
        _, calls = _run(sub, files=files)
        assert not any(c.startswith("pr ") for c in calls)
