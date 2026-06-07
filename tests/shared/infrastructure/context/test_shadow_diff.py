from __future__ import annotations

from shared.infrastructure.context.shadow_diff import ShadowDiff


def _sym(
    file_path: str,
    name: str,
    *,
    kind: str = "FunctionDef",
    parameters: list[dict] | None = None,
    calls: list[str] | None = None,
) -> tuple[str, dict]:
    key = f"{file_path}::{name}"
    return key, {
        "symbol_path": key,
        "name": name,
        "type": kind,
        "file_path": file_path,
        "parameters": parameters or [],
        "calls": calls or [],
    }


def _graph(*symbols: tuple[str, dict]) -> dict:
    return {"metadata": {}, "symbols": dict(symbols)}


def test_empty_graphs_produce_empty_diff() -> None:
    diff = ShadowDiff({"symbols": {}}, {"symbols": {}})
    assert diff.added_symbols() == []
    assert diff.removed_symbols() == []
    assert diff.changed_signatures() == []
    assert diff.orphaned_callers() == []
    assert diff.is_empty()


def test_identical_graphs_produce_empty_diff() -> None:
    g = _graph(_sym("src/foo.py", "bar"))
    diff = ShadowDiff(g, g)
    assert diff.is_empty()


def test_added_symbol_only_in_shadow_surfaces_in_added() -> None:
    disk = _graph(_sym("src/foo.py", "bar"))
    shadow = _graph(
        _sym("src/foo.py", "bar"),
        _sym("src/foo.py", "baz"),
    )
    diff = ShadowDiff(disk, shadow)
    added = diff.added_symbols()
    assert len(added) == 1
    assert added[0].name == "baz"
    assert added[0].symbol_path == "src/foo.py::baz"
    assert diff.removed_symbols() == []
    assert not diff.is_empty()


def test_removed_symbol_only_in_disk_surfaces_in_removed() -> None:
    disk = _graph(
        _sym("src/foo.py", "bar"),
        _sym("src/foo.py", "baz"),
    )
    shadow = _graph(_sym("src/foo.py", "bar"))
    diff = ShadowDiff(disk, shadow)
    removed = diff.removed_symbols()
    assert len(removed) == 1
    assert removed[0].name == "baz"


def test_signature_change_surfaces_when_parameter_lists_differ() -> None:
    disk = _graph(_sym("src/foo.py", "bar", parameters=[{"name": "x"}]))
    shadow = _graph(
        _sym("src/foo.py", "bar", parameters=[{"name": "x"}, {"name": "y"}])
    )
    diff = ShadowDiff(disk, shadow)
    deltas = diff.changed_signatures()
    assert len(deltas) == 1
    assert deltas[0].symbol_path == "src/foo.py::bar"
    assert deltas[0].disk_parameters == ({"name": "x"},)
    assert deltas[0].shadow_parameters == ({"name": "x"}, {"name": "y"})


def test_signature_unchanged_when_parameters_identical() -> None:
    disk = _graph(_sym("src/foo.py", "bar", parameters=[{"name": "x"}]))
    shadow = _graph(_sym("src/foo.py", "bar", parameters=[{"name": "x"}]))
    diff = ShadowDiff(disk, shadow)
    assert diff.changed_signatures() == []


def test_orphaned_caller_when_shadow_calls_disk_only_name() -> None:
    # disk defines both 'caller' and 'helper'; shadow drops 'helper' but
    # caller still references it
    disk = _graph(
        _sym("src/foo.py", "caller", calls=["helper"]),
        _sym("src/foo.py", "helper"),
    )
    shadow = _graph(_sym("src/foo.py", "caller", calls=["helper"]))
    diff = ShadowDiff(disk, shadow)
    orphans = diff.orphaned_callers()
    assert len(orphans) == 1
    assert orphans[0].caller_name == "caller"
    assert orphans[0].orphaned_call == "helper"


def test_calls_to_stdlib_or_unknown_names_are_not_orphans() -> None:
    # 'print' was never in either graph; calling it must not orphan
    disk = _graph(_sym("src/foo.py", "caller", calls=["print"]))
    shadow = _graph(_sym("src/foo.py", "caller", calls=["print"]))
    diff = ShadowDiff(disk, shadow)
    assert diff.orphaned_callers() == []


def test_call_preserved_when_target_still_present_in_shadow() -> None:
    # helper exists in both graphs — caller is not orphaned
    disk = _graph(
        _sym("src/foo.py", "caller", calls=["helper"]),
        _sym("src/foo.py", "helper"),
    )
    shadow = _graph(
        _sym("src/foo.py", "caller", calls=["helper"]),
        _sym("src/bar.py", "helper"),  # moved to another file
    )
    diff = ShadowDiff(disk, shadow)
    # 'helper' still exists somewhere in shadow → not an orphan
    assert diff.orphaned_callers() == []


def test_is_empty_false_when_any_dimension_changed() -> None:
    g_a = _graph(_sym("src/foo.py", "bar"))
    g_b = _graph(_sym("src/foo.py", "bar"), _sym("src/foo.py", "baz"))
    assert not ShadowDiff(g_a, g_b).is_empty()


def test_diff_results_are_deterministically_sorted() -> None:
    disk = _graph()
    shadow = _graph(
        _sym("src/z.py", "zz"),
        _sym("src/a.py", "aa"),
        _sym("src/m.py", "mm"),
    )
    diff = ShadowDiff(disk, shadow)
    paths = [r.symbol_path for r in diff.added_symbols()]
    assert paths == sorted(paths)
