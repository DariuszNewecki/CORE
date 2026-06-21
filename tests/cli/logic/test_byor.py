# tests/cli/logic/test_byor.py

"""Tests for BYOR onboarding logic — _resolve_machinery_floor helper.

Source: src/cli/logic/byor.py

Tests target the deterministic resolution helper only; the async
initialize_repository function requires a live CoreContext and is covered
by integration tests.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from cli.logic.byor import _resolve_machinery_floor


# ── _resolve_machinery_floor ──────────────────────────────────────────────────


def test_source_tree_preferred_when_present(tmp_path: Path) -> None:
    """Source tree path takes priority over wheel data when both exist."""
    source = tmp_path / "examples" / "starter-intent" / ".intent"
    source.mkdir(parents=True)

    result = _resolve_machinery_floor(tmp_path)

    assert result == source


def test_falls_back_to_wheel_data_when_source_absent(tmp_path: Path) -> None:
    """When source tree is absent, resolves bundled package data in shared._machinery_floor."""
    # tmp_path has no examples/ subtree; bundled data lives in the shared package.
    result = _resolve_machinery_floor(tmp_path)

    assert result.is_dir()
    assert (result / "META").is_dir()
    assert (result / "constitution").is_dir()
    assert (result / "enforcement" / "config").is_dir()
    assert (result / "taxonomies").is_dir()


def test_wheel_fallback_contains_all_machinery_floor_prefixes(tmp_path: Path) -> None:
    """Bundled floor has files under every declared machinery-floor prefix."""
    from cli.logic.byor import _MACHINERY_FLOOR_PREFIXES

    result = _resolve_machinery_floor(tmp_path)

    for prefix in _MACHINERY_FLOOR_PREFIXES:
        matched = list(result.rglob("*"))
        covered = any(
            p.is_file() and p.relative_to(result).as_posix().startswith(prefix)
            for p in matched
        )
        assert covered, f"No file found under machinery-floor prefix '{prefix}'"


def test_raises_when_both_sources_absent(tmp_path: Path) -> None:
    """RuntimeError is raised when neither source tree nor wheel data is present."""
    fake_pkg = MagicMock()
    fake_pkg.joinpath.return_value = MagicMock(
        __str__=lambda self: str(tmp_path / "nonexistent")
    )

    with patch("cli.logic.byor.importlib.resources.files", return_value=fake_pkg):
        with pytest.raises(RuntimeError, match="Machinery floor not found"):
            _resolve_machinery_floor(tmp_path)
