# src/mind/governance/checks/base_check.py
"""
Provides a shared base class for all constitutional audit checks to inherit from.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, ClassVar

from shared.logger import getLogger


logger = getLogger(__name__)

if TYPE_CHECKING:
    from mind.governance.audit_context import AuditorContext


# ID: 2cb0374b-a487-4dce-bab1-c2ee8a693b0a
class BaseCheck:
    """
    A base class for audit checks, providing a shared context and requiring
    subclasses to declare the constitutional rules they enforce.
    """

    # --- CONSTITUTIONAL ENFORCEMENT CONTRACT ---
    # Every subclass MUST override this attribute to declare which specific
    # policy rule IDs it is responsible for enforcing. This creates a traceable
    # link between the constitution (the law) and the checks (the enforcement).
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

        # Future enhancement: You could add logic here to validate that
        # subclasses have indeed overridden `policy_rule_ids`.
        if not self.policy_rule_ids:
            logger.info(
                f"Warning: Check '{self.__class__.__name__}' does not enforce any policy rules."
            )
