# src/will/orchestration/intent_guard.py

"""
IntentGuard — CORE's Constitutional Enforcement Module
Enforces safety, structure, and intent alignment for all file changes.
Loads governance rules from .intent/policies/*.yaml and prevents unauthorized
self-modifications of the CORE constitution.

Updated to enforce Policy Precedence (Medium #2).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.config_loader import load_yaml_file
from shared.logger import getLogger

logger = getLogger(__name__)


@dataclass
# ID: a986a205-2e20-4feb-8926-69177de51d5f
class PolicyRule:
    """Structured representation of a policy rule."""

    name: str
    pattern: str
    action: str
    description: str
    severity: str = "error"
    source_policy: str = "unknown"

    @classmethod
    # ID: bdfca32e-ad2e-449e-87e2-c3aa76f4335d
    def from_dict(cls, data: dict, source: str = "unknown") -> PolicyRule:
        """Create PolicyRule from dictionary data."""
        return cls(
            name=data.get("name") or data.get("id") or "unnamed",
            pattern=data.get("pattern", ""),
            action=data.get("action", "deny"),
            description=data.get("description") or data.get("statement") or "",
            severity=data.get("severity") or data.get("enforcement") or "error",
            source_policy=source,
        )


@dataclass
# ID: 042e36e7-f168-4fb4-8c0d-665d669d9e4d
class ViolationReport:
    """Detailed violation report with context."""

    rule_name: str
    path: str
    message: str
    severity: str
    suggested_fix: str | None = None
    source_policy: str | None = None


# ID: bd28b7bc-8ff5-4c58-b1e8-78fbccd61e73
class ConstitutionalViolationError(Exception):
    """Raised when code generation violates constitutional policies."""

    pass


# ID: 8be64ae4-477d-4166-b7bf-bbb7a77a4c6c
class IntentGuard:
    """
    Central enforcement engine for CORE's safety and governance policies.
    Respects constitutional precedence rules.
    """

    def __init__(self, repo_path: Path):
        """Initialize IntentGuard with repository path and load all policies."""
        self.repo_path = Path(repo_path).resolve()
        self.intent_path = self.repo_path / ".intent"
        self.proposals_path = self.intent_path / "proposals"
        self.policies_path = self.intent_path / "charter" / "policies"

        # Load precedence hierarchy first
        self.precedence_map = self._load_precedence_rules()

        self.rules: list[PolicyRule] = []
        self._load_policies()

        # Sort rules by precedence (Level 1 is highest priority / lowest integer)
        # We default to 999 for unknown policies so they are checked last
        self.rules.sort(key=lambda r: self.precedence_map.get(r.source_policy, 999))

        logger.info(
            f"IntentGuard initialized with {len(self.rules)} rules (sorted by precedence)."
        )

    def _load_precedence_rules(self) -> dict[str, int]:
        """
        Load precedence rules from .intent/charter/constitution/precedence_rules.yaml
        Returns:
            dict: Map of policy_name -> level (e.g., {'safety_framework': 1})
        """
        mapping = {}
        try:
            path = (
                self.intent_path / "charter" / "constitution" / "precedence_rules.yaml"
            )
            if not path.exists():
                logger.warning("Precedence rules not found at %s", path)
                return mapping

            data = load_yaml_file(path)
            hierarchy = data.get("policy_hierarchy", [])

            for entry in hierarchy:
                level = entry.get("level", 999)
                if "policy" in entry:
                    name = entry["policy"].replace(".yaml", "")
                    mapping[name] = level
                if "policies" in entry:
                    for p in entry["policies"]:
                        name = p.replace(".yaml", "")
                        mapping[name] = level

            return mapping
        except Exception as e:
            logger.error("Failed to load precedence rules: %s", e)
            return {}

    def _load_policies(self):
        """Load rules from all YAML files in the `.intent/charter/policies/` directory."""
        if not self.policies_path.is_dir():
            logger.warning(f"Policies directory not found: {self.policies_path}")
            return
        for policy_file in self.policies_path.glob("*.yaml"):
            policy_name = policy_file.stem
            try:
                content = load_yaml_file(policy_file)

                # Handle standard "rules" list
                if (
                    content
                    and "rules" in content
                    and isinstance(content["rules"], list)
                ):
                    for rule_data in content["rules"]:
                        if isinstance(rule_data, dict):
                            self.rules.append(
                                PolicyRule.from_dict(rule_data, source=policy_name)
                            )

                # Handle "safety_rules" (safety_framework.yaml)
                if (
                    content
                    and "safety_rules" in content
                    and isinstance(content["safety_rules"], list)
                ):
                    for rule_data in content["safety_rules"]:
                        if isinstance(rule_data, dict):
                            self.rules.append(
                                PolicyRule.from_dict(rule_data, source=policy_name)
                            )

                # Handle "agent_rules" (agent_governance.yaml)
                if (
                    content
                    and "agent_rules" in content
                    and isinstance(content["agent_rules"], list)
                ):
                    for rule_data in content["agent_rules"]:
                        if isinstance(rule_data, dict):
                            self.rules.append(
                                PolicyRule.from_dict(rule_data, source=policy_name)
                            )

            except Exception as e:
                logger.error("Failed to load policy file {policy_file}: %s", e)

    # ID: ed5b3736-dd99-4f36-bae6-43f44eb1390c
    def check_transaction(
        self, proposed_paths: list[str]
    ) -> tuple[bool, list[ViolationReport]]:
        """
        Check if a proposed set of file changes complies with all active rules.

        Returns:
            tuple[bool, list[ViolationReport]]: (is_valid, violations)
            - is_valid: True ONLY if no violations found
            - violations: List of violation reports (empty if valid)
        """
        violations = []
        for path_str in proposed_paths:
            path = (self.repo_path / path_str).resolve()
            violations.extend(self._check_single_path(path, path_str))
        is_valid = len(violations) == 0
        return (is_valid, violations)

    # ID: 7fc7c3b5-5eb2-4ead-90c6-03c36f08b3d5
    async def validate_generated_code(
        self,
        code: str,
        pattern_id: str,
        component_type: str,
        target_path: str,
    ) -> tuple[bool, list[ViolationReport]]:
        """
        Validate generated code against pattern requirements.
        """
        violations = []

        # Pattern-specific validation
        if pattern_id == "inspect_pattern":
            violations.extend(self._validate_inspect_pattern(code, target_path))
        elif pattern_id == "action_pattern":
            violations.extend(self._validate_action_pattern(code, target_path))
        elif pattern_id == "check_pattern":
            violations.extend(self._validate_check_pattern(code, target_path))
        elif pattern_id == "run_pattern":
            violations.extend(self._validate_run_pattern(code, target_path))

        # Constitutional checks for the target path
        path_violations = self._check_single_path(
            self.repo_path / target_path, target_path
        )
        violations.extend(path_violations)

        is_valid = len(violations) == 0
        return (is_valid, violations)

    def _validate_inspect_pattern(
        self, code: str, target_path: str
    ) -> list[ViolationReport]:
        """Validate inspect pattern: READ-ONLY, no state modification."""
        violations = []
        forbidden_params = [
            "--write",
            "--apply",
            "--force",
            "write:",
            "apply:",
            "force:",
        ]
        for param in forbidden_params:
            if param in code:
                violations.append(
                    ViolationReport(
                        rule_name="inspect_pattern_violation",
                        path=target_path,
                        message=f"Inspect pattern violation: Found forbidden parameter '{param}'. Inspect commands must be read-only.",
                        severity="error",
                        suggested_fix=f"Remove '{param}' parameter - inspect commands cannot modify state.",
                        source_policy="pattern_vectorization",
                    )
                )
        return violations

    def _validate_action_pattern(
        self, code: str, target_path: str
    ) -> list[ViolationReport]:
        """Validate action pattern: Must have write parameter, default to False."""
        violations = []
        if "write:" not in code and "write =" not in code:
            violations.append(
                ViolationReport(
                    rule_name="action_pattern_violation",
                    path=target_path,
                    message="Action pattern violation: Missing required 'write' parameter.",
                    severity="error",
                    suggested_fix="Add 'write: bool = False' parameter to command.",
                    source_policy="pattern_vectorization",
                )
            )
        if "write: bool = True" in code or "write=True" in code:
            violations.append(
                ViolationReport(
                    rule_name="action_pattern_violation",
                    path=target_path,
                    message="Action pattern violation: write parameter must default to False.",
                    severity="error",
                    suggested_fix="Change to 'write: bool = False'.",
                    source_policy="pattern_vectorization",
                )
            )
        return violations

    def _validate_check_pattern(
        self, code: str, target_path: str
    ) -> list[ViolationReport]:
        """Validate check pattern: Validation only, no modification."""
        violations = []
        if "write:" in code or "apply:" in code:
            violations.append(
                ViolationReport(
                    rule_name="check_pattern_violation",
                    path=target_path,
                    message="Check pattern violation: Check commands must not modify state.",
                    severity="error",
                    suggested_fix="Remove write/apply parameters.",
                    source_policy="pattern_vectorization",
                )
            )
        return violations

    def _validate_run_pattern(
        self, code: str, target_path: str
    ) -> list[ViolationReport]:
        """Validate run pattern: Autonomous operations with safety controls."""
        violations = []
        if "write:" not in code and "write =" not in code:
            violations.append(
                ViolationReport(
                    rule_name="run_pattern_violation",
                    path=target_path,
                    message="Run pattern violation: Missing required 'write' parameter.",
                    severity="error",
                    suggested_fix="Add 'write: bool = False' parameter.",
                    source_policy="pattern_vectorization",
                )
            )
        return violations

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
                return ViolationReport(
                    rule_name="immutable_charter",
                    path=path_str,
                    message=f"Direct write to '{path_str}' is forbidden. Changes to the Charter require a formal proposal.",
                    severity="error",
                    source_policy="safety_framework",
                )
        except Exception as e:
            logger.error(
                "Error checking constitutional integrity for {path_str}: %s", e
            )
        return None

    def _check_policy_rules(self, path: Path, path_str: str) -> list[ViolationReport]:
        """Check path against all loaded policy rules."""
        violations = []
        for rule in self.rules:
            try:
                if self._matches_pattern(path_str, rule.pattern):
                    violations.extend(self._apply_rule_action(rule, path_str))
            except Exception as e:
                logger.error("Error applying rule '{rule.name}' to {path_str}: %s", e)
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
                    source_policy=rule.source_policy,
                )
            ]
        elif rule.action == "warn":
            logger.warning("Policy warning for %s: {rule.description}", path_str)
        return []

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if a path matches a given glob pattern."""
        # Add simple glob matching if needed, or use Path.match
        if not pattern:
            return False
        return Path(path).match(pattern)
