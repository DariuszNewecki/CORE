# tests/cli/logic/test_byor_target_safety.py

"""Tests for _reject_unsafe_target — BYOR write-target guard (#787, CodeQL py/path-injection).

Source: src/cli/logic/byor.py
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from cli.logic.byor import _reject_unsafe_target


CORE_ROOT = Path("/opt/dev/CORE")


# ── overlap with CORE's own repo tree ──────────────────────────────────────


def test_rejects_exact_core_root() -> None:
    with pytest.raises(typer.Exit):
        _reject_unsafe_target(CORE_ROOT, CORE_ROOT)


def test_rejects_subdirectory_of_core_root() -> None:
    with pytest.raises(typer.Exit):
        _reject_unsafe_target(CORE_ROOT / "some" / "subdir", CORE_ROOT)


def test_rejects_ancestor_of_core_root() -> None:
    with pytest.raises(typer.Exit):
        _reject_unsafe_target(CORE_ROOT.parent, CORE_ROOT)


# ── fixed system-directory denylist ────────────────────────────────────────


@pytest.mark.parametrize(
    "unsafe_root", ["/", "/etc", "/bin", "/sbin", "/usr", "/root", "/dev"]
)
def test_rejects_system_directories(unsafe_root: str) -> None:
    with pytest.raises(typer.Exit):
        _reject_unsafe_target(Path(unsafe_root), CORE_ROOT)


# ── legitimate external targets pass through ───────────────────────────────


@pytest.mark.parametrize(
    "target", ["/opt/some-external-repo", "/home/user/other-project", "/srv/target"]
)
def test_allows_unrelated_external_targets(target: str) -> None:
    _reject_unsafe_target(Path(target), CORE_ROOT)  # must not raise
