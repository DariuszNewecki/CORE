# src/features/autonomy/micro_proposal_executor.py

"""
Service for validating and applying micro-proposals to enable safe, autonomous
changes to the CORE codebase, adhering to the micro_proposal_policy.yaml and
enforcing safe_by_default and reason_with_purpose principles.

Architectural rule:
- No direct filesystem mutations (write_text/unlink/mkdir/etc.) in this service.
- All mutations must go through FileHandler (IntentGuard enforced).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from pathlib import Path

from shared.infrastructure.storage.file_handler import FileHandler
from shared.logger import getLogger
from shared.models import CheckResult
from shared.path_utils import get_repo_root
from shared.utils.yaml_processor import strict_yaml_processor


logger = getLogger(__name__)


@dataclass
# ID: 5a5fabd4-5e30-48c6-ad4d-5702abbb22e8
class MicroProposal:
    """Internal data structure for a micro-proposal with target file, action, and content."""

    file_path: str
    action: str
    content: str
    validation_report_id: str | None = None
    intent_bundle_id: str | None = None  # Added for constitutional audit traceability


# ID: 91fbe5a7-9add-46b5-9443-c9759e49fa28
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
        self.repo_root = (repo_root or get_repo_root()).resolve()

        # NOTE: policy path kept as-is (your repo currently points to this location)
        self.policy_path = (
            self.repo_root / ".intent/charter/policies/agent/micro_proposal_policy.json"
        )
        self.policy = self._load_policy()

        # Mutation surface (IntentGuard enforced inside)
        self.fs = FileHandler(str(self.repo_root))

        logger.debug("MicroProposalExecutor initialized (repo_root=%s)", self.repo_root)

    def _load_policy(self) -> dict:
        """
        Load and validate the micro_proposal_policy.yaml (or json).

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
        """
        safe_actions_rule = next(
            (
                rule
                for rule in self.policy.get("rules", [])
                if rule.get("id") == "safe_actions"
            ),
            None,
        )
        allowed = (safe_actions_rule or {}).get("allowed_actions", []) or []
        if action not in allowed:
            return CheckResult(
                policy_id=self.policy.get("policy_id", "micro_proposal_policy"),
                rule_id="safe_actions",
                severity="error",
                message=f"Action '{action}' is not in allowed actions",
                path=None,
            )
        return CheckResult(
            policy_id=self.policy.get("policy_id", "micro_proposal_policy"),
            rule_id="safe_actions",
            severity="pass",
            message=f"Action '{action}' is allowed",
            path=None,
        )

    def _check_safe_paths(self, file_path: str) -> CheckResult:
        """
        Verify if the file_path matches allowed patterns and does not match forbidden patterns.
        """
        # This module historically validated paths via policy rules, but the repo also
        # enforces a second gate at mutation-time (IntentGuard inside FileHandler).
        safe_paths_rule = next(
            (
                rule
                for rule in self.policy.get("rules", [])
                if rule.get("id") == "safe_paths"
            ),
            None,
        )
        allowed_patterns = (safe_paths_rule or {}).get("allowed_paths", []) or []
        forbidden_patterns = (safe_paths_rule or {}).get("forbidden_paths", []) or []

        # Normalize to repo-relative for evaluation
        rel = self._normalize_to_repo_rel(file_path)

        # Lightweight glob-style matching using Path.match semantics
        rel_path = Path(rel)

        def _matches_any(patterns: list[str]) -> bool:
            for pat in patterns:
                # Path.match treats patterns as relative and supports ** on POSIX style
                if rel_path.match(pat):
                    return True
            return False

        if forbidden_patterns and _matches_any(forbidden_patterns):
            return CheckResult(
                policy_id=self.policy.get("policy_id", "micro_proposal_policy"),
                rule_id="safe_paths",
                severity="error",
                message=f"File path '{rel}' matches a forbidden pattern",
                path=rel,
            )
        if allowed_patterns and not _matches_any(allowed_patterns):
            return CheckResult(
                policy_id=self.policy.get("policy_id", "micro_proposal_policy"),
                rule_id="safe_paths",
                severity="error",
                message=f"File path '{rel}' does not match any allowed pattern",
                path=rel,
            )
        return CheckResult(
            policy_id=self.policy.get("policy_id", "micro_proposal_policy"),
            rule_id="safe_paths",
            severity="pass",
            message=f"File path '{rel}' is allowed",
            path=rel,
        )

    def _check_validation_report(self, report_id: str | None) -> CheckResult:
        """
        Verify if a validation report ID is provided and valid (placeholder).
        """
        if not report_id:
            return CheckResult(
                policy_id=self.policy.get("policy_id", "micro_proposal_policy"),
                rule_id="require_validation",
                severity="error",
                message="No validation report ID provided",
                path=None,
            )
        return CheckResult(
            policy_id=self.policy.get("policy_id", "micro_proposal_policy"),
            rule_id="require_validation",
            severity="pass",
            message=f"Validation report '{report_id}' accepted (placeholder)",
            path=None,
        )

    # ID: 8e521e21-2ee8-4890-8e1a-be92893f4d61
    def validate_proposal(self, proposal: MicroProposal) -> list[CheckResult]:
        """
        Validate a micro-proposal against safe_actions, safe_paths, and
        require_validation rules from micro_proposal_policy.yaml.
        """
        results: list[CheckResult] = []
        logger.debug(
            "Validating micro-proposal for action '%s' on '%s'",
            proposal.action,
            proposal.file_path,
        )
        results.append(self._check_safe_actions(proposal.action))
        results.append(self._check_safe_paths(proposal.file_path))
        results.append(self._check_validation_report(proposal.validation_report_id))

        errors = [r for r in results if r.severity == "error"]
        if errors:
            logger.error(
                "Micro-proposal validation failed: %s",
                [(r.rule_id, r.message) for r in errors],
            )
        else:
            logger.info("Micro-proposal passed all validation checks")
        return results

    def _normalize_to_repo_rel(self, file_path: str) -> str:
        """
        Convert file_path into a repo-relative path (string), rejecting escapes.
        Supports:
        - repo-relative paths like 'src/x.py'
        - absolute paths under repo_root like '/opt/dev/CORE/src/x.py'
        """
        raw = str(file_path).strip()

        # Treat empty as invalid early (prevents writing to repo root by mistake)
        if not raw:
            raise ValueError("Proposal file_path is empty")

        p = Path(raw)

        if p.is_absolute():
            try:
                rel = p.resolve().relative_to(self.repo_root)
            except ValueError as e:
                raise ValueError(f"Absolute path is outside repo_root: {p}") from e
            return str(rel).lstrip("./")

        # Relative: normalize and ensure it stays within repo_root when resolved
        candidate = (self.repo_root / p).resolve()
        try:
            rel = candidate.relative_to(self.repo_root)
        except ValueError as e:
            raise ValueError(f"Relative path escapes repo_root: {raw}") from e

        return str(rel).lstrip("./")

    # ID: d9dcf58e-224a-4971-bab0-750913c3c3e8
    async def apply_proposal(self, proposal: MicroProposal) -> bool:
        """
        Apply a validated micro-proposal by executing the specified action.

        Policy:
        - Validation first
        - Log intent_bundle_id
        - Write only via FileHandler (IntentGuard enforced)
        """
        validation_results = self.validate_proposal(proposal)
        if any(result.severity == "error" for result in validation_results):
            logger.error("Cannot apply proposal due to validation errors")
            return False

        # Constitutional requirement: Generate and log IntentBundle ID before write operations
        if not proposal.intent_bundle_id:
            proposal.intent_bundle_id = str(uuid.uuid4())

        logger.info(
            "Applying micro-proposal with intent_bundle_id: %s",
            proposal.intent_bundle_id,
        )

        try:
            rel_target = self._normalize_to_repo_rel(proposal.file_path)

            if proposal.action in {
                "autonomy.self_healing.format_code",
                "autonomy.self_healing.fix_docstrings",
                "autonomy.self_healing.fix_headers",
            }:
                logger.info(
                    "Writing changes for intent_bundle_id: %s to %s",
                    proposal.intent_bundle_id,
                    rel_target,
                )

                # IMPORTANT: mutation via governed surface (IntentGuard blocks .intent/**)
                self.fs.write_runtime_text(rel_target, proposal.content)

                logger.info("Applied %s to %s", proposal.action, rel_target)
                return True

            logger.error("Unsupported action: %s", proposal.action)
            return False

        except Exception as e:
            logger.error("Failed to apply micro-proposal: %s", e)
            return False
