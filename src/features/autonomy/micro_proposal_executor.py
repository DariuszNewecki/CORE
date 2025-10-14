# src/features/autonomy/micro_proposal_executor.py
"""
Service for validating and applying micro-proposals to enable safe, autonomous
changes to the CORE codebase, adhering to the micro_proposal_policy.yaml and
enforcing safe_by_default and reason_with_purpose principles.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from shared.logger import getLogger
from shared.models import CheckResult
from shared.path_utils import get_repo_root
from shared.utils.yaml_processor import strict_yaml_processor

log = getLogger("micro_proposal_executor")


@dataclass
# ID: 5b337f4b-e1c5-43f2-a26e-17bc7ceee474
class MicroProposal:
    """Internal data structure for a micro-proposal with target file, action, and content."""

    file_path: str
    action: str
    content: str
    validation_report_id: str | None = None


# ID: 9f3a2e7b-5c4d-4b9e-a2f0-8d7a9e3d6e2c
class MicroProposalExecutor:
    """
    Validates and applies micro-proposals for safe, autonomous changes as defined
    by micro_proposal_policy.yaml, ensuring compliance with safe_by_default and
    reason_with_purpose principles.
    """

    def __init__(self, repo_root: Path | None = None) -> None:
        """
        Initialize the executor with the repository root and load the policy.

        Args:
            repo_root: Path to the repository root, defaults to detected root.
        """
        self.repo_root = repo_root or get_repo_root()
        self.policy_path = (
            self.repo_root / ".intent/charter/policies/agent/micro_proposal_policy.yaml"
        )
        self.policy = self._load_policy()
        log.debug("MicroProposalExecutor initialized")

    def _load_policy(self) -> dict:
        """
        Load and validate the micro_proposal_policy.yaml.

        Returns:
            Dict: The parsed policy content.

        Raises:
            ValueError: If the policy file is missing or invalid.
        """
        try:
            policy = strict_yaml_processor.load_strict(self.policy_path)
            if not policy:
                raise ValueError("Micro-proposal policy is empty or invalid")
            return policy
        except ValueError as e:
            log.error(f"Failed to load micro-proposal policy: {e}")
            raise

    def _check_safe_actions(self, action: str) -> CheckResult:
        """
        Verify if the action is in the allowed_actions list.

        Args:
            action: The action to validate.

        Returns:
            CheckResult: Result of the safe actions check.
        """
        safe_actions_rule = next(
            (rule for rule in self.policy["rules"] if rule["id"] == "safe_actions"),
            None,
        )
        if not safe_actions_rule:
            return CheckResult(
                policy_id=self.policy["policy_id"],
                rule_id="safe_actions",
                severity="error",
                message="Safe actions rule not found in policy",
                path=None,
            )

        if action not in safe_actions_rule["allowed_actions"]:
            return CheckResult(
                policy_id=self.policy["policy_id"],
                rule_id="safe_actions",
                severity="error",
                message=f"Action '{action}' is not in allowed actions: {safe_actions_rule['allowed_actions']}",
                path=None,
            )
        return CheckResult(
            policy_id=self.policy["policy_id"],
            rule_id="safe_actions",
            severity="pass",
            message=f"Action '{action}' is allowed",
            path=None,
        )

    def _check_safe_paths(self, file_path: str) -> CheckResult:
        """
        Verify if the file_path complies with allowed and forbidden paths.

        Args:
            file_path: The file path to validate.

        Returns:
            CheckResult: Result of the safe paths check.
        """
        from fnmatch import fnmatch

        safe_paths_rule = next(
            (rule for rule in self.policy["rules"] if rule["id"] == "safe_paths"), None
        )
        if not safe_paths_rule:
            return CheckResult(
                policy_id=self.policy["policy_id"],
                rule_id="safe_paths",
                severity="error",
                message="Safe paths rule not found in policy",
                path=file_path,
            )

        path_obj = Path(file_path)
        is_allowed = any(
            fnmatch(str(path_obj), pattern)
            for pattern in safe_paths_rule["allowed_paths"]
        )
        is_forbidden = any(
            fnmatch(str(path_obj), pattern)
            for pattern in safe_paths_rule["forbidden_paths"]
        )

        if is_forbidden:
            return CheckResult(
                policy_id=self.policy["policy_id"],
                rule_id="safe_paths",
                severity="error",
                message=f"File path '{file_path}' matches forbidden pattern",
                path=file_path,
            )
        if not is_allowed:
            return CheckResult(
                policy_id=self.policy["policy_id"],
                rule_id="safe_paths",
                severity="error",
                message=f"File path '{file_path}' does not match any allowed pattern",
                path=file_path,
            )
        return CheckResult(
            policy_id=self.policy["policy_id"],
            rule_id="safe_paths",
            severity="pass",
            message=f"File path '{file_path}' is allowed",
            path=file_path,
        )

    def _check_validation_report(self, report_id: str | None) -> CheckResult:
        """
        Verify if a validation report ID is provided and valid (placeholder).

        Args:
            report_id: The validation report ID to check.

        Returns:
            CheckResult: Result of the validation report check.
        """
        if not report_id:
            return CheckResult(
                policy_id=self.policy["policy_id"],
                rule_id="require_validation",
                severity="error",
                message="No validation report ID provided",
                path=None,
            )
        # Placeholder for actual validation report check (e.g., query DB or file)
        return CheckResult(
            policy_id=self.policy["policy_id"],
            rule_id="require_validation",
            severity="pass",
            message=f"Validation report '{report_id}' accepted (placeholder)",
            path=None,
        )

    # ID: 7c2e8d9a-6f3e-4c7a-b3f1-9e8a7f4c5d3b
    def validate_proposal(self, proposal: MicroProposal) -> list[CheckResult]:
        """
        Validate a micro-proposal against safe_actions, safe_paths, and
        require_validation rules from micro_proposal_policy.yaml.

        Args:
            proposal: The MicroProposal to validate.

        Returns:
            List[CheckResult]: List of validation results detailing compliance or violations.
        """
        results = []
        log.debug(
            f"Validating micro-proposal for action '{proposal.action}' on '{proposal.file_path}'"
        )

        # Check safe actions
        results.append(self._check_safe_actions(proposal.action))

        # Check safe paths
        results.append(self._check_safe_paths(proposal.file_path))

        # Check validation report
        results.append(self._check_validation_report(proposal.validation_report_id))

        # Log validation outcome
        errors = [r for r in results if r.severity == "error"]
        if errors:
            log.error(
                f"Micro-proposal validation failed: {[(r.rule_id, r.message) for r in errors]}"
            )
        else:
            log.info("Micro-proposal passed all validation checks")

        return results

    # ID: 5d4f9e8b-8c2f-4d9a-a4e2-0f7b6a5c4e3a
    async def apply_proposal(self, proposal: MicroProposal) -> bool:
        """
        Apply a validated micro-proposal by executing the specified action.

        Args:
            proposal: The MicroProposal to apply, expected to have passed validation.

        Returns:
            bool: True if the proposal was applied successfully, False otherwise.
        """
        validation_results = self.validate_proposal(proposal)
        if any(result.severity == "error" for result in validation_results):
            log.error("Cannot apply proposal due to validation errors")
            return False

        try:
            if proposal.action == "autonomy.self_healing.format_code":
                # Placeholder for formatting logic (e.g., invoke black)
                Path(proposal.file_path).write_text(proposal.content, encoding="utf-8")
                log.info(f"Applied format_code to {proposal.file_path}")
            elif proposal.action == "autonomy.self_healing.fix_docstrings":
                # Placeholder for docstring fixing logic
                Path(proposal.file_path).write_text(proposal.content, encoding="utf-8")
                log.info(f"Applied fix_docstrings to {proposal.file_path}")
            elif proposal.action == "autonomy.self_healing.fix_headers":
                # Placeholder for header fixing logic
                Path(proposal.file_path).write_text(proposal.content, encoding="utf-8")
                log.info(f"Applied fix_headers to {proposal.file_path}")
            else:
                log.error(f"Unsupported action: {proposal.action}")
                return False

            return True
        except Exception as e:
            log.error(f"Failed to apply micro-proposal: {e}")
            return False
