# src/features/governance/micro_proposal_validator.py
"""
Provides a centralized, single-source-of-truth validator for micro-proposal plans.
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from shared.config import settings
from shared.logger import getLogger
from shared.models import ExecutionTask

log = getLogger("micro_proposal_validator")


# ID: dd3a6e30-1762-4cd3-b7b5-dab8f43bed13
class MicroProposalValidator:
    """Validates an execution plan against the micro_proposal_policy."""

    def __init__(self):
        """Initializes the validator by loading the governing policy."""
        self.policy = settings.load("charter.policies.agent.micro_proposal_policy")
        rules = self.policy.get("rules", [])
        self.policy_rules = {rule.get("id"): rule for rule in rules}
        self.allowed_actions = set(
            self.policy_rules.get("safe_actions", {}).get("allowed_actions", [])
        )
        self.allowed_paths = self.policy_rules.get("safe_paths", {}).get(
            "allowed_paths", []
        )
        self.forbidden_paths = self.policy_rules.get("safe_paths", {}).get(
            "forbidden_paths", []
        )

    # ID: 4e5a2a40-6a66-478a-b9eb-b2af08edb161
    def validate(self, plan: List[ExecutionTask]) -> Tuple[bool, str]:
        """
        Validates the entire plan.

        Returns:
            A tuple (is_valid: bool, error_message: str).
        """
        for task in plan:
            # Validate action
            if task.action not in self.allowed_actions:
                return (
                    False,
                    f"Action '{task.action}' is not in the list of allowed safe actions.",
                )

            # Validate path
            file_path = Path(task.params.file_path)
            if self._is_path_forbidden(file_path):
                return (
                    False,
                    f"Path '{file_path}' is explicitly forbidden by the micro-proposal policy.",
                )

            if not self._is_path_allowed(file_path):
                return (
                    False,
                    f"Path '{file_path}' does not match any allowed path patterns in the micro-proposal policy.",
                )

        return True, ""

    def _is_path_forbidden(self, path: Path) -> bool:
        """Checks if a path matches any forbidden patterns."""
        if not self.forbidden_paths:
            return False
        for pattern in self.forbidden_paths:
            try:
                # Handle '**' correctly by checking parent directories
                if "**" in pattern:
                    base_dir_str = pattern.split("**")[0]
                    base_dir = (settings.REPO_PATH / base_dir_str).resolve()
                    if path.resolve().is_relative_to(base_dir):
                        return True
                if path.match(pattern):
                    return True
            except Exception:
                continue
        return False

    def _is_path_allowed(self, path: Path) -> bool:
        """Checks if a path matches any allowed patterns."""
        if not self.allowed_paths:
            return True  # If no allowed_paths are specified, all non-forbidden paths are implicitly allowed

        for pattern in self.allowed_paths:
            if path.match(pattern):
                return True
        return False
