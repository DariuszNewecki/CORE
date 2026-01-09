# src/body/atomic/executor.py
# ID: atomic.executor
"""
Universal Action Executor - Constitutional Enforcement Gateway

This is the ONLY way actions are executed in CORE, whether:
- Human operator via CLI
- AI agent via PlanExecutor
- Workflow orchestrator via DevSyncWorkflow

Every action execution flows through this gateway, ensuring:
- Constitutional policy validation
- Impact level authorization
- Pre/post execution hooks
- Audit logging
- Consistent error handling

CRITICAL: This enforces the "single execution contract" principle.
"""

from __future__ import annotations

import shutil
import time
from typing import TYPE_CHECKING, Any

from body.atomic.registry import ActionCategory, ActionDefinition, action_registry
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: executor_main
# ID: e1b46328-53d2-4abe-93e4-3b875d50300f
class ActionExecutor:
    """
    Universal execution gateway for all atomic actions.

    This class enforces constitutional governance for every action
    execution, regardless of whether the caller is human or AI.

    Architecture:
    - Loads action definitions from registry
    - Validates policies exist in constitution
    - Checks impact authorization
    - Executes pre/post hooks
    - Provides audit trail
    - Returns consistent ActionResult

    Usage:
        executor = ActionExecutor(core_context)
        result = await executor.execute("fix.format", write=True)
    """

    def __init__(self, core_context: CoreContext):
        """
        Initialize executor with CORE context.

        Args:
            core_context: CoreContext with all services
        """
        self.core_context = core_context
        self.registry = action_registry
        logger.debug("ActionExecutor initialized")

    # ID: executor_execute
    # ID: d068c5cc-7e31-479e-a615-993e4570680c
    @atomic_action(
        action_id="action.execute",
        intent="Atomic action for execute",
        impact=ActionImpact.WRITE_CODE,
        policies=["atomic_actions"],
    )
    # ID: 0724a464-ca71-4c53-878c-2c2d75dabcde
    async def execute(
        self,
        action_id: str,
        write: bool = False,
        **params: Any,
    ) -> ActionResult:
        """
        Execute an action with full constitutional governance.

        This is the universal execution method that:
        1. Validates action exists in registry
        2. Validates constitutional policies
        3. Checks impact authorization
        4. Runs pre-execution hooks
        5. Executes the action
        6. Runs post-execution hooks
        7. Records audit trail

        Args:
            action_id: Registered action ID (e.g., "fix.format")
            write: Whether to apply changes (False = dry-run)
            **params: Action-specific parameters

        Returns:
            ActionResult with execution details, timing, and status

        Examples:
            # Format code (dry-run)
            result = await executor.execute("fix.format")

            # Format code (write)
            result = await executor.execute("fix.format", write=True)

            # Sync database
            result = await executor.execute("sync.db", write=True)
        """
        start_time = time.time()

        # 1. Load definition from registry
        definition = self.registry.get(action_id)
        if not definition:
            logger.error("Action not found in registry: %s", action_id)
            return ActionResult(
                action_id=action_id,
                ok=False,
                data={
                    "error": f"Action not found: {action_id}",
                    "available_actions": [
                        a.action_id for a in self.registry.list_all()
                    ],
                },
                duration_sec=time.time() - start_time,
            )

        logger.info(
            "Executing action: %s (write=%s, category=%s, impact=%s)",
            action_id,
            write,
            definition.category.value,
            definition.impact_level,
        )

        # 2. Validate constitutional policies
        policy_validation = await self._validate_policies(definition)
        if not policy_validation["ok"]:
            logger.warning("Policy validation failed for %s", action_id)
            return ActionResult(
                action_id=action_id,
                ok=False,
                data={
                    "error": "Policy validation failed",
                    "details": policy_validation,
                },
                duration_sec=time.time() - start_time,
            )

        # 3. Check impact authorization
        auth_check = self._check_authorization(definition, write)
        if not auth_check["authorized"]:
            logger.warning("Authorization failed for %s", action_id)
            return ActionResult(
                action_id=action_id,
                ok=False,
                data={
                    "error": "Authorization failed",
                    "details": auth_check,
                },
                duration_sec=time.time() - start_time,
            )

        # 4. Pre-execution hooks
        await self._pre_execute_hooks(definition, write, params)

        # 5. Execute action
        try:
            # Prepare execution parameters
            exec_params = self._prepare_params(definition, write, params)

            result = await definition.executor(**exec_params)

            logger.info(
                "Action %s completed: ok=%s, duration=%.2fs",
                action_id,
                result.ok,
                result.duration_sec,
            )

        except Exception as e:
            logger.error(
                "Action %s failed with exception: %s", action_id, e, exc_info=True
            )
            result = ActionResult(
                action_id=action_id,
                ok=False,
                data={
                    "error": str(e),
                    "error_type": type(e).__name__,
                },
                duration_sec=time.time() - start_time,
            )

        # 6. Post-execution hooks
        await self._post_execute_hooks(definition, result)

        # 7. Audit logging
        await self._audit_log(definition, result, write)

        return result

    # ID: executor_validate_policies
    async def _validate_policies(self, definition: ActionDefinition) -> dict[str, Any]:
        """
        Validate that all referenced policies exist in the constitution.

        Args:
            definition: Action definition with policy references

        Returns:
            Validation result with ok status and details
        """
        # FUTURE: Phase 2 - Query constitution database for policy existence
        # For now, assume all policies are valid
        return {
            "ok": True,
            "policies_checked": definition.policies,
            "note": "Policy validation placeholder - Phase 2 will check constitution DB",
        }

    # ID: executor_check_authorization
    def _check_authorization(
        self, definition: ActionDefinition, write: bool
    ) -> dict[str, Any]:
        """
        Check if action is authorized based on impact level and write mode.

        Impact Levels:
        - "safe": Always authorized (read-only, metadata)
        - "moderate": Authorized in write mode (code changes)
        - "dangerous": Requires explicit confirmation (destructive)

        Args:
            definition: Action definition with impact level
            write: Whether action will write changes

        Returns:
            Authorization result with authorized flag and reason
        """
        impact = definition.impact_level.lower()

        # Safe actions always authorized
        if impact == "safe":
            return {
                "authorized": True,
                "reason": "Safe impact level",
                "impact_level": impact,
            }

        # Moderate actions authorized in write mode
        if impact == "moderate":
            if write:
                return {
                    "authorized": True,
                    "reason": "Moderate impact authorized in write mode",
                    "impact_level": impact,
                }
            else:
                return {
                    "authorized": True,
                    "reason": "Dry-run mode (no actual changes)",
                    "impact_level": impact,
                }

        # Dangerous actions require explicit handling
        if impact == "dangerous":
            # FUTURE: Phase 2 - Implement confirmation mechanism
            if write:
                return {
                    "authorized": False,
                    "reason": "Dangerous actions require explicit confirmation",
                    "impact_level": impact,
                }
            else:
                return {
                    "authorized": True,
                    "reason": "Dry-run mode (safe preview)",
                    "impact_level": impact,
                }

        # Unknown impact level - deny by default
        return {
            "authorized": False,
            "reason": f"Unknown impact level: {impact}",
            "impact_level": impact,
        }

    # ID: executor_prepare_params
    def _prepare_params(
        self, definition: ActionDefinition, write: bool, params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Prepare execution parameters based on action requirements.

        Injects required dependencies:
        - core_context if action needs it
        - write flag for all actions
        - Resource checks (DB, vectors)

        Args:
            definition: Action definition
            write: Write mode flag
            params: User-provided parameters

        Returns:
            Complete parameter dict for action execution
        """
        exec_params = {"write": write}

        # Inject core_context if action signature needs it
        # We check the function signature to be smart about this
        import inspect

        sig = inspect.signature(definition.executor)
        if "core_context" in sig.parameters:
            exec_params["core_context"] = self.core_context

        # Add user parameters
        exec_params.update(params)

        # Resource availability checks
        if definition.requires_db and not self.core_context.db_available:
            logger.warning(
                "Action %s requires DB but it's not available", definition.action_id
            )

        if definition.requires_vectors and not self.core_context.qdrant_service:
            logger.warning(
                "Action %s requires vectors but Qdrant is not available",
                definition.action_id,
            )

        return exec_params

    # ID: executor_pre_hooks
    async def _pre_execute_hooks(
        self, definition: ActionDefinition, write: bool, params: dict[str, Any]
    ) -> None:
        """
        Run pre-execution hooks.

        These run BEFORE action execution to:
        - Validate preconditions
        - Prepare environment
        - Check resource availability

        Args:
            definition: Action definition
            write: Write mode
            params: Execution parameters
        """
        action_id = definition.action_id
        git_service = self.core_context.git_service

        if write and git_service and git_service.is_git_repo():
            try:
                status = git_service.status_porcelain()
            except Exception as exc:
                logger.warning("Pre-hook git status failed for %s: %s", action_id, exc)
            else:
                if status:
                    dirty_count = len(status.splitlines())
                    logger.warning(
                        "Git working directory not clean before %s (%d changes)",
                        action_id,
                        dirty_count,
                    )

        if write and (
            action_id.startswith("file.")
            or definition.category in (ActionCategory.FIX, ActionCategory.BUILD)
        ):
            repo_path = git_service.repo_path if git_service else None
            if repo_path:
                try:
                    _total, _used, free = shutil.disk_usage(repo_path)
                except Exception as exc:
                    logger.warning(
                        "Pre-hook disk check failed for %s: %s", action_id, exc
                    )
                else:
                    min_free_bytes = 100 * 1024 * 1024
                    if free < min_free_bytes:
                        logger.warning(
                            "Low disk space before %s: %d MB free",
                            action_id,
                            free // (1024 * 1024),
                        )

        if definition.requires_db and not self.core_context.db_available:
            logger.warning("Action %s requires DB but it's not available", action_id)

        if definition.requires_vectors and not self.core_context.qdrant_service:
            logger.warning(
                "Action %s requires vectors but Qdrant is not available", action_id
            )

    # ID: executor_post_hooks
    async def _post_execute_hooks(
        self, definition: ActionDefinition, result: ActionResult
    ) -> None:
        """
        Run post-execution hooks.

        These run AFTER action execution to:
        - Validate results
        - Update metrics
        - Trigger dependent actions

        Args:
            definition: Action definition
            result: Execution result
        """
        # FUTURE: Phase 2 - Implement post-execution hooks
        # Examples:
        # - Run constitutional audit after fix actions
        # - Update success rate metrics
        # - Notify monitoring systems
        logger.debug("Post-execution hooks for %s (placeholder)", definition.action_id)

    # ID: executor_audit_log
    async def _audit_log(
        self, definition: ActionDefinition, result: ActionResult, write: bool
    ) -> None:
        """
        Record execution in audit trail.

        Creates permanent record of:
        - What action was executed
        - When it was executed
        - Who/what executed it
        - What the result was
        - What changes were made

        Args:
            definition: Action definition
            result: Execution result
            write: Whether changes were written
        """
        # FUTURE: Phase 2 - Persist to audit database
        # For now, structured logging
        logger.info(
            "AUDIT: action=%s category=%s impact=%s write=%s ok=%s duration=%.2fs",
            definition.action_id,
            definition.category.value,
            definition.impact_level,
            write,
            result.ok,
            result.duration_sec,
        )

    # ID: executor_list_actions
    # ID: 118ed7f6-3a4f-4c31-b6a9-448727bbea76
    def list_actions(
        self, category: ActionCategory | None = None
    ) -> list[ActionDefinition]:
        """
        List available actions, optionally filtered by category.

        Args:
            category: Optional category filter

        Returns:
            List of action definitions
        """
        if category:
            return self.registry.get_by_category(category)
        return self.registry.list_all()

    # ID: executor_get_action
    # ID: 46e53493-d92c-402d-83c8-b9516d394f81
    def get_action(self, action_id: str) -> ActionDefinition | None:
        """
        Get action definition by ID.

        Args:
            action_id: Action identifier

        Returns:
            Action definition or None if not found
        """
        return self.registry.get(action_id)
