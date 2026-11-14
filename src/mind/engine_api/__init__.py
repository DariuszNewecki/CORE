# src/mind/engine_api/__init__.py

"""The public engine interface (ADR-177 D6).

An engine outside CORE imports from here and nowhere else in ``mind``: only
this module is promised across 3.x (ADR-176 D3); everything under
``mind.logic`` is internal and may move.
"""

from __future__ import annotations

from mind.logic.engines.base import (
    CONTENT_NOT_EVALUATED,
    CORE_ENGINE_API,
    BaseEngine,
    EngineResult,
    normalize_violation,
)
from mind.logic.record_contract import RecordFinding, RulePart
from shared.models.audit_models import EvidenceClass


__all__ = [
    "CONTENT_NOT_EVALUATED",
    "CORE_ENGINE_API",
    "BaseEngine",
    "EngineResult",
    "EvidenceClass",
    "RecordFinding",
    "RulePart",
    "normalize_violation",
]
