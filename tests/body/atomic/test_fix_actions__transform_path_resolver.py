"""Tests for ``_transform_path_resolver`` — Form 0 (leaf) and Form 1 (embedded).

Form 0: ``<other> / "reports"`` / ``<other> / "logs"`` (existing behaviour).
Form 1: ``<other> / "reports/sub/path"`` (extension landed for #276).

Tests exercise the transformer directly rather than running the full action,
so the assertions are about textual rewrites — exactly what the action emits.
"""

from __future__ import annotations

from body.atomic.path_resolver_rewriter import _transform_path_resolver


def _wrap(expr: str) -> str:
    """Embed an expression in a minimal module so the transformer parses it."""
    return f"x = {expr}\n"


def test_form0_leaf_reports() -> None:
    new_source, n = _transform_path_resolver(_wrap('repo_root / "reports"'))
    assert n == 1
    assert "PathResolver.from_repo(repo_root).reports_dir" in new_source
    assert '"reports"' not in new_source.split("=", 1)[1]


def test_form0_leaf_logs() -> None:
    new_source, n = _transform_path_resolver(_wrap('base / "logs"'))
    assert n == 1
    assert "PathResolver.from_repo(base).logs_dir" in new_source


def test_form0_chained_leaf_with_subdir() -> None:
    """`repo_root / "reports" / "X"` — outer BinOp skipped, inner rewritten."""
    new_source, n = _transform_path_resolver(_wrap('repo_root / "reports" / "X"'))
    assert n == 1
    assert 'PathResolver.from_repo(repo_root).reports_dir / "X"' in new_source


def test_form1_embedded_reports_with_remainder() -> None:
    new_source, n = _transform_path_resolver(
        _wrap('repo_root / "reports/audit/latest.json"')
    )
    assert n == 1
    assert (
        'PathResolver.from_repo(repo_root).reports_dir / "audit/latest.json"'
        in new_source
    )


def test_form1_embedded_logs_with_remainder() -> None:
    new_source, n = _transform_path_resolver(_wrap('base / "logs/app.log"'))
    assert n == 1
    assert 'PathResolver.from_repo(base).logs_dir / "app.log"' in new_source


def test_form1_embedded_bare_trailing_slash() -> None:
    """`repo_root / "reports/"` — empty remainder collapses to bare property."""
    new_source, n = _transform_path_resolver(_wrap('repo_root / "reports/"'))
    assert n == 1
    assert "PathResolver.from_repo(repo_root).reports_dir" in new_source
    # Trailing-slash literal is gone; no bare `/ ""` appended.
    assert '/ ""' not in new_source


def test_form1_chained_embedded_outer_skipped() -> None:
    """`foo / "reports/X" / "Y"` — only the inner BinOp is rewritten."""
    new_source, n = _transform_path_resolver(_wrap('foo / "reports/X" / "Y"'))
    assert n == 1
    assert 'PathResolver.from_repo(foo).reports_dir / "X" / "Y"' in new_source


def test_no_match_leaves_source_unchanged() -> None:
    src = _wrap('repo_root / "src" / "module.py"')
    new_source, n = _transform_path_resolver(src)
    assert n == 0
    assert new_source == src


def test_constant_reports_outside_path_division_not_rewritten() -> None:
    """Bare `"reports"` outside a `/` BinOp must not be rewritten (regex
    only flags path-division contexts after ADR-032)."""
    src = 'x = "reports"\n'
    new_source, n = _transform_path_resolver(src)
    assert n == 0
    assert new_source == src
