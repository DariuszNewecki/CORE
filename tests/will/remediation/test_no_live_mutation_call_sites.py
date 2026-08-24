# tests/will/remediation/test_no_live_mutation_call_sites.py
"""
Structural boundary test (ADR-154 D4): candidate-only remediation must
never regain a route to production mutation.

architecture.boundary.remediation_write_access (an ast_gate
runtime_import_boundary rule) forbids a fresh direct GitService import
under src/will/remediation/**, but that mechanism cannot see the two
concrete regression risks in this codebase:

- `self._ctx.git_service.commit_paths(...)` is reached via a
  dependency-injected context attribute — there is no GitService import
  anywhere in this surface for an import scanner to catch.
- `CrateProcessingService.apply_and_finalize_crate(...)` cannot be banned
  at the import level either: crate_canary.py legitimately imports
  CrateProcessingService for validate_crate_by_id() (Canary validation),
  so an import-level ban would also block legitimate validation.

This test closes that gap with a call-site check: it parses every source
file under src/will/remediation/ and asserts no `.commit_paths(...)` or
`.apply_and_finalize_crate(...)` call site exists, regardless of how the
receiver was obtained (import, DI, attribute access).
"""

from __future__ import annotations

import ast
from pathlib import Path

import will.remediation as _remediation_pkg


_FORBIDDEN_METHOD_CALLS = frozenset({"commit_paths", "apply_and_finalize_crate"})


def _remediation_source_files() -> list[Path]:
    package_dir = Path(_remediation_pkg.__file__).resolve().parent
    return sorted(package_dir.rglob("*.py"))


def _forbidden_call_sites(path: Path) -> list[tuple[str, int]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    hits: list[tuple[str, int]] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in _FORBIDDEN_METHOD_CALLS
        ):
            hits.append((node.func.attr, node.lineno))
    return hits


def test_no_live_mutation_call_sites_under_remediation() -> None:
    """No `.commit_paths(...)` or `.apply_and_finalize_crate(...)` call
    site exists anywhere under src/will/remediation/ — production
    mutation from candidate-only remediation is structurally impossible,
    not merely unreached at runtime (ADR-154 D4)."""
    source_files = _remediation_source_files()
    assert source_files, "expected to find source files under will/remediation"

    violations: list[str] = []
    for path in source_files:
        for method_name, lineno in _forbidden_call_sites(path):
            violations.append(f"{path}:{lineno} calls .{method_name}(...)")

    assert not violations, (
        "candidate-only remediation must never call a live-mutation method "
        "(ADR-154 D4): " + "; ".join(violations)
    )
