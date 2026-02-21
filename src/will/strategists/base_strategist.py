# src/will/strategists/base_strategist.py
# ID: d6e4b5c7-e8f9-0123-defa-123456789013
"""Base Strategist - RUNTIME phase base class.

All Will strategists make rule-based decisions without LLMs.
They return structured decisions with confidence scores.

Owning `phase` here eliminates AST duplication across:
    ClarityStrategist, ComplexityStrategist, FixStrategist,
    SyncStrategist, ValidationStrategist, GovernanceDecider.
"""

from __future__ import annotations

from shared.component_primitive import Component, ComponentPhase


# ID: e7f5c6d8-f901-2345-efab-234567890124
class BaseStrategist(Component):
    """Base class for all RUNTIME phase strategists.

    Subclasses must implement execute(). They inherit phase automatically.
    Strategists are deterministic decision-makers — no LLM, no side effects.
    """

    @property
    # ID: f8a6d7e9-0012-3456-fabc-345678901235
    def phase(self) -> ComponentPhase:
        """All strategists operate in the RUNTIME phase."""
        return ComponentPhase.RUNTIME
