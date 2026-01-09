# src/will/strategists/__init__.py

"""
Strategists - Runtime decision phase components.

Strategists make rule-based decisions without LLMs.
They provide clear reasoning for their choices.

Available Strategists:
- TestStrategist: Select test generation strategy based on file type

Constitutional Alignment:
- Phase: RUNTIME (decision-making)
- Rule-based logic (no LLM overhead)
- Returns decisions with confidence scores

Usage:
    from will.strategists import TestStrategist

    strategist = TestStrategist()
    result = await strategist.execute(
        file_type="sqlalchemy_model",
        complexity="high"
    )

    # Use result.data['strategy'] and result.data['constraints']
"""

from __future__ import annotations

from .clarity_strategist import ClarityStrategist
from .complexity_strategist import ComplexityStrategist
from .fix_strategist import FixStrategist
from .sync_strategist import SyncStrategist
from .test_strategist import TestStrategist
from .validation_strategist import ValidationStrategist


__all__ = [
    "ClarityStrategist",
    "ComplexityStrategist",
    "FixStrategist",
    "SyncStrategist",
    "TestStrategist",
    "ValidationStrategist",
]
