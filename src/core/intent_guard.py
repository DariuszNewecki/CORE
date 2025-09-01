# src/core/intent_guard.py
"""
IntentGuard — CORE's Constitutional Enforcement Module

Enforces safety, structure, and intent alignment for all file changes.
Loads governance rules from .intent/policies/*.yaml and prevents unauthorized
self-modifications of the CORE constitution.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Tuple

from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger(__name__)


# CAPABILITY: intent_guarding
class IntentGuard:
    """
    Central enforcement engine for CORE's safety and governance policies.
    Ensures all proposed file changes comply with declared rules and classifications.
    """

    # CAPABILITY: intent_guarding.initialize
    def __init__(self, repo_path: Path):
        """
        Initialize IntentGuard with repository path and load all policies.
        """
        self.repo_path = Path(repo_path).resolve()
        self.intent_path = self.repo_path / ".intent"
        self.proposals_path = self.intent_path / "proposals"
        self.policies_path = self.intent_path / "policies"
        self.rules: List[Dict] = []

        self._load_policies()
        self.source_code_manifest = self._load_source_manifest()

        log.info(
            f"IntentGuard initialized. {len(self.rules)} rules loaded. Watching {len(self.source_code_manifest)} source files."
        )

    # CAPABILITY: intent_guard.policies.load
    def _load_policies(self):
        """Load rules from all YAML files in the `.intent/policies/` directory."""
        if not self.policies_path.is_dir():
            return
        for policy_file in self.policies_path.glob("*.yaml"):
            content = load_config(policy_file, "yaml")
            if content and "rules" in content and isinstance(content["rules"], list):
                self.rules.extend(content["rules"])

    # CAPABILITY: core.intent_guard.load_source_manifest
    def _load_source_manifest(self) -> List[str]:
        """
        Load the list of all known source files from the knowledge graph.
        """
        manifest_file = self.intent_path / "knowledge" / "knowledge_graph.json"
        if not manifest_file.exists():
            return []
        try:
            manifest_data = json.loads(manifest_file.read_text(encoding="utf-8"))
            symbols = manifest_data.get("symbols", {})
            # Use a set to get unique file paths, then convert to a sorted list.
            unique_files = {
                entry.get("file") for entry in symbols.values() if entry.get("file")
            }
            return sorted(list(unique_files))
        except (json.JSONDecodeError, TypeError):
            return []

    # --- THIS IS THE FIX ---
    # The method now correctly resolves paths relative to the repository root.
    # CAPABILITY: intent_guard.check_transaction
    def check_transaction(self, proposed_paths: List[str]) -> Tuple[bool, List[str]]:
        """
        Check if a proposed set of file changes complies with all active rules.
        This is the primary enforcement point for constitutional integrity.
        """
        violations = []

        # Rule: Prevent direct writes to the .intent directory, except for proposals.
        for path_str in proposed_paths:
            # Resolve the path relative to the repository root, not the current working directory.
            # This makes the check robust regardless of where the script is executed from.
            path = (self.repo_path / path_str).resolve()

            # Check if the path is within the .intent directory
            if self.intent_path.resolve() in path.parents:
                # If it is, check if it's also within the allowed proposals directory
                if (
                    self.proposals_path.resolve() not in path.parents
                    and path.parent != self.proposals_path.resolve()
                ):
                    violations.append(
                        f"Rule Violation (immutable_intent): Direct write to '{path_str}' is forbidden. "
                        "All changes to the constitution must go through '.intent/proposals/'."
                    )

        # Placeholder for future, more sophisticated rule checks
        # for rule in self.rules:
        #    ...

        return not violations, violations
