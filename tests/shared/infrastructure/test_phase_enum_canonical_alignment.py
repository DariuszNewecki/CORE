# tests/shared/infrastructure/test_phase_enum_canonical_alignment.py

"""
Phase-enum drift guard (issue #460).

These tests are the principle-2 safety net for the Python sites where
dynamic loading from `.intent/META/enums.json` is impractical
(typing.Literal aliases, str-Enum classes). They fail noisily when the
Python mirror drifts from the canonical store so the closed-enum
discipline holds even though the consumer-side member list is repeated
in code for static-typing reasons.
"""

from __future__ import annotations

from typing import get_args

from shared.component_primitive import ComponentPhase
from shared.infrastructure.context.models import PhaseType
from shared.infrastructure.intent.canonical_enums import (
    get_enum_members,
    reload_enums_cache,
)


def setup_function(_func) -> None:
    """Force a fresh read of enums.json for every test."""
    reload_enums_cache()


def test_component_phase_enum_mirrors_canonical_phase() -> None:
    """ComponentPhase (Python) must enumerate exactly the canonical `phase` set."""
    canonical = get_enum_members("phase")
    python_members = {member.value for member in ComponentPhase}
    assert python_members == canonical, (
        f"ComponentPhase has drifted from canonical `phase` enum.\n"
        f"  Python: {sorted(python_members)}\n"
        f"  Canonical: {sorted(canonical)}\n"
        f"Fix by updating either src/shared/component_primitive.py "
        f"ComponentPhase or .intent/META/enums.json definitions.phase."
    )


def test_phase_type_literal_mirrors_canonical_component_phase() -> None:
    """PhaseType Literal must enumerate exactly the canonical `component_phase`."""
    canonical = get_enum_members("component_phase")
    literal_members = set(get_args(PhaseType))
    assert literal_members == canonical, (
        f"PhaseType Literal has drifted from canonical `component_phase` enum.\n"
        f"  Python: {sorted(literal_members)}\n"
        f"  Canonical: {sorted(canonical)}\n"
        f"Fix by updating either src/shared/infrastructure/context/models.py "
        f"PhaseType or .intent/META/enums.json definitions.component_phase."
    )


def test_worker_phase_is_proper_subset_of_phase() -> None:
    """worker_phase must be a (possibly improper) subset of `phase`."""
    worker_phase = get_enum_members("worker_phase")
    phase = get_enum_members("phase")
    assert worker_phase <= phase, (
        f"worker_phase contains members not in canonical phase:\n"
        f"  Extra: {sorted(worker_phase - phase)}"
    )


def test_component_phase_is_proper_subset_of_phase() -> None:
    """component_phase must be a (possibly improper) subset of `phase`."""
    component_phase = get_enum_members("component_phase")
    phase = get_enum_members("phase")
    assert component_phase <= phase, (
        f"component_phase contains members not in canonical phase:\n"
        f"  Extra: {sorted(component_phase - phase)}"
    )


def test_interpret_is_excluded_from_component_phase() -> None:
    """component_phase must exclude `interpret` (it runs at the Will layer)."""
    assert "interpret" not in get_enum_members("component_phase"), (
        "component_phase has gained `interpret`. The INTERPRET phase runs "
        "at the Will/interpreter layer before any Component is dispatched; "
        "Components do not operate in it."
    )


def test_interpret_parse_load_excluded_from_worker_phase() -> None:
    """worker_phase must exclude `interpret`, `parse`, `load`."""
    worker_phase = get_enum_members("worker_phase")
    for excluded in ("interpret", "parse", "load"):
        assert excluded not in worker_phase, (
            f"worker_phase has gained {excluded!r}. Workers operate only in "
            f"the execution-side phases; interpret/parse/load run before any "
            f"worker is dispatched."
        )
