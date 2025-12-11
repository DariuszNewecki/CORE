# src/mind/governance/schemas.py
"""
Constitutional Resource Schemas.

Data models for constitutional policies and patterns loaded from .intent/.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
# ID: c9728355-9313-4ab3-9258-813393a0b195
class PolicyResource:
    """A constitutional policy loaded from .intent/charter/policies/."""

    policy_id: str
    version: str
    title: str
    status: str
    purpose: str
    rules: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_file: str = ""


@dataclass
# ID: 45a15e98-cf61-4f87-b2b4-c023fb783654
class PatternResource:
    """An architectural pattern loaded from .intent/charter/patterns/."""

    pattern_id: str
    version: str
    title: str
    status: str
    purpose: str
    patterns: list[dict[str, Any]] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    source_file: str = ""


@dataclass
# ID: 7707cd60-24ba-4adf-a5c8-30e40c75f584
class ConstitutionalPrinciple:
    """A principle from constitutional governance documents."""

    principle_id: str
    statement: str
    rationale: str
    scope: list[str]
    enforcement_method: str
    enforcement_parameters: dict[str, Any]
    source_document: str


# Union type for loading different resource types
ConstitutionalResource = PolicyResource | PatternResource


@dataclass
# ID: 7e345c64-8b5d-4879-8b05-fd1a1c96f4b2
class GovernanceRegistry:
    """Registry of all loaded constitutional resources."""

    policies: dict[str, PolicyResource] = field(default_factory=dict)
    patterns: dict[str, PatternResource] = field(default_factory=dict)
    principles: dict[str, ConstitutionalPrinciple] = field(default_factory=dict)

    # ID: a8e1f910-81f6-427d-9b6b-bf4b3801a42f
    def get_policy(self, policy_id: str) -> PolicyResource | None:
        """
        Retrieve a policy by ID.

        Args:
            policy_id: Policy identifier

        Returns:
            PolicyResource if found, None otherwise
        """
        return self.policies.get(policy_id)

    # ID: f05bf3d3-0ac1-4a50-b45b-2a15756a9e67
    def get_pattern(self, pattern_id: str) -> PatternResource | None:
        """
        Retrieve a pattern by ID.

        Args:
            pattern_id: Pattern identifier

        Returns:
            PatternResource if found, None otherwise
        """
        return self.patterns.get(pattern_id)

    # ID: fce8c3c9-b145-4c3a-b016-789b4d32cc73
    def get_principle(self, principle_id: str) -> ConstitutionalPrinciple | None:
        """
        Retrieve a principle by ID.

        Args:
            principle_id: Principle identifier

        Returns:
            ConstitutionalPrinciple if found, None otherwise
        """
        return self.principles.get(principle_id)

    # ID: a1f1541e-183d-4a51-b9f7-69f8ea31917b
    def list_policies(self) -> list[str]:
        """Get list of all loaded policy IDs."""
        return list(self.policies.keys())

    # ID: 5d2975b8-514d-4e03-8ae6-fa5783ac8488
    def list_patterns(self) -> list[str]:
        """Get list of all loaded pattern IDs."""
        return list(self.patterns.keys())

    # ID: 5ebcda9a-62ff-4d16-8406-05af44a22b5a
    def list_principles(self) -> list[str]:
        """Get list of all loaded principle IDs."""
        return list(self.principles.keys())
