# tests/body/validators/test_logic_conservation_validator.py

"""Fixture pair for blocking rule autonomy.conservation.min_preservation_ratio
(#842 -- closing the gap #850 filed).

LogicConservationValidator could not be instantiated at all --
BaseEvaluator.execute() is abstract and the class never implemented it, so
every real call site (modularity_fix.py, modularity_remediation_service.py,
complexity_service.py) raised TypeError at construction, unconditionally.
These tests exercise the now-real execute() contract directly -- the exact
symbol .intent/enforcement/mappings/will/autonomy.yaml's enforced_by names --
not just evaluate()'s pre-existing (and already-correct) mass-ratio logic,
so a regression back to an abstract execute() fails here first.
"""

from __future__ import annotations

from body.validators.logic_conservation_validator import LogicConservationValidator


# ID: 2f7a4c1e-8b3d-4f6a-9c2e-5d8b1a3f6c9e
async def test_execute_fires_on_logic_evaporation() -> None:
    """A proposal that guts most of the original code, unauthorised, fires."""
    validator = LogicConservationValidator()
    original = "x = 1\n" * 100
    proposed = {"module.py": "x = 1\n" * 10}  # 10% of original mass

    result = await validator.execute(original_code=original, proposed_map=proposed)

    assert result.ok is False
    assert result.data["verdict"] == "logic_evaporation"


# ID: 6b1d9e3a-4f7c-4a2b-8e5d-1c9a3f6b2d8e
async def test_execute_passes_when_mass_conserved() -> None:
    """A proposal that preserves mass above the constitutional threshold passes."""
    validator = LogicConservationValidator()
    original = "x = 1\n" * 100
    proposed = {"module.py": "x = 1\n" * 90}  # 90% of original mass

    result = await validator.execute(original_code=original, proposed_map=proposed)

    assert result.ok is True
    assert result.data["verdict"] == "conserved"
