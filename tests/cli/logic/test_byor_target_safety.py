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


# ── no CORE repository to protect (installed wheel) ────────────────────────


def test_no_core_root_allows_ordinary_target() -> None:
    """core_root=None (pip install): only the system-dir backstop applies."""
    _reject_unsafe_target(Path("/home/someone/their-repo"), None)


def test_no_core_root_still_rejects_system_dirs() -> None:
    with pytest.raises(typer.Exit):
        _reject_unsafe_target(Path("/etc"), None)


def test_core_source_root_is_the_checkout_not_the_cwd(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Regression (2026-10-02): the guard derived CORE's root by walking up from
    cwd, which for a pip user standing in their own repo is *their* repo, so
    every adopt-pack --write was refused as "overlaps CORE's own repo root"."""
    from cli.logic.byor import core_source_root
    from shared.config import REPO_ROOT

    adopter = tmp_path / "adopter"
    (adopter / ".intent").mkdir(parents=True)
    monkeypatch.chdir(adopter)

    root = core_source_root()
    assert root != adopter.resolve()
    # Running these tests from a CORE checkout, the source tree is CORE's repo.
    assert root == REPO_ROOT.resolve()


def test_core_source_root_none_without_intent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """An installed wheel's REPO_ROOT has no .intent/ — nothing to protect."""
    import shared.config as config
    from cli.logic.byor import core_source_root

    monkeypatch.setattr(config, "REPO_ROOT", tmp_path / "site-packages-ish")
    assert core_source_root() is None
