# src/will/orchestration/intent_guard.py
# ID: orchestration.intent_guard
"""
IntentGuard — CORE's Constitutional Enforcement Module
Enforces safety, structure, and intent alignment for all file changes.
Loads governance rules from .intent/policies/*.yaml and prevents unauthorized
self-modifications of the CORE constitution.

Updated to enforce Policy Precedence (Medium #2) and Emergency Override (Crate 4).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.config import settings
from shared.config_loader import load_yaml_file
from shared.logger import getLogger


logger = getLogger(__name__)

# This file indicates the system is in Emergency Mode (Break Glass Protocol)
EMERGENCY_LOCK_FILE = Path(".intent/mind/.emergency_override")


@dataclass
# ID: 7ae2a59e-e1f5-4b75-9969-71be1ccbec6a
class PolicyRule:
    """Structured representation of a policy rule."""

    name: str
    pattern: str
    action: str
    description: str
    severity: str = "error"
    source_policy: str = "unknown"

    @classmethod
    # ID: d66ce31f-9efe-4c1d-a127-6a51699df421
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
# ID: aa955039-69d6-4766-bbdb-8fdf4ff625ee
class ViolationReport:
    """Detailed violation report with context."""

    rule_name: str
    path: str
    message: str
    severity: str
    suggested_fix: str | None = None
    source_policy: str | None = None


# ID: 61fd7791-1b1c-4e83-ae8d-4ef686d2281a
class ConstitutionalViolationError(Exception):
    """Raised when code generation violates constitutional policies."""

    pass


# ID: af558ebb-97bd-4b81-9de2-740acdfc3b1a
class IntentGuard:
    """
    Central enforcement engine for CORE's safety and governance policies.
    Respects constitutional precedence rules.
    """

    def __init__(self, repo_path: Path):
        """Initialize IntentGuard with repository path and load all policies."""
        self.repo_path = Path(repo_path).resolve()
        #        self.intent_path = self.repo_path / ".intent"
        self.intent_path = settings.paths.intent_root
        self.proposals_path = settings.paths.proposals_dir
        self.policies_path = settings.paths.policies_dir
        self.precedence_map = self._load_precedence_rules()
        self.rules: list[PolicyRule] = []
        self._load_policies()
        self.rules.sort(key=lambda r: self.precedence_map.get(r.source_policy, 999))
        logger.info(
            "IntentGuard initialized with %s rules (sorted by precedence).",
            len(self.rules),
        )

    def _load_precedence_rules(self) -> dict[str, int]:
        """
        Load precedence rules from .intent/charter/constitution/precedence_rules.yaml
        Returns:
            dict: Map of policy_name -> level (e.g., {'safety_framework': 1})
        """
        mapping = {}
        try:
            path = settings.paths.constitution_dir / "precedence_rules.yaml"
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
            logger.warning("Policies directory not found: %s", self.policies_path)
            return
        for policy_file in self.policies_path.rglob("*.yaml"):
            policy_name = policy_file.stem
            try:
                content = load_yaml_file(policy_file)
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

    # ID: b4d5c82c-d19f-4026-89a3-13ee3ffb200e
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
        # --- EMERGENCY OVERRIDE CHECK ---
        if EMERGENCY_LOCK_FILE.exists():
            reason = "Unknown"
            try:
                content = EMERGENCY_LOCK_FILE.read_text().strip()
                if "|" in content:
                    _, reason = content.split("|", 1)
            except Exception:
                pass

            logger.critical(
                "INTENT GUARD BYPASSED (EMERGENCY MODE). Reason: %s. Allowing access to: %s",
                reason,
                proposed_paths,
            )
            # In emergency mode, we return Valid with NO violations.
            return (True, [])
        # --------------------------------

        violations = []
        for path_str in proposed_paths:
            path = (self.repo_path / path_str).resolve()
            violations.extend(self._check_single_path(path, path_str))
        is_valid = len(violations) == 0
        return (is_valid, violations)

    # ID: 86791f7d-277d-4c89-82b0-b1a29471a60d
    async def validate_generated_code(
        self, code: str, pattern_id: str, component_type: str, target_path: str
    ) -> tuple[bool, list[ViolationReport]]:
        """
        Validate generated code against pattern requirements.
        """
        # --- EMERGENCY OVERRIDE CHECK ---
        if EMERGENCY_LOCK_FILE.exists():
            logger.critical(
                "CODE VALIDATION BYPASSED (EMERGENCY MODE). Target: %s", target_path
            )
            return (True, [])
        # --------------------------------

        violations = []
        if pattern_id == "inspect_pattern":
            violations.extend(self._validate_inspect_pattern(code, target_path))
        elif pattern_id == "action_pattern":
            violations.extend(self._validate_action_pattern(code, target_path))
        elif pattern_id == "check_pattern":
            violations.extend(self._validate_check_pattern(code, target_path))
        elif pattern_id == "run_pattern":
            violations.extend(self._validate_run_pattern(code, target_path))
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
        if not pattern:
            return False
        return Path(path).match(pattern)
