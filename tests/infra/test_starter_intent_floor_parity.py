"""The published starter carries a byte-identical copy of the bundled floor.

``examples/starter-intent/.intent/`` (mirrored to core-audit-demo) must run
as-is, and the audit does not fall back to the bundled machinery floor for a
rules-only ``.intent/`` (ADR-108 D3 is incomplete there). So the starter
carries the floor itself; this test keeps that copy from drifting away from
``shared._machinery_floor`` when the floor changes.

The starter's own ``constitution/CONSTITUTION.md`` is excluded: it describes
the starter's four rules, while the floor's copy is a stub.
"""

from __future__ import annotations

from pathlib import Path

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
FLOOR = REPO_ROOT / "src" / "shared" / "_machinery_floor"
STARTER_INTENT = REPO_ROOT / "examples" / "starter-intent" / ".intent"


def _floor_files() -> list[str]:
    return sorted(
        p.relative_to(FLOOR).as_posix()
        for p in FLOOR.rglob("*")
        if p.is_file()
        and p.name != "__init__.py"
        and "__pycache__" not in p.parts
        and p.relative_to(FLOOR).parts[0] != "constitution"
    )


def test_floor_has_files() -> None:
    assert len(_floor_files()) > 20


@pytest.mark.parametrize("rel", _floor_files())
def test_starter_carries_identical_floor_file(rel: str) -> None:
    starter_file = STARTER_INTENT / rel
    assert starter_file.is_file(), f"starter is missing floor file {rel}"
    assert starter_file.read_bytes() == (FLOOR / rel).read_bytes(), (
        f"starter copy of {rel} differs from shared/_machinery_floor"
    )
