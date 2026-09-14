"""Tests for ``core-admin project adopt-pack`` (ADR-149).

Calls the undecorated coroutine (``adopt_pack_command.__wrapped__``) so the
``@core_command`` loop/teardown machinery stays out of the way. The pack is
resolved from CORE's real ``packs/`` registry — the same registry the wheel
ships — and delivered to a ``tmp_path`` target through the ADR-111 D3 lane;
``resolve_default_repo_path`` is patched so the target is not refused as
"inside CORE".

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


async def _run(target: Path, *, write: bool, override: list[str] | None = None):
    # Pretend CORE lives elsewhere so the tmp target is a legitimate external repo.
    with patch(
        "cli.resources.project.adopt_pack.resolve_default_repo_path",
        return_value=target.parent / "core-install",
    ):
        await adopt_pack_command.__wrapped__(
            pack_id=PACK_ID, target_dir=target, write=write, override=override or []
        )


@pytest.mark.asyncio
async def test_preview_writes_nothing(tmp_path: Path) -> None:
    target = _bare_repo(tmp_path)
    await _run(target, write=False)
    assert not (target / ".intent").exists()


@pytest.mark.asyncio
async def test_write_delivers_rules_and_mappings_to_bare_repo(tmp_path: Path) -> None:
    target = _bare_repo(tmp_path)
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

    # A bare repo has no META/intent_tree.yaml — the pack is delivered without it.
    assert not (target / ".intent" / "META").exists()


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
    target.mkdir(parents=True)

    with patch(
        "cli.resources.project.adopt_pack.resolve_default_repo_path",
        return_value=core,
    ):
        with pytest.raises(typer.Exit):
            await adopt_pack_command.__wrapped__(
                pack_id=PACK_ID, target_dir=target, write=True, override=[]
            )
    assert not (target / ".intent").exists()


@pytest.mark.asyncio
async def test_unknown_pack_exits(tmp_path: Path) -> None:
    target = _bare_repo(tmp_path)
    with pytest.raises(typer.Exit):
        await adopt_pack_command.__wrapped__(
            pack_id="core/does-not-exist", target_dir=target, write=False, override=[]
        )
