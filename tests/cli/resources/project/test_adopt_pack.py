"""Tests for ``core-admin project adopt-pack`` (ADR-149).

Calls the undecorated coroutine (``adopt_pack_command.__wrapped__``) so the
``@core_command`` loop/teardown machinery stays out of the way. The pack is
resolved from CORE's real ``packs/`` registry (repository first) or, for a
law root whose repository has no ``packs/``, from the registry bundled in the
wheel — and delivered to a ``tmp_path`` target through the ADR-111 D3 lane;
``core_source_root`` is patched so the target is not refused as
"inside CORE".

Regression (2026-10-02): a pip-installed adopter's law root is their own
repository, which has no ``packs/``; the 2.10.2 wheel shipped no packs either,
so every pack was "not found". The bundled-registry test below pins the fix.

Regression: ``--write`` crashed from the day the command was written
(2026-07-14, ``f6513de4``) — first on a dead ``shared.infrastructure.
file_handler`` import, then on FileHandler's ``.intent/`` hard block — and no
test existed to notice. The preview path never touched either.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest
import typer
import yaml

from cli.resources.project.adopt_pack import adopt_pack_command


PACK_ID = "core/starter-python"
SLUG = "core_starter_python"


def _bare_repo(tmp_path: Path) -> Path:
    target = tmp_path / "target-repo"
    (target / "pkg").mkdir(parents=True)
    (target / "pkg" / "a.py").write_text("print('x')\n")
    return target


def _floored_repo(tmp_path: Path) -> Path:
    """A repo carrying the machinery floor's META/ (all adopt-pack checks for)."""
    target = _bare_repo(tmp_path)
    tree = target / ".intent" / "META" / "intent_tree.yaml"
    tree.parent.mkdir(parents=True)
    tree.write_text("packs: []\n")
    return target


async def _run(target: Path, *, write: bool, override: list[str] | None = None):
    # Pretend CORE lives elsewhere so the tmp target is a legitimate external repo.
    with patch(
        "cli.logic.byor.core_source_root",
        return_value=target.parent / "core-install",
    ):
        await adopt_pack_command.__wrapped__(
            pack_id=PACK_ID, target_dir=target, write=write, override=override or []
        )


@pytest.mark.asyncio
async def test_preview_writes_nothing(tmp_path: Path) -> None:
    target = _floored_repo(tmp_path)
    await _run(target, write=False)
    assert not (target / ".intent" / "rules").exists()
    assert (target / ".intent" / "META" / "intent_tree.yaml").read_text() == (
        "packs: []\n"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("write", [False, True])
async def test_refuses_repo_without_machinery_floor(
    tmp_path: Path, write: bool
) -> None:
    """Regression (#939): rules delivered into a floor-less repo are rules the
    audit cannot load; the command used to write them and say "Pack applied"."""
    target = _bare_repo(tmp_path)
    with pytest.raises(typer.Exit) as exc:
        await _run(target, write=write)
    assert exc.value.exit_code == 1
    assert not (target / ".intent").exists()


@pytest.mark.asyncio
async def test_write_delivers_rules_and_mappings(tmp_path: Path) -> None:
    target = _floored_repo(tmp_path)
    await _run(target, write=True)

    rules = target / ".intent" / "rules" / "packs" / f"{SLUG}.json"
    mappings = (
        target / ".intent" / "enforcement" / "mappings" / "packs" / f"{SLUG}.yaml"
    )
    assert rules.is_file() and mappings.is_file()

    doc = json.loads(rules.read_text())
    assert doc["kind"] == "rule_document"
    assert doc["metadata"]["id"] == f"rules.packs.{SLUG}"
    rule_ids = {r["id"] for r in doc["rules"]}
    assert rule_ids, "pack delivered no rules"

    mapped = yaml.safe_load(mappings.read_text())["mappings"]
    assert set(mapped) == rule_ids, "every pack rule must carry an enforcement mapping"

    tree = yaml.safe_load(
        (target / ".intent" / "META" / "intent_tree.yaml").read_text()
    )
    assert [p["id"] for p in tree["packs"]] == [PACK_ID]


@pytest.mark.asyncio
async def test_write_upserts_pack_into_existing_intent_tree(tmp_path: Path) -> None:
    target = _bare_repo(tmp_path)
    tree = target / ".intent" / "META" / "intent_tree.yaml"
    tree.parent.mkdir(parents=True)
    tree.write_text("packs:\n- id: other/pack\n  source: local\n")

    await _run(target, write=True, override=["starter.no_print:advisory"])

    data = yaml.safe_load(tree.read_text())
    by_id = {p["id"]: p for p in data["packs"]}
    assert set(by_id) == {"other/pack", PACK_ID}
    assert by_id[PACK_ID]["overrides"] == [
        {"rule_id": "starter.no_print", "enforcement": "advisory"}
    ]

    rules = target / ".intent" / "rules" / "packs" / f"{SLUG}.json"
    doc = json.loads(rules.read_text())
    assert (
        next(r for r in doc["rules"] if r["id"] == "starter.no_print")["enforcement"]
        == "advisory"
    )


@pytest.mark.asyncio
async def test_write_is_idempotent(tmp_path: Path) -> None:
    target = _bare_repo(tmp_path)
    tree = target / ".intent" / "META" / "intent_tree.yaml"
    tree.parent.mkdir(parents=True)
    tree.write_text("packs: []\n")

    await _run(target, write=True)
    await _run(target, write=True)

    data = yaml.safe_load(tree.read_text())
    assert [p["id"] for p in data["packs"]] == [PACK_ID]


@pytest.mark.asyncio
async def test_write_refuses_target_inside_core_root(tmp_path: Path) -> None:
    core = tmp_path / "core-install"
    target = core / "var" / "tmp" / "probe"
    (target / ".intent" / "META").mkdir(parents=True)

    with patch(
        "cli.logic.byor.core_source_root",
        return_value=core,
    ):
        with pytest.raises(typer.Exit):
            await adopt_pack_command.__wrapped__(
                pack_id=PACK_ID, target_dir=target, write=True, override=[]
            )
    assert not (target / ".intent" / "rules").exists()


@pytest.mark.asyncio
async def test_unknown_pack_exits(tmp_path: Path) -> None:
    target = _bare_repo(tmp_path)
    with pytest.raises(typer.Exit):
        await adopt_pack_command.__wrapped__(
            pack_id="core/does-not-exist", target_dir=target, write=False, override=[]
        )


@pytest.mark.asyncio
async def test_pack_resolves_from_bundle_when_law_root_repo_has_no_packs(
    tmp_path: Path,
) -> None:
    """The pip-install case: law root = the adopter's repo, which has no packs/."""
    from types import SimpleNamespace

    adopter = _floored_repo(tmp_path)
    assert not (adopter / "packs").exists()

    with (
        patch(
            "cli.resources.project.adopt_pack.settings",
            SimpleNamespace(MIND=adopter / ".intent"),
        ),
        # An installed wheel: there is no CORE source checkout to protect.
        patch("cli.logic.byor.core_source_root", return_value=None),
    ):
        await adopt_pack_command.__wrapped__(
            pack_id=PACK_ID, target_dir=adopter, write=True, override=[]
        )

    rules = adopter / ".intent" / "rules" / "packs" / f"{SLUG}.json"
    assert rules.is_file()
