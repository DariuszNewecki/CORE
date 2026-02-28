# src/mind/governance/policy_rule.py
"""
PolicyRule data structure for constitutional governance.

Represents a single constitutional rule with engine dispatch capability.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
# ID: d337536c-f552-432d-94a6-a2431db94dd3
class PolicyRule:
    """
    Structured representation of a constitutional policy rule.

    Attributes:
        name: Unique rule identifier (e.g., "di.no_global_session_import")
        pattern: Glob pattern for file matching (e.g., "src/**/*.py")
        action: Rule action - "deny", "warn", or engine-based
        description: Human-readable rule explanation
        severity: "error" or "warning"
        source_policy: Policy file this rule came from
        engine: Optional engine ID for verification (e.g., "ast_gate")
        params: Optional parameters for engine execution
        authority: Binding tier — "constitution" always blocks;
                   "policy" blocks only when strict_mode=True
    """

    name: str
    pattern: str
    action: str
    description: str
    severity: str = "error"
    source_policy: str = "unknown"
    # Engine dispatch fields
    engine: str | None = None
    params: dict[str, Any] | None = None
    # Binding tier — sourced from the rule's 'authority' field in .intent/
    authority: str = "policy"

    @classmethod
    # ID: ef47b7d5-3232-4a9d-8edc-3532e70a92f2
    def from_dict(cls, data: dict[str, Any], source: str = "unknown") -> PolicyRule:
        """
        Parse rule from constitutional JSON/YAML.

        Expected structure:
        {
          "id": "rule.name",
          "statement": "description",
          "authority": "policy",
          "check": {
            "engine": "ast_gate",
            "params": {"check_type": "import_boundary", ...}
          },
          "enforcement": "error",
          "scope": ["src/**/*.py"]
        }

        Args:
            data: Raw rule dictionary from policy file
            source: Source policy name for traceability

        Returns:
            Parsed PolicyRule instance
        """
        # Extract check block if present (engine dispatch)
        check_block = data.get("check", {})
        engine_id = check_block.get("engine") if isinstance(check_block, dict) else None
        params = check_block.get("params", {}) if isinstance(check_block, dict) else {}

        # Extract pattern from scope (first entry) or pattern field
        scope = data.get("scope", [])
        pattern = ""
        if isinstance(scope, list) and scope:
            pattern = str(scope[0])
        elif data.get("pattern"):
            pattern = str(data.get("pattern"))

        return cls(
            name=str(data.get("name") or data.get("id") or "unnamed"),
            pattern=pattern,
            action=str(data.get("action") or "deny"),
            description=str(data.get("description") or data.get("statement") or ""),
            severity=str(data.get("severity") or data.get("enforcement") or "error"),
            source_policy=source,
            engine=engine_id,
            params=params,
            authority=str(data.get("authority", "policy")),
        )
