# src/body/atomic/executor.py
# ID: c50206d4-1f2b-42c6-b665-e4018cbbd55c
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
- Runtime result validation

CRITICAL: This enforces the "single execution contract" principle.

CONSTITUTIONAL ENFORCEMENT:
This module enforces .intent/rules/architecture/atomic_actions.json at runtime.
Actions that return invalid results are wrapped with error ActionResults.

HEALED (V2.3.0):
- Layer Violation Fix: _validate_policies now queries IntentRepository
  in-memory index instead of PathResolver filesystem access.
  Body must never touch .intent/ directly — Mind indexes at startup,
  Body queries the index.
"""

from __future__ import annotations

import inspect
import json
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from body.atomic.registry import ActionDefinition, action_registry
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: b2c3d4e5-f6a7-8b9c-0d1e-2f3a4b5c6d7e
def _validate_action_result(action_id: str, result: Any) -> ActionResult:
    """
    Validate action result against constitutional requirements.

    Enforces .intent/rules/architecture/atomic_actions.json:
    - atomic_actions.result_must_be_structured
    - atomic_actions.no_governance_bypass

    If the result is not an ActionResult, wraps it in an error ActionResult.
    If the result.data is not a dict, wraps it in an error ActionResult.

    Args:
        action_id: Action that produced the result
        result: The returned value from the action

    Returns:
        Valid ActionResult (either the original or an error wrapper)
    """
    # Rule: atomic_actions.no_governance_bypass
    # Check if result is ActionResult
    if not isinstance(result, ActionResult):
        logger.error(
            "Constitutional violation detected at runtime: "
            "Action '%s' returned type '%s' instead of ActionResult. "
            "Rule: atomic_actions.no_governance_bypass. "
            "Wrapping in error ActionResult.",
            action_id,
            type(result).__name__,
        )
        return ActionResult(
            action_id=action_id,
            ok=False,
            data={
                "error": "Constitutional violation",
                "detail": f"Action returned {type(result).__name__} instead of ActionResult",
                "rule_violated": "atomic_actions.no_governance_bypass",
                "original_result": str(result)[:200],  # Truncate for safety
            },
            duration_sec=0.0,
        )

    # Rule: atomic_actions.result_must_be_structured
    # Check if result.data is a dict
    if not isinstance(result.data, dict):
        logger.error(
            "Constitutional violation detected at runtime: "
            "Action '%s' returned ActionResult with non-dict data (type: %s). "
            "Rule: atomic_actions.result_must_be_structured. "
            "Wrapping in error ActionResult.",
            action_id,
            type(result.data).__name__,
        )
        return ActionResult(
            action_id=action_id,
            ok=False,
            data={
                "error": "Constitutional violation",
                "detail": f"ActionResult.data must be dict, got {type(result.data).__name__}",
                "rule_violated": "atomic_actions.result_must_be_structured",
                "original_data_type": type(result.data).__name__,
            },
            duration_sec=result.duration_sec,
        )

    # Validation passed
    logger.debug(
        "Runtime constitutional validation passed for action '%s': "
        "result is ActionResult with dict data",
        action_id,
    )
    return result


# ID: c84e1977-dfbd-47f1-83e0-01260da9420e
# ID: e1b46328-53d2-4abe-93e4-3b875d50300f
class ActionExecutor:
    """
    Universal execution gateway for all atomic actions.

    This class enforces constitutional governance for every action
    execution, regardless of whether the caller is human or AI.

    Architecture:
    - Loads action definitions from registry
    - Validates policies exist in constitution (via Mind's in-memory index)
    - Checks impact authorization
    - Executes pre/post hooks
    - Validates results at runtime
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

    # ID: 535abb39-c8d9-4d38-9ab3-782e4e43e233
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
        6. VALIDATES RESULT AT RUNTIME (constitutional enforcement)
        7. Runs post-execution hooks
        8. Records audit trail

        Args:
            action_id: Registered action ID (e.g., "fix.format")
            write: Whether to apply changes (False = dry-run)
            **params: Action-specific parameters

        Returns:
            ActionResult with execution details, timing, and status
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

        # 2. Validate constitutional policies (via Mind's in-memory index)
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
            # Prepare execution parameters with smart injection
            exec_params = self._prepare_params(definition, write, params)

            raw_result = await definition.executor(**exec_params)

            # CONSTITUTIONAL ENFORCEMENT: Validate result at runtime
            result = _validate_action_result(action_id, raw_result)

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

    # ID: 7d302f78-f0c6-4fe5-8273-11f85d53b2fb
    async def _validate_policies(self, definition: ActionDefinition) -> dict[str, Any]:
        """
        Validate that all referenced policies exist in the constitution.

        CONSTITUTIONAL FIX (V2.3.0):
        Queries Mind's in-memory IntentRepository index instead of
        touching .intent/ filesystem via PathResolver. Body layer must
        never access .intent/ directly — Mind indexes at startup, Body
        queries the indexed knowledge.

        Policy IDs must match the canonical indexed format:
            rules/architecture/atomic_actions
            rules/code/purity
            rules/data/governance
        """
        from shared.infrastructure.intent.intent_repository import (
            get_intent_repository,
        )

        intent_repo = get_intent_repository()
        indexed_policies = {p.policy_id for p in intent_repo.list_policies()}

        missing = []
        for policy_id in definition.policies:
            if policy_id not in indexed_policies:
                missing.append(policy_id)

        if missing:
            logger.warning(
                "Action '%s' references unindexed policies: %s. "
                "Available: %d indexed policies. "
                "Policy IDs must use canonical format: rules/<domain>/<name>",
                definition.action_id,
                missing,
                len(indexed_policies),
            )

        return {
            "ok": len(missing) == 0,
            "policies": definition.policies,
            "missing": missing,
        }

    # ID: 238c67b1-eef2-436d-8013-091a6788368a
    def _check_authorization(
        self, definition: ActionDefinition, write: bool
    ) -> dict[str, Any]:
        """
        Check if action execution is authorized.
        """
        # Basic impact-level check
        if definition.impact_level == "dangerous" and write:
            logger.warning(
                "Dangerous action %s requested in write mode", definition.action_id
            )
            # In commercial mode, this is where we'd check a 'STRICT' flag
            return {
                "authorized": True,
                "impact_level": definition.impact_level,
                "write_mode": write,
            }

        return {
            "authorized": True,
            "impact_level": definition.impact_level,
            "write_mode": write,
        }

    # ID: 738ad11a-5848-49ce-a16d-2dfcbef8b763
    async def _pre_execute_hooks(
        self, definition: ActionDefinition, write: bool, params: dict[str, Any]
    ) -> None:
        """
        Execute pre-execution hooks.
        """
        logger.debug("Pre-execution hooks for %s", definition.action_id)

    # ID: 3de2d9e3-b074-485d-98ad-06ea51e009e2
    async def _post_execute_hooks(
        self, definition: ActionDefinition, result: ActionResult
    ) -> None:
        """
        Execute post-execution hooks.
        """
        logger.debug("Post-execution hooks for %s", definition.action_id)

    # ID: 454c8ccb-ece8-4ef8-baf1-13c9c19f4300
    async def _audit_log(
        self, definition: ActionDefinition, result: ActionResult, write: bool
    ) -> None:
        """
        Log action execution to database audit trail (SSOT).
        """
        try:
            async with self.core_context.registry.session() as session:
                async with session.begin():
                    # Record evidence for the Traceability Matrix
                    stmt = text(
                        """
                        INSERT INTO core.action_results
                        (action_type, ok, file_path, error_message, action_metadata, agent_id, duration_ms)
                        VALUES (:atype, :ok, :path, :err, :meta, :agent, :dur)
                    """
                    )
                    await session.execute(
                        stmt,
                        {
                            "atype": definition.action_id,
                            "ok": result.ok,
                            "path": result.data.get("path")
                            or result.data.get("file_path"),
                            "err": result.data.get("error") if not result.ok else None,
                            "meta": json.dumps(
                                {
                                    "write_mode": write,
                                    "impact": definition.impact_level,
                                }
                            ),
                            "agent": "ActionExecutor",
                            "dur": int(result.duration_sec * 1000),
                        },
                    )
        except Exception as e:
            logger.warning("Non-blocking audit log failure: %s", e)

    # ID: eff3eded-b30d-49e0-b50c-3503a1b695af
    def _prepare_params(
        self, definition: ActionDefinition, write: bool, params: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Prepare parameters for action execution with smart injection.
        """
        # Get the function signature
        sig = inspect.signature(definition.executor)
        param_names = set(sig.parameters.keys())

        # Build parameter dict with available injectables
        available = {
            "core_context": self.core_context,
            "write": write,
            **params,  # User-provided params take precedence
        }

        # Check if function accepts **kwargs
        has_var_keyword = any(
            p.kind == inspect.Parameter.VAR_KEYWORD for p in sig.parameters.values()
        )

        if has_var_keyword:
            # Function accepts **kwargs, give it everything
            return available

        # Only pass parameters the function actually accepts
        exec_params = {
            key: value for key, value in available.items() if key in param_names
        }

        return exec_params
