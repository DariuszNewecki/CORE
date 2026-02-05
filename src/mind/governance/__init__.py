# src/mind/governance/__init__.py
"""
Mind Layer Governance Module

CONSTITUTIONAL ARCHITECTURE:
Mind layer contains pure query interfaces and data structures.
Execution logic has been moved to Body layer.

COMPATIBILITY NOTE:
Execution components (IntentGuard, EngineDispatcher, PatternValidators)
have moved to body.governance. Update imports:

OLD: from body.governance.intent_guard import IntentGuard
NEW: from body.governance.intent_guard import IntentGuard

Data structures (ViolationReport, PolicyRule) remain in Mind.
"""

from __future__ import annotations

# NO re-exports to avoid circular imports
# Import directly from the actual module locations
