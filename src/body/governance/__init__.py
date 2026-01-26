# src/body/governance/__init__.py
"""
Body Layer Governance Module

CONSTITUTIONAL FIX: Governance execution logic (Body layer)

This module contains execution components for constitutional governance.
These components were moved from Mind layer to comply with Mind-Body-Will separation.

Constitutional Architecture:
- Mind layer (src/mind/governance/) - Pure query interface to .intent/
- Body layer (src/body/governance/) - Execution logic for governance
- Will layer (src/will/) - Decision-making and orchestration

Components:
- risk_classification_service.py: Risk assessment and governance decisions
"""

from __future__ import annotations

from body.governance.risk_classification_service import (
    ApprovalType,
    GovernanceDecision,
    RiskClassificationService,
    RiskTier,
)


__all__ = [
    "ApprovalType",
    "GovernanceDecision",
    "RiskClassificationService",
    "RiskTier",
]
