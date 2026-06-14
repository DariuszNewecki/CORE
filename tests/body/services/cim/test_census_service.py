# tests/body/services/cim/test_census_service.py
"""Regression guard for #648 — the census `core_version` must derive from the
installed package metadata, never a hardcoded literal that silently drifts."""

from __future__ import annotations

from importlib.metadata import PackageNotFoundError, version

import body.services.cim.census_service as census_mod
from body.services.cim.census_service import _resolve_core_version


def test_resolve_core_version_matches_installed_package() -> None:
    """`core_version` is sourced from the installed `core-runtime` distribution
    (single source of truth = pyproject `[project.version]`), so a census artifact
    can never re-introduce a stale hardcoded version — the #648 `"2.0.0"` drift."""
    assert _resolve_core_version() == version("core-runtime")


def test_resolve_core_version_falls_back_in_source_tree_mode(monkeypatch) -> None:
    """With no installed wheel (raw source tree), the resolver yields a PEP 440
    local-version marker instead of raising."""

    def _raise(_name: str) -> str:
        raise PackageNotFoundError(_name)

    monkeypatch.setattr(census_mod, "_pkg_version", _raise)
    assert _resolve_core_version() == "0.0.0+source"
