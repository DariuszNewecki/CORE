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
- remediation_service.py: Fix constitutional violations

Note: Governance decision logic moved to body/services/constitutional_validator.py
      for proper singleton management and IntentRepository integration.
"""

from __future__ import annotations

# Re-export from constitutional_validator for backward compatibility
from body.services.constitutional_validator import (
    ApprovalType,
    GovernanceDecision,
    RiskTier,
)


__all__ = [
    "ApprovalType",
    "GovernanceDecision",
    "RiskTier",
]
