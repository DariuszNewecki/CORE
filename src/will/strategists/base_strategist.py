# src/will/strategists/base_strategist.py
"""Base Strategist - RUNTIME phase base class.

All Will strategists make rule-based decisions without LLMs.
They return structured decisions with confidence scores.

Owning `phase` here eliminates AST duplication across:
    ClarityStrategist, ComplexityStrategist, FixStrategist,
    SyncStrategist, ValidationStrategist, GovernanceDecider.
"""

from __future__ import annotations

from shared.component_primitive import Component, ComponentPhase


# ID: 35a786be-41d1-4f4a-954e-2a90bb969748
class BaseStrategist(Component):
    """Base class for all RUNTIME phase strategists.

    Subclasses must implement execute(). They inherit phase automatically.
    Strategists are deterministic decision-makers — no LLM, no side effects.
    """

    @property
    # ID: 0f2f5182-f962-4dc6-aa39-762a86b5bf15
    def phase(self) -> ComponentPhase:
        """All strategists operate in the RUNTIME phase."""
        return ComponentPhase.RUNTIME
