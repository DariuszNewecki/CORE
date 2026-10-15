"""`core-admin project init` — the machinery floor into an existing repository (#1023).

Before #1023 an existing repository could get its ``.intent/`` floor only from
``core project onboard`` (core-cli + a running CORE API, Postgres, Qdrant);
from a plain ``pip install core-runtime`` only a new project could. ``init``
copies the same bundled floor, file-only, and never overwrites.
"""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import typer

from cli.logic.byor import _machinery_floor_files, _resolve_machinery_floor
from cli.resources.project.adopt_pack import adopt_pack_command
from cli.resources.project.init import init_project_command


@pytest.fixture(autouse=True)
def _standalone_install(monkeypatch: pytest.MonkeyPatch) -> None:
    """No CORE database configured, no CORE checkout to protect: a plain pip install."""
    monkeypatch.setattr(
        "body.services.outside_write_ledger.database_is_configured", lambda: False
    )
    monkeypatch.setattr("cli.resources.project.init.core_source_root", lambda: None)


def _ctx() -> MagicMock:
    ctx = MagicMock(spec=typer.Context)
    ctx.obj = MagicMock()
    return ctx


def _existing_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "existing"
    (repo / "app").mkdir(parents=True)
    (repo / "app" / "calc.py").write_text("def add(a, b):\n    return a + b\n")
    (repo / "README.md").write_text("mine\n")
    return repo


def _floor() -> list[str]:
    floor = _resolve_machinery_floor(None)
    return sorted(
        f".intent/{p.relative_to(floor).as_posix()}"
        for p in _machinery_floor_files(floor)
    )


# ID: 17b2b816-84c2-4213-9103-06863602835f
async def test_write_delivers_the_floor_and_leaves_the_repository_alone(
    tmp_path: Path,
) -> None:
    repo = _existing_repo(tmp_path)
    await init_project_command(_ctx(), repo, True)
    delivered = sorted(
        p.relative_to(repo).as_posix()
        for p in (repo / ".intent").rglob("*")
        if p.is_file()
    )
    assert delivered == _floor() and delivered
    assert (repo / ".intent" / "META").is_dir()
    assert not (repo / ".intent" / "rules").exists()  # no law
    assert (repo / "README.md").read_text() == "mine\n"
    assert (repo / "app" / "calc.py").is_file()
    assert not (repo / "pyproject.toml").exists()  # no skeleton


# ID: 6bdb5a6f-5f92-4f2e-845d-23d34c9038cc
async def test_preview_writes_nothing(tmp_path: Path) -> None:
    repo = _existing_repo(tmp_path)
    await init_project_command(_ctx(), repo, False)
    assert not (repo / ".intent").exists()


# ID: db64d3d7-3f8e-4adf-9bce-39a4ad4c86f2
@pytest.mark.parametrize("write", [False, True])
async def test_an_existing_intent_is_never_overwritten(
    tmp_path: Path, write: bool
) -> None:
    repo = _existing_repo(tmp_path)
    (repo / ".intent").mkdir()
    (repo / ".intent" / "own.yaml").write_text("mine: true\n")
    with pytest.raises(typer.Exit):
        await init_project_command(_ctx(), repo, write)
    assert [p.name for p in (repo / ".intent").iterdir()] == ["own.yaml"]


# ID: 27677c14-3a2b-4e98-b24d-3dff23844983
async def test_a_missing_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(typer.Exit):
        await init_project_command(_ctx(), tmp_path / "absent", True)
    assert not (tmp_path / "absent").exists()


# ID: 561411cb-6b22-4e14-8154-e66b9b5452b6
async def test_cores_own_repository_is_refused(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    repo = _existing_repo(tmp_path)
    monkeypatch.setattr("cli.resources.project.init.core_source_root", lambda: repo)
    with pytest.raises(typer.Exit):
        await init_project_command(_ctx(), repo / "app", True)
    assert not (repo / "app" / ".intent").exists()


# ID: fe81058b-943c-4bf0-b73d-948ec77a763b
async def test_after_init_a_pack_can_be_adopted(tmp_path: Path) -> None:
    """The proof path: existing repo -> init -> adopt-pack, no services."""
    repo = _existing_repo(tmp_path)
    await init_project_command(_ctx(), repo, True)
    with patch(
        "cli.logic.byor.core_source_root", return_value=tmp_path / "core-install"
    ):
        await adopt_pack_command.__wrapped__(
            pack_id="core/starter-python", target_dir=repo, write=True, override=[]
        )
    assert (repo / ".intent" / "rules" / "packs" / "core_starter_python.json").is_file()
