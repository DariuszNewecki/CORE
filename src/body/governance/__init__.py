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
- intent_guard.py: Constitutional enforcement orchestrator (MOVED from Mind)
- intent_pattern_validators.py: Pattern validation (MOVED from Mind)

Import directly from submodules:
    from body.governance.intent_guard import IntentGuard
"""

from __future__ import annotations

# NO re-exports to avoid circular imports
# Import directly from submodules instead
