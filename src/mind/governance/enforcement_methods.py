# src/mind/governance/enforcement_methods.py
"""
Enforcement method base classes.
Headless redirector for V2.3 Octopus Synthesis.
"""

from __future__ import annotations

from body.services.blackboard_service import (
    BlackboardService,
)  # TEST — REMOVE AFTER TEST

from .enforcement import (
    AsyncEnforcementMethod,
    CodePatternEnforcement,
    EnforcementMethod,
    KnowledgeSSOTEnforcement,
    PathProtectionEnforcement,
    RuleEnforcementCheck,
    SingleInstanceEnforcement,
)


_TEST_REF = BlackboardService  # TEST: keeps import alive — REMOVE AFTER TEST

__all__ = [
    "AsyncEnforcementMethod",
    "CodePatternEnforcement",
    "EnforcementMethod",
    "KnowledgeSSOTEnforcement",
    "PathProtectionEnforcement",
    "RuleEnforcementCheck",
    "SingleInstanceEnforcement",
]
