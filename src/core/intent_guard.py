# src/core/intent_guard.py
"""
IntentGuard — CORE's Constitutional Enforcement Module
Enforces safety, structure, and intent alignment for all file changes.
Loads governance rules from .intent/policies/*.yaml and prevents unauthorized
self-modifications of the CORE constitution.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.config_loader import load_yaml_file
from shared.logger import getLogger

log = getLogger(__name__)


@dataclass
# ID: 1499a5c2-5fc6-4ea3-8049-21702aa20f6e
class PolicyRule:
    """Structured representation of a policy rule."""

    name: str
    pattern: str
    action: str
    description: str
    severity: str = "error"

    @classmethod
    # ID: db43791c-92bd-435e-8ade-85620f3cf4f6
    def from_dict(cls, data: dict) -> PolicyRule:
        """Create PolicyRule from dictionary data."""
        return cls(
            name=data.get("name", "unnamed"),
            pattern=data.get("pattern", ""),
            action=data.get("action", "deny"),
            description=data.get("description", ""),
            severity=data.get("severity", "error"),
        )


@dataclass
# ID: 8bdef506-b2b3-4b1e-9a11-96e8d79282b3
class ViolationReport:
    """Detailed violation report with context."""

    rule_name: str
    path: str
    message: str
    severity: str
    suggested_fix: str | None = None


# ID: 1f189a22-8497-44f9-af8e-00888b0eca0e
class IntentGuard:
    """
    Central enforcement engine for CORE's safety and governance policies.
    """

    def __init__(self, repo_path: Path):
        """Initialize IntentGuard with repository path and load all policies."""
        self.repo_path = Path(repo_path).resolve()
        self.intent_path = self.repo_path / ".intent"
        self.proposals_path = self.intent_path / "proposals"
        self.policies_path = self.intent_path / "charter" / "policies"

        self.rules: list[PolicyRule] = []
        self._load_policies()

        log.info(f"IntentGuard initialized with {len(self.rules)} rules loaded.")

    def _load_policies(self):
        """Load rules from all YAML files in the `.intent/charter/policies/` directory."""
        if not self.policies_path.is_dir():
            log.warning(f"Policies directory not found: {self.policies_path}")
            return

        for policy_file in self.policies_path.glob("*.yaml"):
            try:
                content = load_yaml_file(policy_file)
                if (
                    content
                    and "rules" in content
                    and isinstance(content["rules"], list)
                ):
                    for rule_data in content["rules"]:
                        if isinstance(rule_data, dict):
                            self.rules.append(PolicyRule.from_dict(rule_data))
            except Exception as e:
                log.error(f"Failed to load policy file {policy_file}: {e}")

    # ID: abd3b486-3aaa-4dee-8a99-2a0fbd8f1c28
    def check_transaction(
        self, proposed_paths: list[str]
    ) -> tuple[bool, list[ViolationReport]]:
        """
        Check if a proposed set of file changes complies with all active rules.
        """
        violations = []
        for path_str in proposed_paths:
            path = (self.repo_path / path_str).resolve()
            violations.extend(self._check_single_path(path, path_str))
        return len(violations) == 0, violations

    def _check_single_path(self, path: Path, path_str: str) -> list[ViolationReport]:
        """Check a single path against all rules."""
        violations = []
        constitutional_violation = self._check_constitutional_integrity(path, path_str)
        if constitutional_violation:
            violations.append(constitutional_violation)
        violations.extend(self._check_policy_rules(path, path_str))
        return violations

    def _check_constitutional_integrity(
        self, path: Path, path_str: str
    ) -> ViolationReport | None:
        """Check if the path violates constitutional immutability rules."""
        try:
            charter_path_resolved = (self.intent_path / "charter").resolve()
            if charter_path_resolved in path.parents or path == charter_path_resolved:
                return self._create_constitutional_violation(path_str)
        except Exception as e:
            log.error(f"Error checking constitutional integrity for {path_str}: {e}")
        return None

    def _create_constitutional_violation(self, path_str: str) -> ViolationReport:
        """Create a constitutional violation report."""
        return ViolationReport(
            rule_name="immutable_charter",
            path=path_str,
            message=f"Direct write to '{path_str}' is forbidden. Changes to the Charter require a formal proposal.",
            severity="error",
        )

    def _check_policy_rules(self, path: Path, path_str: str) -> list[ViolationReport]:
        """Check path against all loaded policy rules."""
        violations = []
        for rule in self.rules:
            try:
                if self._matches_pattern(path_str, rule.pattern):
                    violations.extend(self._apply_rule_action(rule, path_str))
            except Exception as e:
                log.error(f"Error applying rule '{rule.name}' to {path_str}: {e}")
        return violations

    def _apply_rule_action(
        self, rule: PolicyRule, path_str: str
    ) -> list[ViolationReport]:
        """Apply the action for a matched rule."""
        if rule.action == "deny":
            return [
                ViolationReport(
                    rule_name=rule.name,
                    path=path_str,
                    message=f"Rule '{rule.name}' violation: {rule.description}",
                    severity=rule.severity,
                )
            ]
        elif rule.action == "warn":
            log.warning(f"Policy warning for {path_str}: {rule.description}")
        return []

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a given glob pattern."""
        return Path(path).match(pattern)
