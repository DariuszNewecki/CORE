# src/mind/governance/checks/base_check.py

"""
Provides a shared base class for all constitutional audit checks to inherit from.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from shared.logger import getLogger
from shared.models import AuditFinding  # Enforce return type contract


logger = getLogger(__name__)

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


# ID: 2a274998-e17b-498a-be66-0bf2af8b7394
class BaseCheck(ABC):
    """
    A base class for audit checks, providing a shared context and requiring
    subclasses to declare the constitutional rules they enforce.

    Enforces the 'governance_check' entry point pattern via abstract execute().
    """

    policy_rule_ids: ClassVar[list[str]] = []

    def __init__(self, context: AuditorContext):
        """
        Initializes the check with a shared auditor context.
        This common initializer serves the 'dry_by_design' principle.
        """
        self.context = context
        self.repo_root = context.repo_path
        self.intent_path = context.intent_path
        self.src_dir = context.src_dir

        # Enforce Policy Integrity: Checks must declare what they enforce
        if not self.policy_rule_ids:
            logger.warning(
                "Check '%s' does not enforce any policy rules. "
                "This may violate policy_integrity.yaml.",
                self.__class__.__name__,
            )

    @abstractmethod
    # ID: fbe633a1-3dda-4d78-be07-e6bf4399ecc6
    def execute(self) -> list[AuditFinding]:
        """
        The constitutional contract for all Governance Checks.
        Must return a list of findings (empty if compliant).
        """
        pass
