# src/mind/governance/registry.py

"""Provides functionality for the registry module."""

from __future__ import annotations

from pathlib import Path

import yaml

from shared.logger import getLogger

from .schemas import PatternResource, PolicyResource, ResourceKind


logger = getLogger(__name__)


# ID: 3c714e64-6ffe-4004-9f1b-1a1dab45dfbf
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

    # ID: 37050656-cd8e-48f2-85ad-78f694f2cdfe
    async def load(self):
        """Scans .intent and loads all valid KRM resources."""
        logger.info("Loading Governance Platform from %s", self.root)
        for path in self.root.rglob("*.yaml"):
            if "mind_export" in str(path):
                continue
            try:
                self._load_file(path)
            except Exception as e:
                logger.warning("Failed to load resource {path.name}: %s", e)
        self._loaded = True
        logger.info(
            "Governance loaded: %s Policies, %s Patterns",
            len(self._policies),
            len(self._patterns),
        )

    def _load_file(self, path: Path):
        content = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(content, dict) or "kind" not in content:
            return
        kind = content.get("kind")
        if kind == ResourceKind.POLICY:
            resource = PolicyResource(**content)
            self._policies[resource.metadata.id] = resource
        elif kind == ResourceKind.PATTERN:
            resource = PatternResource(**content)
            self._patterns[resource.metadata.id] = resource

    # ID: f8a5e1c6-0ffe-4d4e-a881-1d47172f9b9d
    def get_policy(self, policy_id: str) -> PolicyResource:
        return self._policies.get(policy_id)

    # ID: 49674e6c-206d-456f-abf3-c3789a53f48a
    def get_all_rules(self) -> list[dict]:
        """Flattened list of all active rules for the auditor."""
        rules = []
        for policy in self._policies.values():
            if policy.metadata.status != "active":
                continue
            for rule in policy.spec.rules:
                rules.append({"policy_id": policy.metadata.id, **rule.model_dump()})
        return rules
