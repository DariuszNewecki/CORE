"""CLI entrypoints are read with the stdlib TOML parser (#1387 F11).

``tomli`` is a dev-only dependency; a wheel install does not have it. Blocking
it here reproduces that install.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from body.services.cim.scanners import extract_cli_entrypoints, scan_execution_surfaces


_PYPROJECT = """
[project]
name = "demo"

[project.scripts]
demo-cli = "demo.cli:main"
other = "demo.other:main"
"""


@pytest.fixture
def repo_without_tomli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    (tmp_path / "pyproject.toml").write_text(_PYPROJECT, encoding="utf-8")
    monkeypatch.setitem(sys.modules, "tomli", None)  # import tomli -> ImportError
    return tmp_path


def test_entrypoints_found_without_tomli(repo_without_tomli: Path) -> None:
    assert extract_cli_entrypoints(repo_without_tomli) == ["demo-cli", "other"]


def test_cli_surface_found_without_tomli(repo_without_tomli: Path) -> None:
    surfaces, errors = scan_execution_surfaces(repo_without_tomli)
    assert [s.type for s in surfaces] == ["cli_entrypoint"]
    assert errors == []
