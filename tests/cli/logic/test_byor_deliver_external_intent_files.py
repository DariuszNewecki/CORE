"""Tests for ``cli.logic.byor.deliver_external_intent_files`` — the ADR-111 D3
delivery lane that ``project adopt-pack`` (ADR-149) writes through.

Regression context: ``adopt-pack --write`` crashed from the day it was written
(2026-07-14, ``f6513de4``) on a dead ``shared.infrastructure.file_handler``
import, and — once that was corrected — on FileHandler's governed-artifact
hard block of any literal ``.intent/`` path. Neither failure was caught
because the module had no tests. These pin the lane's contract:

- writes land under ``<target>/.intent/`` with parent dirs created;
- targets inside CORE's own tree are refused (``_reject_unsafe_target``);
- non-``.intent/`` and traversal paths are refused before any write.
"""

from __future__ import annotations

from pathlib import Path

import pytest
import typer

from cli.logic.byor import deliver_external_intent_files


def test_writes_files_under_target_intent(tmp_path: Path) -> None:
    core_root = tmp_path / "core"
    core_root.mkdir()
    target = tmp_path / "repos" / "my-project"
    target.mkdir(parents=True)

    written = deliver_external_intent_files(
        target,
        core_root,
        {
            ".intent/rules/packs/x.json": '{"kind": "rule_document"}\n',
            ".intent/enforcement/mappings/packs/x.yaml": "mappings:\n",
        },
    )

    assert written == 2
    assert (target / ".intent/rules/packs/x.json").read_text() == (
        '{"kind": "rule_document"}\n'
    )
    assert (target / ".intent/enforcement/mappings/packs/x.yaml").read_text() == (
        "mappings:\n"
    )


def test_refuses_target_inside_core_root(tmp_path: Path) -> None:
    core_root = tmp_path / "core"
    inside = core_root / "var" / "tmp" / "probe"
    inside.mkdir(parents=True)

    with pytest.raises(typer.Exit):
        deliver_external_intent_files(
            inside, core_root, {".intent/rules/packs/x.json": "{}\n"}
        )
    assert not (inside / ".intent").exists()


def test_refuses_core_root_itself(tmp_path: Path) -> None:
    core_root = tmp_path / "core"
    core_root.mkdir()

    with pytest.raises(typer.Exit):
        deliver_external_intent_files(
            core_root, core_root, {".intent/rules/packs/x.json": "{}\n"}
        )
    assert not (core_root / ".intent").exists()


@pytest.mark.parametrize(
    "bad_rel",
    ["rules/packs/x.json", "src/evil.py", ".intent/../escape.txt"],
)
def test_refuses_non_intent_or_traversal_paths(tmp_path: Path, bad_rel: str) -> None:
    core_root = tmp_path / "core"
    core_root.mkdir()
    target = tmp_path / "target"
    target.mkdir()

    with pytest.raises(ValueError):
        deliver_external_intent_files(target, core_root, {bad_rel: "x\n"})
    assert list(target.rglob("*")) == []
