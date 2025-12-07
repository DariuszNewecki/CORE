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

logger = getLogger(__name__)


@dataclass
# ID: 59a37e53-cff3-451b-b007-e67294a938bc
class MicroProposal:
    """Internal data structure for a micro-proposal with target file, action, and content."""

    file_path: str
    action: str
    content: str
    validation_report_id: str | None = None


# ID: a681a59e-70b7-43a9-a35e-228ca254d055
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
        logger.debug("MicroProposalExecutor initialized")

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
            logger.error("Failed to load micro-proposal policy: %s", e)
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
        return CheckResult(
            policy_id=self.policy["policy_id"],
            rule_id="require_validation",
            severity="pass",
            message=f"Validation report '{report_id}' accepted (placeholder)",
            path=None,
        )

    # ID: b539d219-51aa-4123-9cd8-d77ffb209a4c
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
        logger.debug(
            f"Validating micro-proposal for action '{proposal.action}' on '{proposal.file_path}'"
        )
        results.append(self._check_safe_actions(proposal.action))
        results.append(self._check_safe_paths(proposal.file_path))
        results.append(self._check_validation_report(proposal.validation_report_id))
        errors = [r for r in results if r.severity == "error"]
        if errors:
            logger.error(
                f"Micro-proposal validation failed: {[(r.rule_id, r.message) for r in errors]}"
            )
        else:
            logger.info("Micro-proposal passed all validation checks")
        return results

    # ID: 945fb9c6-6789-415c-9412-64b57e03fd8f
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
            logger.error("Cannot apply proposal due to validation errors")
            return False
        try:
            if proposal.action == "autonomy.self_healing.format_code":
                Path(proposal.file_path).write_text(proposal.content, encoding="utf-8")
                logger.info(f"Applied format_code to {proposal.file_path}")
            elif proposal.action == "autonomy.self_healing.fix_docstrings":
                Path(proposal.file_path).write_text(proposal.content, encoding="utf-8")
                logger.info(f"Applied fix_docstrings to {proposal.file_path}")
            elif proposal.action == "autonomy.self_healing.fix_headers":
                Path(proposal.file_path).write_text(proposal.content, encoding="utf-8")
                logger.info(f"Applied fix_headers to {proposal.file_path}")
            else:
                logger.error(f"Unsupported action: {proposal.action}")
                return False
            return True
        except Exception as e:
            logger.error("Failed to apply micro-proposal: %s", e)
            return False
