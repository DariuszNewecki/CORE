# tests/body/introspection/test_id_anchor_scanner.py
"""
Unit tests for IdAnchorScanner (ADR-143 D2).

All tests use a synthetic tmp directory — no real src/ access.
"""

from __future__ import annotations

import textwrap
from pathlib import Path

from body.introspection.id_anchor_scanner import scan


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _write(root: Path, rel: str, content: str) -> None:
    target = root / rel
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(textwrap.dedent(content), encoding="utf-8")


def _anchored_paths(result) -> set[str]:
    return {s.symbol_path for s in result.anchored}


def _anchored_uuids(result) -> dict[str, str]:
    return {s.symbol_path: s.anchor_uuid for s in result.anchored}


# ---------------------------------------------------------------------------
# Basic anchored detection
# ---------------------------------------------------------------------------


def test_anchored_function(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/foo.py",
        """\
        from __future__ import annotations

        # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
        def my_func(x: int) -> int:
            return x
        """,
    )
    result = scan(tmp_path)
    assert "src/foo.py::my_func" in _anchored_paths(result)
    assert "src/foo.py::my_func" not in result.anchor_missing


def test_anchored_class(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/bar.py",
        """\
        from __future__ import annotations

        # ID: b2c3d4e5-f6a7-8901-bcde-f12345678901
        class MyService:
            pass
        """,
    )
    result = scan(tmp_path)
    assert "src/bar.py::MyService" in _anchored_paths(result)
    assert "src/bar.py::MyService" not in result.anchor_missing


def test_anchored_async_function(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/svc.py",
        """\
        from __future__ import annotations

        # ID: c3d4e5f6-a7b8-9012-cdef-012345678902
        async def run_task() -> None:
            pass
        """,
    )
    result = scan(tmp_path)
    assert "src/svc.py::run_task" in _anchored_paths(result)


def test_uuid_stored_lowercase(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/foo.py",
        """\
        # ID: A1B2C3D4-E5F6-7890-ABCD-EF1234567890
        def my_func() -> None:
            pass
        """,
    )
    result = scan(tmp_path)
    uuids = _anchored_uuids(result)
    assert uuids["src/foo.py::my_func"] == "a1b2c3d4-e5f6-7890-abcd-ef1234567890"


# ---------------------------------------------------------------------------
# anchor_missing detection
# ---------------------------------------------------------------------------


def test_anchor_missing_no_id_comment(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/foo.py",
        """\
        from __future__ import annotations

        def orphan_func() -> None:
            pass
        """,
    )
    result = scan(tmp_path)
    assert "src/foo.py::orphan_func" in result.anchor_missing
    assert "src/foo.py::orphan_func" not in _anchored_paths(result)


def test_anchor_missing_decorator_not_id(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/foo.py",
        """\
        from __future__ import annotations

        @some_decorator
        def decorated_no_id() -> None:
            pass
        """,
    )
    result = scan(tmp_path)
    assert "src/foo.py::decorated_no_id" in result.anchor_missing


# ---------------------------------------------------------------------------
# Private symbols are exempt
# ---------------------------------------------------------------------------


def test_private_function_exempt(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/foo.py",
        """\
        from __future__ import annotations

        def _private_helper() -> None:
            pass

        def __dunder_method__(self) -> None:
            pass
        """,
    )
    result = scan(tmp_path)
    assert not any("_private_helper" in s for s in _anchored_paths(result))
    assert not any("_private_helper" in s for s in result.anchor_missing)
    assert not any("__dunder" in s for s in result.anchor_missing)


# ---------------------------------------------------------------------------
# Indented methods inside classes
# ---------------------------------------------------------------------------


def test_anchored_method_inside_class(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/svc.py",
        """\
        from __future__ import annotations

        # ID: d4e5f6a7-b8c9-0123-defa-123456789012
        class MyClass:
            # ID: e5f6a7b8-c9d0-1234-efab-234567890123
            def run(self) -> None:
                pass
        """,
    )
    result = scan(tmp_path)
    paths = _anchored_paths(result)
    assert "src/svc.py::MyClass" in paths
    assert "src/svc.py::run" in paths


def test_missing_method_inside_class(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/svc.py",
        """\
        from __future__ import annotations

        # ID: d4e5f6a7-b8c9-0123-defa-123456789012
        class MyClass:
            def run(self) -> None:
                pass
        """,
    )
    result = scan(tmp_path)
    assert "src/svc.py::run" in result.anchor_missing


# ---------------------------------------------------------------------------
# # ID: before decorator (standard CORE pattern)
# ---------------------------------------------------------------------------


def test_id_before_decorator_pattern(tmp_path: Path) -> None:
    """Pattern where # ID: sits above decorators, not directly above def."""
    _write(
        tmp_path,
        "src/action.py",
        """\
        from __future__ import annotations

        @atomic_action(action_id="foo.bar")
        # ID: f6a7b8c9-d0e1-2345-fabc-345678901234
        async def foo_action(**kwargs):
            pass
        """,
    )
    result = scan(tmp_path)
    # # ID: is directly before async def → anchored
    assert "src/action.py::foo_action" in _anchored_paths(result)


# ---------------------------------------------------------------------------
# Empty src directory
# ---------------------------------------------------------------------------


def test_empty_src(tmp_path: Path) -> None:
    (tmp_path / "src").mkdir()
    result = scan(tmp_path)
    assert result.anchored == frozenset()
    assert result.anchor_missing == frozenset()


# ---------------------------------------------------------------------------
# Multiple files, symbol_path format
# ---------------------------------------------------------------------------


def test_symbol_path_format(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/body/services/my_service.py",
        """\
        from __future__ import annotations

        # ID: a7b8c9d0-e1f2-3456-abcd-456789012345
        class MyService:
            pass
        """,
    )
    result = scan(tmp_path)
    paths = _anchored_paths(result)
    assert "src/body/services/my_service.py::MyService" in paths


def test_file_path_stored_in_anchored_symbol(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/foo.py",
        """\
        # ID: b8c9d0e1-f2a3-4567-bcde-567890123456
        def my_func() -> None:
            pass
        """,
    )
    result = scan(tmp_path)
    sym = next(s for s in result.anchored if s.symbol_path == "src/foo.py::my_func")
    assert sym.file_path == "src/foo.py"


def test_mixed_file(tmp_path: Path) -> None:
    _write(
        tmp_path,
        "src/mixed.py",
        """\
        from __future__ import annotations

        # ID: c9d0e1f2-a3b4-5678-cdef-678901234567
        def anchored_one() -> None:
            pass

        def missing_one() -> None:
            pass

        def _private_exempt() -> None:
            pass

        # ID: d0e1f2a3-b4c5-6789-defa-789012345678
        class AnchoredClass:
            pass
        """,
    )
    result = scan(tmp_path)
    assert "src/mixed.py::anchored_one" in _anchored_paths(result)
    assert "src/mixed.py::AnchoredClass" in _anchored_paths(result)
    assert "src/mixed.py::missing_one" in result.anchor_missing
    assert "src/mixed.py::_private_exempt" not in result.anchor_missing
