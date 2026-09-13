# tests/will/autonomy/test_legacy_direct_write_registry.py
"""ADR-160 D3 polarity inversion — enforce the registry against reality.

`_GRANDFATHERED_DIRECT_WRITE_CALLERS` in autonomous_developer.py is a
registry, not a comment: this test scans src/ for every `develop_from_goal`
call site that opts out of the new fail-closed default
(`legacy_direct_write=True`) and asserts that set equals the registry's
keys exactly. A new caller that opts out without being registered fails; a
registry entry with no corresponding call site also fails.
"""

from __future__ import annotations

import ast
from pathlib import Path

import will as _will_pkg
from will.autonomy.autonomous_developer import _GRANDFATHERED_DIRECT_WRITE_CALLERS


_SRC_ROOT = Path(_will_pkg.__file__).resolve().parent.parent
_AUTONOMOUS_DEVELOPER_PATH = _SRC_ROOT / "will" / "autonomy" / "autonomous_developer.py"


def _module_path(file_path: Path) -> str:
    return ".".join(file_path.relative_to(_SRC_ROOT).with_suffix("").parts)


def _opts_out_of_fail_closed_default(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)):
            continue
        if node.func.id != "develop_from_goal":
            continue
        for kw in node.keywords:
            if (
                kw.arg == "legacy_direct_write"
                and isinstance(kw.value, ast.Constant)
                and kw.value.value is True
            ):
                return True
    return False


def _find_opt_out_callers() -> set[str]:
    callers: set[str] = set()
    for file_path in _SRC_ROOT.rglob("*.py"):
        if file_path == _AUTONOMOUS_DEVELOPER_PATH:
            # The shim's own default parameter declaration, not a call site.
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        if _opts_out_of_fail_closed_default(tree):
            callers.add(_module_path(file_path))
    return callers


def test_registry_matches_actual_opt_out_call_sites() -> None:
    actual = _find_opt_out_callers()
    registered = set(_GRANDFATHERED_DIRECT_WRITE_CALLERS.keys())
    assert actual == registered, (
        f"_GRANDFATHERED_DIRECT_WRITE_CALLERS drifted from src/: "
        f"unregistered opt-outs={actual - registered}, "
        f"stale registry entries={registered - actual}"
    )
