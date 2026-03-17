# src/shared/infrastructure/intent/intent_connector.py

"""Provides functionality for the intent_connector module."""

from __future__ import annotations

import fnmatch
import logging
from pathlib import Path
from typing import Any

from shared.infrastructure.intent.intent_repository import (
    GovernanceError,
    get_intent_repository,
)


logger = logging.getLogger(__name__)


# ID: 106da0b1-1db4-4d4e-9a44-2f71833d72a9
class IntentConnector:
    """
    Compatibility wrapper over IntentRepository with Context-Aware filtering.
    Designed to work in both long-running services and standalone scripts.
    """

    def __init__(self):
        # Fact: standalone scripts run 'cold'. We must ensure index is built.
        self._ensure_repo_ready()

    def _ensure_repo_ready(self):
        """Ensures the underlying repository has scanned the .intent directory."""
        repo = get_intent_repository()
        # If the index is None, it means the repository has not been initialized.
        if getattr(repo, "_rule_index", None) is None:
            try:
                # CORE convention: initialize() triggers discovery of rules
                if hasattr(repo, "initialize"):
                    repo.initialize()
                else:
                    # Fallback for older versions of repository
                    logger.warning(
                        "IntentRepository index is None. Ensure .intent folder exists."
                    )
            except Exception as e:
                raise GovernanceError(f"Failed to initialize IntentRepository: {e}")

    # ID: 0caa13c6-1e1c-4a56-a776-1304f9515781
    def get_rule(self, rule_id: str) -> dict[str, Any]:
        """Retrieves a single rule and enriches it with policy context."""
        self._ensure_repo_ready()
        ref = get_intent_repository().get_rule(rule_id)
        return {
            **ref.content,
            "_policy_id": ref.policy_id,
            "_source": str(ref.source_path),
        }

    # ID: e25f7d07-b3ba-4233-96c7-96f7541a3931
    def get_policy(self, policy_name: str) -> dict[str, Any]:
        """Retrieves a full policy file by its canonical path/id."""
        if "/" not in policy_name:
            raise GovernanceError(
                f"Ambiguous policy identifier '{policy_name}'. "
                f"Use canonical policy_id like 'policies/<category>/<name>'."
            )
        return get_intent_repository().load_policy(policy_name)

    # ID: d5a2b3c4-e5f6-4789-8c1d-6e5f4a3b2c1d
    def get_applicable_rules(self, file_path: Path) -> list[dict[str, Any]]:
        """
        Retrieve all rules from the Constitution that apply to a specific file.
        Filters based on 'scope' metadata defined in rules or policies.
        """
        self._ensure_repo_ready()
        repo = get_intent_repository()

        if repo._rule_index is None:
            return []

        applicable = []
        target_path = str(file_path).replace("\\", "/")

        for ref in repo._rule_index.values():
            rule_content = ref.content

            scope = rule_content.get("scope")

            if not scope:
                policy = repo.load_policy(ref.policy_id)
                scope = policy.get("scope", {}).get("paths") or policy.get("scope")

            if not scope or self._path_matches_scope(target_path, scope):
                applicable.append(self.get_rule(ref.rule_id))

        return applicable

    # ID: f5a6b1c2-d3e4-4789-8c1d-6e5f4a3b2c1d
    def _path_matches_scope(self, path: str, scope: str | list[str]) -> bool:
        """Helper to evaluate if a path falls within a constitutional scope."""
        if not scope:
            return True

        patterns = [scope] if isinstance(scope, str) else scope

        for pattern in patterns:
            if "**" in pattern:
                prefix = pattern.split("/**")[0]
                if not prefix or path.startswith(prefix):
                    return True
            if fnmatch.fnmatch(path, pattern):
                return True

        return False

    # ID: 48542cd3-e04e-4983-8072-732b6d10283a
    def list_governance_map(self) -> dict[str, list[str]]:
        """Returns the structural hierarchy of the Constitution."""
        return get_intent_repository().list_governance_map()

    # ID: c07fef88-79d0-46da-ac08-40b4a34462c0
    def get_rules_by_policy(self, policy_id: str) -> list[str]:
        """Lists all rule identifiers belonging to a specific policy."""
        self._ensure_repo_ready()
        repo = get_intent_repository()
        if not repo._rule_index:
            return []

        rule_ids = [
            rid for rid, ref in repo._rule_index.items() if ref.policy_id == policy_id
        ]
        return sorted(rule_ids)

    # ID: 2c7b8c3a-7b14-4d67-8f07-30f2f4a9d201
    def list_workflows(self) -> list[str]:
        """List workflow definitions from the constitutional repository."""
        self._ensure_repo_ready()
        return get_intent_repository().list_workflows()

    # ID: 0d17b52e-0ed3-4d87-a0d1-24bff7f8d202
    def load_workflow(self, workflow_id: str) -> dict[str, Any]:
        """Load a workflow definition from the constitutional repository."""
        self._ensure_repo_ready()
        return get_intent_repository().load_workflow(workflow_id)

    # ID: d4f9d4a2-08bb-41d3-92ec-8dba3f18d203
    def list_phases(self) -> list[str]:
        """List constitutional phase definitions from the constitutional repository."""
        self._ensure_repo_ready()
        return get_intent_repository().list_phases()

    # ID: e9bb6f9c-3f18-49db-8d40-f58d7d58d204
    def load_phase(self, phase_id: str) -> dict[str, Any]:
        """Load a constitutional phase definition from the constitutional repository."""
        self._ensure_repo_ready()
        return get_intent_repository().load_phase(phase_id)
