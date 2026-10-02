# tests/cli/logic/test_project_scaffold.py
"""project new — Generate bootstrap stage (ADR-119 Amendment 2026-10-02, #892).

Pins: the floor is the same file selection project onboard delivers and is copied
byte-for-byte; the skeleton is neutral and carries no law; unsafe or occupied
targets are refused in dry-run and write mode alike.
"""

from __future__ import annotations

import filecmp
from pathlib import Path

import pytest
import typer

from cli.logic.byor import _machinery_floor_files, _resolve_machinery_floor
from cli.logic.project_scaffold import plan_new_project, write_new_project


@pytest.fixture
def core_root(tmp_path: Path) -> Path:
    root = tmp_path / "core"
    root.mkdir()
    return root


@pytest.fixture
def parent(tmp_path: Path) -> Path:
    parent = tmp_path / "work"
    parent.mkdir()
    return parent


# ID: 495d12ea-485f-4df1-b58d-4b8078d3bf9a
def test_floor_is_exactly_what_onboard_delivers(parent: Path, core_root: Path) -> None:
    plan = plan_new_project("demo", parent, core_root)

    floor_dir = _resolve_machinery_floor(core_root)
    expected = {
        (src, f".intent/{src.relative_to(floor_dir).as_posix()}")
        for src in _machinery_floor_files(floor_dir)
    }
    assert set(plan.floor_copies) == expected
    assert plan.floor_copies, "bundled floor must not be empty"


# ID: caf6b602-f6bf-4192-a8d8-ea3119f338a5
def test_plan_contains_no_project_law(parent: Path, core_root: Path) -> None:
    plan = plan_new_project("demo", parent, core_root)

    all_rel = [rel for _, rel in plan.floor_copies] + [
        rel for rel, _ in plan.skeleton_files
    ]
    assert not any(r.startswith(".intent/rules/") for r in all_rel)
    assert not any(r.startswith(".intent/enforcement/mappings/") for r in all_rel)
    assert not any("__init__.py" in r for r in all_rel if r.startswith(".intent/"))


# ID: 854d4a70-e1fc-49be-b990-81b3fdfb6848
def test_skeleton_is_minimal_and_neutral(parent: Path, core_root: Path) -> None:
    plan = plan_new_project("my-app", parent, core_root)

    assert plan.package == "my_app"
    assert plan.target_root == (parent / "my-app").resolve()
    skeleton = dict(plan.skeleton_files)
    assert set(skeleton) == {
        "pyproject.toml",
        "README.md",
        "src/my_app/__init__.py",
        "tests/__init__.py",
    }
    assert 'name = "my-app"' in skeleton["pyproject.toml"]
    assert "dependencies = []" in skeleton["pyproject.toml"]
    assert "no project-specific law" in skeleton["README.md"]


@pytest.mark.parametrize("bad", ["1app", "my app", "", "app/x", "class"])
# ID: f1c3e34f-17a0-40d2-b4ab-6380c9e59151
def test_invalid_names_are_refused(bad: str, parent: Path, core_root: Path) -> None:
    with pytest.raises(typer.Exit):
        plan_new_project(bad, parent, core_root)


# ID: 1c0ab681-074d-4006-8c62-9cbca278940b
def test_write_delivers_floor_bytes_and_skeleton(parent: Path, core_root: Path) -> None:
    plan = plan_new_project("demo", parent, core_root)

    count = write_new_project(plan, core_root, write=True)

    assert count == plan.file_count
    for src, rel in plan.floor_copies:
        assert filecmp.cmp(src, plan.target_root / rel, shallow=False), rel
    for rel, text in plan.skeleton_files:
        assert (plan.target_root / rel).read_text(encoding="utf-8") == text
    assert not (core_root / "demo").exists()


# ID: 29e2131b-8ffa-4e81-8e1a-75dd5538cd10
def test_dry_run_writes_nothing(parent: Path, core_root: Path) -> None:
    plan = plan_new_project("demo", parent, core_root)

    count = write_new_project(plan, core_root, write=False)

    assert count == plan.file_count
    assert not plan.target_root.exists()


# ID: 4d985747-1609-4dda-87cc-b0cab829ba05
def test_empty_existing_directory_is_accepted(parent: Path, core_root: Path) -> None:
    (parent / "demo").mkdir()
    plan = plan_new_project("demo", parent, core_root)

    write_new_project(plan, core_root, write=True)

    assert (plan.target_root / ".intent").is_dir()


@pytest.mark.parametrize("write", [False, True])
# ID: d6bf95fe-89ca-4fb9-b715-77d6bf22a914
def test_non_empty_target_is_refused(
    write: bool, parent: Path, core_root: Path
) -> None:
    (parent / "demo").mkdir()
    (parent / "demo" / "keep.txt").write_text("mine")
    plan = plan_new_project("demo", parent, core_root)

    with pytest.raises(typer.Exit):
        write_new_project(plan, core_root, write=write)
    assert sorted(p.name for p in (parent / "demo").iterdir()) == ["keep.txt"]


# ID: 9fdfa747-a42f-4ba0-9d7a-75470cc6d989
def test_target_that_is_a_file_is_refused(parent: Path, core_root: Path) -> None:
    (parent / "demo").write_text("a file")
    plan = plan_new_project("demo", parent, core_root)

    with pytest.raises(typer.Exit):
        write_new_project(plan, core_root, write=True)


@pytest.mark.parametrize("write", [False, True])
# ID: ede04093-5c74-438a-b0bc-5024d52a7ae7
def test_target_inside_core_repo_is_refused(write: bool, core_root: Path) -> None:
    plan = plan_new_project("demo", core_root / "sub", core_root)

    with pytest.raises(typer.Exit):
        write_new_project(plan, core_root, write=write)
    assert not (core_root / "sub").exists()
