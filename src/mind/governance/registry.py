# src/mind/governance/registry.py

"""Provides functionality for the registry module."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.logger import getLogger

from .schemas import PatternResource, PolicyResource, ResourceKind


logger = getLogger(__name__)


# ID: 32cd0603-a40d-4a95-beeb-a90deeaf5d0d
class GovernanceRegistry:
    """
    The Single Source of Truth for all constitutional resources.
    Loads, validates, and indexes policies and patterns.
    """

    def __init__(self, intent_root: Path):
        self.root = intent_root
        self._policies: dict[str, PolicyResource] = {}
        self._patterns: dict[str, PatternResource] = {}
        self._loaded = False

    # ID: 51c4830c-9fae-4dd7-b81e-76ff26b4d84f
    async def load(self):
        """Scans .intent and loads all valid KRM resources."""
        logger.info(f"Loading Governance Platform from {self.root}")

        # Recursive scan for .yaml files
        for path in self.root.rglob("*.yaml"):
            if "mind_export" in str(path):
                continue

            try:
                self._load_file(path)
            except Exception as e:
                logger.warning("Failed to load resource {path.name}: %s", e)

        self._loaded = True
        logger.info(
            f"Governance loaded: {len(self._policies)} Policies, {len(self._patterns)} Patterns"
        )

    def _load_file(self, path: Path):
        content = yaml.safe_load(path.read_text(encoding="utf-8"))

        if not isinstance(content, dict) or "kind" not in content:
            return  # Skip non-KRM files (legacy files)

        kind = content.get("kind")

        if kind == ResourceKind.POLICY:
            resource = PolicyResource(**content)
            self._policies[resource.metadata.id] = resource

        elif kind == ResourceKind.PATTERN:
            resource = PatternResource(**content)
            self._patterns[resource.metadata.id] = resource

        # Add Registry/Manifest handling here

    # ID: 6270193d-4d3f-4f00-891d-ec964048758a
    def get_policy(self, policy_id: str) -> PolicyResource:
        return self._policies.get(policy_id)

    # ID: ce451562-98d4-4262-9cb7-56a04d78c79a
    def get_all_rules(self) -> list[dict]:
        """Flattened list of all active rules for the auditor."""
        rules = []
        for policy in self._policies.values():
            if policy.metadata.status != "active":
                continue
            for rule in policy.spec.rules:
                rules.append({"policy_id": policy.metadata.id, **rule.model_dump()})
        return rules
