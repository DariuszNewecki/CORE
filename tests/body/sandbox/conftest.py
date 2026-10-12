# tests/body/sandbox/conftest.py
"""Fixtures for the sandbox runner tests: scratch trees under var/tmp, never /tmp."""

from __future__ import annotations

import shutil
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from body.infrastructure.storage.file_handler import FileHandler


REPO_ROOT = Path(__file__).resolve().parents[3]


@pytest.fixture
def scratch() -> Iterator[Path]:
    var_tmp = REPO_ROOT / "var" / "tmp"
    var_tmp.mkdir(parents=True, exist_ok=True)
    d = Path(tempfile.mkdtemp(prefix="sandbox_test_", dir=str(var_tmp)))
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


@pytest.fixture
def fh(scratch: Path, monkeypatch: pytest.MonkeyPatch) -> FileHandler:
    repo = scratch / "repo"
    repo.mkdir()
    handler = FileHandler(str(repo))
    monkeypatch.setattr(handler, "_guard_paths", lambda *a, **kw: None)
    return handler


def make_tree(
    root: Path, tests: dict[str, str], src: dict[str, str] | None = None
) -> Path:
    """A tiny project: tests/<name> and src/<name> files, plus a pyproject."""
    (root / "tests").mkdir(parents=True)
    for name, body in tests.items():
        (root / "tests" / name).write_text(body, encoding="utf-8")
    for name, body in (src or {}).items():
        path = root / "src" / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(body, encoding="utf-8")
    (root / "pyproject.toml").write_text(
        '[tool.pytest.ini_options]\nmarkers = ["integration: needs the database"]\n',
        encoding="utf-8",
    )
    return root
