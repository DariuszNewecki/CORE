# src/will/orchestration/intent_guard.py
# ID: orchestration.intent_guard

"""
IntentGuard — CORE's Constitutional Enforcement Module

ONE JOB ONLY:
- Enforce governance decisions on proposed changes (allow/deny + violations)

NON-JOBS (explicitly forbidden here):
- Crawling `.intent`
- Parsing YAML/JSON directly
- Loading precedence rules directly
- Reading emergency override content directly

All `.intent` reads MUST go through:
- src/shared/infrastructure/intent/intent_repository.py (IntentRepository)
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from shared.config import settings
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.logger import getLogger


logger = getLogger(__name__)


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
    def from_dict(cls, data: dict[str, Any], source: str = "unknown") -> PolicyRule:
        return cls(
            name=str(data.get("name") or data.get("id") or "unnamed"),
            pattern=str(data.get("pattern") or ""),
            action=str(data.get("action") or "deny"),
            description=str(data.get("description") or data.get("statement") or ""),
            severity=str(data.get("severity") or data.get("enforcement") or "error"),
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


# ID: af558ebb-97bd-4b81-9de2-740acdfc3b1a
class IntentGuard:
    """
    Enforcement-only engine.

    Governance inputs MUST be provided by IntentRepository:
    - precedence map
    - flattened policy rules

    Emergency override is existence-only here.
    """

    _EMERGENCY_LOCK_REL = ".intent/mind/.emergency_override"

    def __init__(self, repo_path: Path):
        self.repo_path = Path(repo_path).resolve()

        # Paths used only for boundary checks / anchoring (no crawling)
        self.intent_path = settings.paths.intent_root
        self.proposals_path = settings.paths.proposals_dir
        self.charter_dir = getattr(
            settings.paths, "charter_dir", (self.intent_path / "charter")
        )

        # Emergency override: existence-only check (no file read here)
        self.emergency_lock_file = (self.repo_path / self._EMERGENCY_LOCK_REL).resolve()

        # Governance inputs (repo owns IO/parsing/indexing)
        repo = get_intent_repository()
        self.precedence_map = repo.get_precedence_map()

        # repo.list_policy_rules() returns dict wrappers:
        # {"policy_name": str, "section": str, "rule": dict}
        raw_rules = repo.list_policy_rules()
        self.rules: list[PolicyRule] = []
        for entry in raw_rules:
            if not isinstance(entry, dict):
                continue
            policy_name = entry.get("policy_name") or "unknown"
            rule_dict = entry.get("rule")
            if isinstance(rule_dict, dict):
                self.rules.append(
                    PolicyRule.from_dict(rule_dict, source=str(policy_name))
                )

        # Apply precedence (lower number = higher priority)
        self.rules.sort(key=lambda r: self.precedence_map.get(r.source_policy, 999))

        logger.info("IntentGuard initialized with %s rules.", len(self.rules))

    # -------------------------------------------------------------------------
    # Public API
    # -------------------------------------------------------------------------

    # ID: b4d5c82c-d19f-4026-89a3-13ee3ffb200e
    def check_transaction(
        self, proposed_paths: list[str]
    ) -> tuple[bool, list[ViolationReport]]:
        if self._is_emergency_mode():
            logger.critical(
                "INTENT GUARD BYPASSED (EMERGENCY MODE). Allowing access to: %s",
                proposed_paths,
            )
            return (True, [])

        violations: list[ViolationReport] = []
        for path_str in proposed_paths:
            abs_path = (self.repo_path / path_str).resolve()
            violations.extend(self._check_single_path(abs_path, path_str))
        return (len(violations) == 0, violations)

    # ID: 86791f7d-277d-4c89-82b0-b1a29471a60d
    async def validate_generated_code(
        self, code: str, pattern_id: str, component_type: str, target_path: str
    ) -> tuple[bool, list[ViolationReport]]:
        # component_type kept for compatibility
        if self._is_emergency_mode():
            logger.critical(
                "CODE VALIDATION BYPASSED (EMERGENCY MODE). Target: %s",
                target_path,
            )
            return (True, [])

        violations: list[ViolationReport] = []

        if pattern_id == "inspect_pattern":
            violations.extend(self._validate_inspect_pattern(code, target_path))
        elif pattern_id == "action_pattern":
            violations.extend(self._validate_action_pattern(code, target_path))
        elif pattern_id == "check_pattern":
            violations.extend(self._validate_check_pattern(code, target_path))
        elif pattern_id == "run_pattern":
            violations.extend(self._validate_run_pattern(code, target_path))

        violations.extend(
            self._check_single_path(self.repo_path / target_path, target_path)
        )
        return (len(violations) == 0, violations)

    # -------------------------------------------------------------------------
    # Emergency mode (existence-only)
    # -------------------------------------------------------------------------

    def _is_emergency_mode(self) -> bool:
        return self.emergency_lock_file.exists()

    # -------------------------------------------------------------------------
    # Pattern validators (unchanged semantics)
    # -------------------------------------------------------------------------

    def _validate_inspect_pattern(
        self, code: str, target_path: str
    ) -> list[ViolationReport]:
        violations: list[ViolationReport] = []
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
                        message=(
                            f"Inspect pattern violation: Found forbidden parameter '{param}'. "
                            "Inspect commands must be read-only."
                        ),
                        severity="error",
                        suggested_fix=(
                            f"Remove '{param}' parameter - inspect commands cannot modify state."
                        ),
                        source_policy="pattern_vectorization",
                    )
                )
        return violations

    def _validate_action_pattern(
        self, code: str, target_path: str
    ) -> list[ViolationReport]:
        violations: list[ViolationReport] = []
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
        violations: list[ViolationReport] = []
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
        violations: list[ViolationReport] = []
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

    # -------------------------------------------------------------------------
    # Enforcement core
    # -------------------------------------------------------------------------

    def _check_single_path(self, path: Path, path_str: str) -> list[ViolationReport]:
        violations: list[ViolationReport] = []
        constitutional_violation = self._check_constitutional_integrity(path, path_str)
        if constitutional_violation:
            violations.append(constitutional_violation)
        violations.extend(self._check_policy_rules(path_str))
        return violations

    def _check_constitutional_integrity(
        self, path: Path, path_str: str
    ) -> ViolationReport | None:
        try:
            charter_root = Path(self.charter_dir).resolve()
            if charter_root in path.parents or path == charter_root:
                return ViolationReport(
                    rule_name="immutable_charter",
                    path=path_str,
                    message=(
                        f"Direct write to '{path_str}' is forbidden. "
                        "Changes to the Charter require a formal proposal."
                    ),
                    severity="error",
                    source_policy="safety_framework",
                )
        except Exception as e:
            logger.error(
                "Error checking constitutional integrity for %s: %s", path_str, e
            )
        return None

    def _check_policy_rules(self, path_str: str) -> list[ViolationReport]:
        violations: list[ViolationReport] = []
        for rule in self.rules:
            try:
                if self._matches_pattern(path_str, rule.pattern):
                    violations.extend(self._apply_rule_action(rule, path_str))
            except Exception as e:
                logger.error(
                    "Error applying rule '%s' to %s: %s", rule.name, path_str, e
                )
        return violations

    def _apply_rule_action(
        self, rule: PolicyRule, path_str: str
    ) -> list[ViolationReport]:
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
        if rule.action == "warn":
            logger.warning("Policy warning for %s: %s", path_str, rule.description)
        return []

    def _matches_pattern(self, path: str, pattern: str) -> bool:
        if not pattern:
            return False
        return Path(path).match(pattern)
