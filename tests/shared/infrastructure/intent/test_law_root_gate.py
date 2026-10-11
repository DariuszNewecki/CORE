# tests/shared/infrastructure/intent/test_law_root_gate.py
"""Startup law-root gate (ADR-132 D10 · D2, C1): a service never judges
against a missing law root or the machinery floor."""

from __future__ import annotations

from pathlib import Path

import pytest

from shared.infrastructure.intent.law_root_gate import (
    EX_CONFIG,
    LawRootRefusal,
    law_root_problem,
    require_service_law_root,
)


def _law(root: Path) -> Path:
    mind = root / ".intent"
    (mind / "rules" / "architecture").mkdir(parents=True)
    (mind / "rules" / "architecture" / "r.json").write_text('{"rules": []}\n')
    return mind


# ID: cf3889fb-9c18-485f-b43e-d1d142cd9f5e
def test_real_law_root_passes(tmp_path: Path) -> None:
    mind = _law(tmp_path)
    assert law_root_problem(mind) is None
    require_service_law_root("test", mind)


# ID: ffed72b1-ff1c-4fac-85c3-3317d9058302
def test_missing_root_refused(tmp_path: Path) -> None:
    assert "does not exist" in (law_root_problem(tmp_path / "nope") or "")


# ID: aca95d1c-81d9-476b-aa38-44e8a42111e4
def test_root_without_rules_refused(tmp_path: Path) -> None:
    mind = tmp_path / ".intent"
    (mind / "rules").mkdir(parents=True)
    assert "no rules" in (law_root_problem(mind) or "")


# ID: 1d877a2c-14f3-4c45-921b-a5341aaedf3d
def test_machinery_floor_refused() -> None:
    import shared

    floor = Path(shared.__file__).resolve().parent / "_machinery_floor"
    assert floor.is_dir()
    assert "machinery floor" in (law_root_problem(floor) or "")


# ID: 5a4f466c-5fe9-40b4-9b88-e2237d2ae422
def test_require_raises_with_exit_78(tmp_path: Path) -> None:
    with pytest.raises(LawRootRefusal, match="refuses to start") as exc:
        require_service_law_root("CORE daemon", tmp_path / "nope")
    assert exc.value.exit_code == EX_CONFIG == 78
