"""The law's test scope is a rule over paths, not a list of files (ADR-172 item 4, #1325)."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest
import yaml

from shared.infrastructure.intent.test_coverage_paths import in_test_scope


_REPO = Path(__file__).resolve().parents[4]


def test_include_paths_take_directories_and_files_minus_exclusions():
    config = {
        "include_paths": ["src/mind/", "src/body/one.py"],
        "exclude_paths": ["src/mind/skip/"],
    }
    assert in_test_scope("src/mind/a.py", config)
    assert in_test_scope("src/body/one.py", config)
    assert not in_test_scope("src/body/two.py", config)
    assert not in_test_scope("src/mind/skip/b.py", config)


def test_a_config_that_still_lists_files_keeps_working():
    config = {"include_files": ["src/x.py"]}
    assert in_test_scope("src/x.py", config)
    assert not in_test_scope("src/y.py", config)
    assert in_test_scope("src/y.py", {})


def test_every_file_of_the_retired_list_stays_in_scope():
    """The 134 files of include_files at 1d20c476 are all inside the rule."""
    shown = subprocess.run(
        ["git", "show", "1d20c476:.intent/enforcement/config/test_coverage.yaml"],
        cwd=_REPO,
        capture_output=True,
        text=True,
    )
    if shown.returncode != 0:
        pytest.skip("a shallow clone has no 1d20c476")
    old = shown.stdout
    retired = yaml.safe_load(old)["include_files"]
    config = yaml.safe_load(
        (_REPO / ".intent/enforcement/config/test_coverage.yaml").read_text()
    )
    assert "include_files" not in config
    assert len(retired) == 134
    assert [f for f in retired if not in_test_scope(f, config)] == []
