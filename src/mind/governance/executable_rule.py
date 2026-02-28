# src/mind/governance/executable_rule.py
"""
ExecutableRule - Represents a constitutional rule that can be executed via an engine.

This dataclass bridges the gap between policy JSON declarations and runtime execution.
It extracts the essential execution information from policy rules, allowing the audit
system to execute rules directly from JSON without requiring Python Check classes.

Design Philosophy:
- Rules live in .intent/ policies (Mind layer)
- Engines execute them (Body layer)
- This dataclass is just the connector (pure data)

Ref: Dynamic Rule Execution Architecture
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ID: e7f9d2c8-4a3b-5e1f-9d6c-8b7a2e4f1c3d
@dataclass
# ID: ff4bed96-5d93-4e3f-84dc-5f980af199fb
class ExecutableRule:
    """
    Represents a constitutional rule ready for execution.

    Extracted from policy JSON with structure:
    {
        "id": "rule.name",
        "enforcement": "error",
        "authority": "policy",          # "constitution" | "policy"
        "check": {
            "engine": "ast_gate",
            "params": {"check_type": "...", ...}
        },
        "scope": ["src/**/*.py"],
        "exclusions": ["tests/**"]
    }
    """

    rule_id: str
    """Unique rule identifier (e.g., 'async.runtime.no_nested_loop_creation')"""

    engine: str
    """Engine identifier (e.g., 'ast_gate', 'llm_gate', 'knowledge_gate')"""

    params: dict[str, Any]
    """Engine-specific parameters (e.g., {'check_type': 'restrict_event_loop_creation'})"""

    enforcement: str
    """Severity level: 'error' or 'warning'"""

    statement: str = ""
    """Human-readable rule statement"""

    scope: list[str] = field(default_factory=lambda: ["src/**/*.py"])
    """File patterns to include (glob patterns)"""

    exclusions: list[str] = field(default_factory=list)
    """File patterns to exclude (glob patterns)"""

    policy_id: str = ""
    """Source policy identifier for traceability"""

    is_context_level: bool = False
    """
    Whether this rule operates on full AuditorContext vs individual files.

    - True: Engine needs full context (knowledge_gate, workflow_gate)
    - False: Engine operates file-by-file (ast_gate, glob_gate, regex_gate)

    Set automatically by rule_extractor based on engine type.
    """

    authority: str = "policy"
    """
    Who declared this rule and how binding it is.

    - "constitution": Declared by the sovereign constitution. Always blocks,
      regardless of strict_mode. These rules cannot be made advisory.
    - "policy":       Declared by an operational policy. Advisory by default;
      blocks only when IntentGuard is initialised with strict_mode=True.

    Sourced directly from the rule's 'authority' field in the .intent/ document.
    Defaults to "policy" (the safer, less disruptive tier) when absent.
    """

    def __repr__(self) -> str:
        """Concise representation for logging."""
        return f"ExecutableRule({self.rule_id}, engine={self.engine}, authority={self.authority})"
