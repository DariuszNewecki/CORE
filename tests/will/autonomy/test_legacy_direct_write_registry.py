# tests/will/autonomy/test_legacy_direct_write_registry.py
"""ADR-160 D3 polarity inversion — enforce the registry against reality.

`_GRANDFATHERED_DIRECT_WRITE_CALLERS` in autonomous_developer.py is a
registry, not a comment: this test scans src/ for every `develop_from_goal`
call site that opts out of the new fail-closed default
(`legacy_direct_write=True`) and asserts that set equals the registry's
keys exactly. A new caller that opts out without being registered fails; a
registry entry with no corresponding call site also fails.

Fail-closed, not declarative-only (the class of gate ADR-160's Context
section criticises): a call site is only ever accepted as a *non*-opt-out
when its `legacy_direct_write` argument is statically absent or a literal
`False`. Anything this scanner cannot prove one way or the other --
`legacy_direct_write=some_flag`, a positional `True` in that slot,
`**kwargs` or `*args` forwarding into the call -- fails the test outright
instead of silently passing through uncounted. A gate that can't see a
dynamic value is not a gate.
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import TypeGuard

import pytest

import will as _will_pkg
from will.autonomy.autonomous_developer import _GRANDFATHERED_DIRECT_WRITE_CALLERS


_SRC_ROOT = Path(_will_pkg.__file__).resolve().parent.parent
_AUTONOMOUS_DEVELOPER_PATH = _SRC_ROOT / "will" / "autonomy" / "autonomous_developer.py"

# Position of `legacy_direct_write` in develop_from_goal's signature
# (context, goal, workflow_type, write, task_id, legacy_direct_write) --
# 0-indexed, so a 6th positional argument would land here.
_LEGACY_DIRECT_WRITE_POSITION = 5


def _module_path(file_path: Path) -> str:
    return ".".join(file_path.relative_to(_SRC_ROOT).with_suffix("").parts)


def _is_develop_from_goal_call(node: ast.AST) -> TypeGuard[ast.Call]:
    if not isinstance(node, ast.Call):
        return False
    func = node.func
    if isinstance(func, ast.Name):
        return func.id == "develop_from_goal"
    if isinstance(func, ast.Attribute):
        return func.attr == "develop_from_goal"
    return False


def _is_literal_bool(node: ast.AST, value: bool) -> bool:
    return isinstance(node, ast.Constant) and node.value is value


def _classify_call(node: ast.Call, path: Path) -> bool:
    """Return True iff this call site is a verified `legacy_direct_write=True`
    literal opt-out. Raises AssertionError if the call cannot be statically
    verified either way (unpacking, a non-literal value)."""
    for arg in node.args:
        if isinstance(arg, ast.Starred):
            raise AssertionError(
                f"{path}: develop_from_goal(*...) uses positional unpacking "
                "-- cannot statically verify whether legacy_direct_write is "
                "set. Rewrite as explicit keyword arguments."
            )
    for kw in node.keywords:
        if kw.arg is None:
            raise AssertionError(
                f"{path}: develop_from_goal(**...) uses keyword unpacking "
                "-- cannot statically verify whether legacy_direct_write is "
                "set. Rewrite as explicit keyword arguments."
            )

    legacy_value: ast.AST | None = None
    if len(node.args) > _LEGACY_DIRECT_WRITE_POSITION:
        legacy_value = node.args[_LEGACY_DIRECT_WRITE_POSITION]
    for kw in node.keywords:
        if kw.arg == "legacy_direct_write":
            legacy_value = kw.value

    if legacy_value is None:
        return False
    if _is_literal_bool(legacy_value, False):
        return False
    if _is_literal_bool(legacy_value, True):
        return True
    raise AssertionError(
        f"{path}: develop_from_goal(..., legacy_direct_write=<non-literal>) "
        "-- legacy_direct_write must be a literal True or False so this "
        "registry can verify it statically. A variable, expression, or "
        "computed value defeats the registry the same way ADR-160's "
        "Context criticises declarative-only gates for."
    )


def _find_opt_out_callers() -> set[str]:
    callers: set[str] = set()
    for file_path in sorted(_SRC_ROOT.rglob("*.py")):
        if file_path == _AUTONOMOUS_DEVELOPER_PATH:
            # The shim's own default parameter declaration, not a call site.
            continue
        tree = ast.parse(file_path.read_text(encoding="utf-8"), filename=str(file_path))
        for node in ast.walk(tree):
            if _is_develop_from_goal_call(node) and _classify_call(node, file_path):
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


# --------------------------------------------- _classify_call unit coverage
# Direct coverage of the classifier's fail-closed behavior itself, not just
# the integration scan over the real source tree -- these prove the gap a
# bare literal-True check would have (silently passing a dynamic value
# through as "not an opt-out") is actually closed.


def _call_node(source: str) -> ast.Call:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            return node
    raise AssertionError(f"no Call node found in test fixture source: {source!r}")


def test_classify_call_true_literal_kwarg_is_opt_out() -> None:
    node = _call_node("develop_from_goal(write=True, legacy_direct_write=True)")
    assert _classify_call(node, Path("dummy.py")) is True


def test_classify_call_false_literal_kwarg_is_not_opt_out() -> None:
    node = _call_node("develop_from_goal(write=True, legacy_direct_write=False)")
    assert _classify_call(node, Path("dummy.py")) is False


def test_classify_call_absent_kwarg_is_not_opt_out() -> None:
    node = _call_node("develop_from_goal(write=True)")
    assert _classify_call(node, Path("dummy.py")) is False


def test_classify_call_true_literal_positional_is_opt_out() -> None:
    node = _call_node('develop_from_goal(ctx, "goal", "wf", True, "task-1", True)')
    assert _classify_call(node, Path("dummy.py")) is True


def test_classify_call_non_literal_kwarg_fails_closed() -> None:
    node = _call_node("develop_from_goal(write=True, legacy_direct_write=some_flag)")
    with pytest.raises(AssertionError, match="non-literal"):
        _classify_call(node, Path("dummy.py"))


def test_classify_call_kwargs_unpacking_fails_closed() -> None:
    node = _call_node("develop_from_goal(write=True, **extra)")
    with pytest.raises(AssertionError, match="keyword unpacking"):
        _classify_call(node, Path("dummy.py"))


def test_classify_call_star_args_unpacking_fails_closed() -> None:
    node = _call_node("develop_from_goal(*args)")
    with pytest.raises(AssertionError, match="positional unpacking"):
        _classify_call(node, Path("dummy.py"))
