# src/mind/governance/governance_query.py

"""
Governance Query Interface - Mind Layer

CONSTITUTIONAL COMPLIANCE: Pure query interface over .intent/ documents

This module provides Mind layer's constitutional role: reading and querying
governance documents WITHOUT executing any decision logic.

Constitutional Design:
- Mind defines law but never executes
- Pure query interface (no risk classification, no decision-making)
- Returns structured data for Body/Will layers to use
- No caching, no execution logic, no I/O operations

Migration Notes:
- Replaces execution logic from risk_classifier.py
- Mind now only loads and queries .intent/ documents
- All execution logic moved to Body layer (risk_classification_service.py)
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import yaml

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: class-governance-query
# ID: a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d
class GovernanceQuery:
    """
    Mind layer query interface for constitutional documents.

    CONSTITUTIONAL ROLE:
    - Load .intent/ governance documents
    - Provide query interface to governance rules
    - Return raw data structures (no interpretation)
    - NO execution logic (that belongs in Body layer)

    This is a pure data access layer. It loads YAML/JSON files
    and returns their contents. It does NOT make decisions.
    """

    def __init__(self, intent_path: Path):
        """
        Initialize governance query interface.

        Args:
            intent_path: Path to .intent/ directory
        """
        self.intent_path = intent_path
        self._constitution_cache: dict[str, Any] | None = None

    # ID: 7ebcb861-479d-4593-96ee-8a6cf7b15a9a
    def load_constitution(self) -> dict[str, Any]:
        """
        Load constitutional documents from .intent/ directory.

        This method simply reads YAML files and returns their parsed content.
        It does NOT interpret or execute any governance logic.

        Returns:
            Dictionary containing constitutional rules and principles
        """
        if self._constitution_cache is not None:
            return self._constitution_cache

        constitution: dict[str, Any] = {
            "authority": {},
            "boundaries": {},
            "risk": {},
            "policies": {},
        }

        # Load authority principles
        authority_path = self.intent_path / "constitution" / "authority.yaml"
        if authority_path.exists():
            with open(authority_path) as f:
                constitution["authority"] = yaml.safe_load(f) or {}

        # Load boundary definitions
        boundaries_path = self.intent_path / "constitution" / "boundaries.yaml"
        if boundaries_path.exists():
            with open(boundaries_path) as f:
                constitution["boundaries"] = yaml.safe_load(f) or {}

        # Load risk tier definitions
        risk_path = self.intent_path / "constitution" / "risk.yaml"
        if risk_path.exists():
            with open(risk_path) as f:
                constitution["risk"] = yaml.safe_load(f) or {}

        # Load policy rules
        policies_path = self.intent_path / "rules"
        if policies_path.exists():
            for policy_file in policies_path.rglob("*.yaml"):
                with open(policy_file) as f:
                    policy_data = yaml.safe_load(f)
                    if policy_data:
                        policy_name = policy_file.stem
                        constitution["policies"][policy_name] = policy_data

        self._constitution_cache = constitution
        logger.info("Loaded constitutional documents from %s", self.intent_path)

        return constitution

    # ID: 32c67958-27bb-4e46-b9fd-e3299a9d1244
    def get_authority_principles(self) -> dict[str, Any]:
        """
        Query authority principles from constitution.

        Returns:
            Dictionary of authority principles (raw data from .intent/)
        """
        constitution = self.load_constitution()
        return constitution.get("authority", {}).get("principles", {})

    # ID: e507263b-d161-4ce2-a73f-4b2d9d514c48
    def get_boundary_rules(self) -> dict[str, Any]:
        """
        Query boundary rules from constitution.

        Returns:
            Dictionary of boundary rules (raw data from .intent/)
        """
        constitution = self.load_constitution()
        return constitution.get("boundaries", {}).get("principles", {})

    # ID: c353174f-f208-4bb1-b810-bcc4ffa3339a
    def get_risk_definitions(self) -> dict[str, Any]:
        """
        Query risk tier definitions from constitution.

        Returns:
            Dictionary of risk definitions (raw data from .intent/)
        """
        constitution = self.load_constitution()
        return constitution.get("risk", {}).get("principles", {})

    # ID: 23f6a85d-f170-4f3e-9ae3-99e4d5a5f828
    def get_policy_rules(self, policy_name: str | None = None) -> dict[str, Any]:
        """
        Query policy rules from constitution.

        Args:
            policy_name: Optional specific policy to query

        Returns:
            Dictionary of policy rules (raw data from .intent/)
        """
        constitution = self.load_constitution()
        policies = constitution.get("policies", {})

        if policy_name:
            return policies.get(policy_name, {})

        return policies

    # ID: 51e071a6-92d4-47a4-a8e2-29a83d7fa598
    def invalidate_cache(self) -> None:
        """
        Invalidate cached constitution data.

        Call this if .intent/ documents are updated and need to be reloaded.
        """
        self._constitution_cache = None
        logger.info("Invalidated constitution cache")


# ID: get-governance-query
# ID: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
def get_governance_query(intent_path: Path | None = None) -> GovernanceQuery:
    """
    Factory function for governance query interface.

    Args:
        intent_path: Optional path to .intent/ directory (defaults to .intent/)

    Returns:
        GovernanceQuery instance

    Usage:
        # Mind layer: Query governance rules
        query = get_governance_query()
        constitution = query.load_constitution()

        # Body layer: Use constitution for execution
        from body.governance.risk_classification_service import RiskClassificationService
        risk_service = RiskClassificationService(constitution)
        decision = risk_service.can_execute_autonomously("src/test.py", "edit")
    """
    if intent_path is None:
        intent_path = Path(".intent")

    return GovernanceQuery(intent_path)
