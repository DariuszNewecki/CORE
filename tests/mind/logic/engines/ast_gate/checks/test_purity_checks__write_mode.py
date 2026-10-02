"""ADR-166 D5a — the no_direct_writes detector reads the real mode argument.

Regression (2026-10-02): ``_is_write_mode`` flagged any call with a string
argument containing ``w`` or ``a`` (so a read of ``"data.json"`` counted as a
write), missed ``x`` and ``r+``, and ``Path.open`` / ``tarfile.open`` were not
watched at all, so ``action_logger`` (``Path.open("a")``), ``coherence/seed.py``
and ``context_export.py`` wrote invisibly.
"""

from __future__ import annotations

import ast

import pytest

from mind.logic.engines.ast_gate.checks.purity_checks import PurityChecks
from shared.infrastructure.intent.filesystem_operations import (
    load_filesystem_operations,
)


@pytest.fixture(scope="module")
def taxonomy():
    return load_filesystem_operations()


def _writes(code: str, taxonomy) -> list[str]:
    return PurityChecks.check_no_direct_writes(ast.parse(code), taxonomy)


@pytest.mark.parametrize(
    "code",
    [
        'open("out.txt", "w")',
        'open("out.txt", "x")',
        'open("out.txt", "r+")',
        'open("out.txt", mode="ab")',
        'p.open("a")',
        'p.open(mode="w")',
        'tarfile.open("a.tgz", "w:gz")',
        'tarfile.open("a.tgz", mode="x:xz")',
    ],
)
def test_write_modes_are_detected(code: str, taxonomy) -> None:
    assert _writes(f"import tarfile\n{code}\n", taxonomy)


@pytest.mark.parametrize(
    "code",
    [
        'open("data.json")',
        'open("data.json", "r")',
        'open("archive_w.txt", "rb")',
        "p.open()",
        'p.open("r")',
        'tarfile.open("a.tgz")',
        'tarfile.open("a.tgz", "r:gz")',
        'webbrowser.open("https://example.com/write")',
        'tarfile.open(fileobj=buf, mode="w:gz")',
    ],
)
def test_reads_and_non_file_opens_are_not_writes(code: str, taxonomy) -> None:
    assert _writes(f"import tarfile, webbrowser\n{code}\n", taxonomy) == []
