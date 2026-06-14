# src/body/atomic/executor.py
"""
Universal Action Executor - Constitutional Enforcement Gateway

This is the ONLY way actions are executed in CORE, whether:
- Human operator via CLI
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

import inspect
import json
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from body.atomic.registry import ActionCategory, ActionDefinition, action_registry
from body.atomic.sandbox_lifecycle import SandboxLifecycle
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.governance_token import authorize_execution
from shared.infrastructure.intent.action_risk import load_action_risk
from shared.infrastructure.intent.intent_repository import get_intent_repository
from shared.infrastructure.intent.operational_capabilities import (
    load_operational_capabilities,
)
from shared.logger import _current_run_id, getLogger


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
    """
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
                "original_result": str(result)[:200],
            },
            duration_sec=0.0,
        )

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
                "detail": f"ActionResult.data is {type(result.data).__name__} instead of dict",
                "rule_violated": "atomic_actions.result_must_be_structured",
            },
            duration_sec=result.duration_sec,
        )

    return result


# ID: e1b46328-53d2-4abe-93e4-3b875d50300f
class ActionExecutor:
    """
    Universal execution gateway for all atomic actions.

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
        import body.atomic  # noqa: F401 — triggers action registration

        self.core_context = core_context
        self.registry = action_registry
        self._sandbox = SandboxLifecycle(core_context)

        # Overlay impact_level from .intent/enforcement/config/action_risk.yaml
        # onto every registered ActionDefinition. @register_action no longer
        # accepts impact_level — it is governed externally. See ADR-008.
        risk_mapping = load_action_risk()
        self.registry.apply_risk_config(risk_mapping)

        # ADR-091 D6 item 3 + ADR-092 D1 + D4 Option B: overlay artifact_type
        # from .intent/taxonomies/operational_capabilities.yaml. Capabilities
        # without an artifact target legitimately omit the field (ADR-092
        # sub-question (i)); their actions stay at the default empty tuple
        # and bypass the registry-coupling refusal check.
        capability_artifact_map = {
            cap.id: cap.artifact_type
            for cap in load_operational_capabilities()
            if cap.artifact_type
        }
        self.registry.apply_artifact_type_config(capability_artifact_map)

        logger.debug("ActionExecutor initialized")

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
        pre_execution_sha: str | None = None,
        **params: Any,
    ) -> ActionResult:
        """
        Execute an action with full constitutional governance.

        1. Validates action exists in registry
        2. Validates constitutional policies
        3. Checks impact authorization
        4. Runs pre-execution hooks
        5. Executes the action (sandboxed in a git worktree if applicable)
        6. Runs post-execution hooks
        7. Records audit trail

        Sandboxing (ADR-071 D2.2 Phase 2)
        --------------------------------
        When `pre_execution_sha` is supplied AND `write=True` AND the
        action's ActionImpact is WRITE_CODE or WRITE_METADATA, the action
        runs against a hermetic git worktree checked out at
        `pre_execution_sha`. The scoped CoreContext has both `git_service`
        and `file_handler` repointed at the worktree, so mutations land
        inside the sandbox. On success, changed files are copy-propagated
        back to the main tree under ADR-021's existing scope-binding (the
        commit_paths call in proposal_execution_pipeline is unchanged).
        On failure, the sandbox is discarded and the main tree is
        untouched. CLI direct invocations leave `pre_execution_sha=None`
        and pass through with no sandbox — D2.1's operational stop/start
        protocol covers concurrent-human cases there.
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

        # 1.5. F-43 registry-coupling refusal (ADR-091 D6 item 3, ADR-092 D1).
        # When the action's capability declares an artifact_type, every
        # declared ID must be present in the F-41 IntentRepository registry.
        # Actions whose capability omits the field (ADR-092 sub-question (i))
        # bypass this check — their artifact_type tuple is empty.
        if definition.artifact_type:
            intent_repo = get_intent_repository()
            intent_repo.initialize()
            registered_ids = {ref.id for ref in intent_repo.list_artifact_types()}
            unregistered = tuple(
                at for at in definition.artifact_type if at not in registered_ids
            )
            if unregistered:
                logger.warning(
                    "Action %s refused: declared artifact_type(s) %s not "
                    "registered in F-41 IntentRepository",
                    action_id,
                    list(unregistered),
                )
                return ActionResult(
                    action_id=action_id,
                    ok=False,
                    data={
                        "error": "Action declared unregistered artifact_type",
                        "unregistered_artifact_types": list(unregistered),
                        "registered_artifact_types": sorted(registered_ids),
                        "constitutional_basis": (
                            "ADR-091 D6 item 3 registry-coupling enforcement; "
                            "ADR-092 D1 F-43 exit criterion"
                        ),
                    },
                    duration_sec=time.time() - start_time,
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

        # 5. Execute action (sandboxed when ADR-071 D2.2 conditions hold)
        exec_context, scoped_git = self._sandbox.build_execution_context(
            definition, write, pre_execution_sha
        )
        try:
            exec_params = self._prepare_params(
                definition, write, params, context=exec_context
            )

            # --- Issue Governance Token ---
            with authorize_execution(action_id):
                raw_result = await definition.executor(**exec_params)
            # --- End Governance Token ---

            # CONSTITUTIONAL ENFORCEMENT: Validate result at runtime
            result = _validate_action_result(action_id, raw_result)

            if scoped_git is not None and result.ok:
                target_paths = self._sandbox.propagate_changes(scoped_git)
                # ADR-101 D2: stamp the sandbox production set onto the
                # result so commit_proposal_changes can derive the commit
                # set (and rollback the rollback target) from actual
                # production, not from the proposal's permission scope.
                # Underscore-prefixed key marks this as runtime-injected,
                # not declared by the action.
                if isinstance(result.data, dict):
                    result.data["_sandbox_target_paths"] = sorted(target_paths)

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
        finally:
            if scoped_git is not None:
                scoped_git.cleanup()

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
        touching .intent/ filesystem via PathResolver.
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
                "Policy IDs must use canonical format: rules/<domain>/<n>",
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
        Inline pass-through — authorization of record is the approval layer.

        This method intentionally returns ``authorized: True``; it is NOT the
        authorization gate and never was. For the autonomous path an action's
        authority to run is decided UPSTREAM, before ActionExecutor is reached:
        ``.intent/enforcement/config/action_risk.yaml`` classifies every action
        ``safe | moderate | dangerous``, and ``Proposal.requires_approval``
        (``src/will/autonomy/proposal.py``) gates execution on it — only
        ``safe`` auto-executes; ``moderate``/``dangerous`` (and any unmapped
        action, which fails closed to ``moderate``) require explicit governor
        approval before a proposal can execute. The audit → consequence loop is
        the post-hoc net. By the time execute() runs an autonomous action its
        authorization has already been adjudicated, so re-deciding it here would
        duplicate the approval layer, not add safety.

        A ``dangerous`` + ``write`` request still logs a warning because the one
        path NOT covered by approval gating is a direct CLI invocation (no
        proposal → no ``requires_approval`` check). That is a governor-operated,
        trusted-operator surface today (see #636 on the CLI/sandbox boundary).
        Activation criterion for filling this method with a real deny path: a
        dangerous action becoming reachable by a NON-governor caller — e.g. the
        action-execution surface exposed over the API, or non-governor CLI
        users. Until then the inline check is a pass-through by design.

        (A prior docstring cited ADR-015/017/019 as the deferral basis; those
        are consequence-chain *attribution* decisions and establish no
        authorization deferral — citation corrected per #633.)
        """
        if definition.impact_level == "dangerous" and write:
            logger.warning(
                "Dangerous action %s requested in write mode via the inline "
                "path — authorization of record is the approval layer "
                "(action_risk → Proposal.requires_approval); the inline check "
                "is a pass-through (see #633).",
                definition.action_id,
            )

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

        CONSTITUTIONAL FIX: session_id is read cleanly from _current_run_id
        context var (imported at module level). Removed duplicate key and
        broken __import__ hack from prior patch.
        """
        try:
            async with self.core_context.registry.session() as session:
                async with session.begin():
                    stmt = text(
                        """
                        INSERT INTO core.action_results
                        (action_type, ok, file_path, error_message, action_metadata, agent_id, duration_ms)
                        VALUES (:atype, :ok, :path, :err, :meta, :agent, :dur)
                        """
                    )
                    # Prefer session_id from core_context, fall back to context var
                    session_id = getattr(
                        self.core_context, "session_id", None
                    ) or _current_run_id.get(None)

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
                                    "session_id": session_id,
                                }
                            ),
                            "agent": "ActionExecutor",
                            "dur": int(result.duration_sec * 1000),
                        },
                    )
        except Exception as e:
            # #634: audit persistence is best-effort and runs at step 7, after
            # the mutation has already landed (post-propagate) — there is no
            # file+DB transaction to unwind, so we do NOT roll back. But a
            # write action whose action_results row fails to persist is a real
            # audit gap, not a benign miss: surface it LOUD (ERROR + greppable
            # AUDIT_GAP marker) so it is alertable, never silently swallowed.
            # The schema has no per-row failure mode (only action_type/ok are
            # NOT NULL and both are always supplied), so this fires only on DB
            # unavailability/serialization. On the autonomous path the
            # proposal's completion write shares that DB failure, leaving a
            # visibly-stuck proposal; CLI-direct is the governor-operated
            # residual. Reads stay a quiet best-effort warning.
            if write:
                logger.error(
                    "AUDIT_GAP: write action %s executed but its "
                    "core.action_results row failed to persist (%s) — mutation "
                    "stands, audit trail incomplete for this action (#634)",
                    definition.action_id,
                    e,
                )
            else:
                logger.warning("Non-blocking audit log failure (read): %s", e)

    # ID: eff3eded-b30d-49e0-b50c-3503a1b695af
    def _prepare_params(
        self,
        definition: ActionDefinition,
        write: bool,
        params: dict[str, Any],
        context: CoreContext | None = None,
    ) -> dict[str, Any]:
        """
        Prepare parameters for action execution with smart injection.

        `context` overrides the core_context injected into actions that
        accept it. None means use self.core_context (the default for
        unsandboxed pass-through); a scoped CoreContext is supplied by
        _build_execution_context when ADR-071 D2.2 sandboxing applies.
        """
        exec_params = {"write": write}
        effective_context = context if context is not None else self.core_context

        sig = inspect.signature(definition.executor)
        if "core_context" in sig.parameters:
            exec_params["core_context"] = effective_context

        exec_params.update(params)

        if definition.requires_db and not effective_context.db_available:
            logger.warning(
                "Action %s requires DB but it's not available", definition.action_id
            )

        if definition.requires_vectors and not effective_context.qdrant_service:
            logger.warning(
                "Action %s requires vectors but Qdrant is not available",
                definition.action_id,
            )

        return exec_params

    # ID: 118ed7f6-3a4f-4c31-b6a9-448727bbea76
    def list_actions(
        self, category: ActionCategory | None = None
    ) -> list[ActionDefinition]:
        """
        List available actions, optionally filtered by category.
        """
        if category:
            return self.registry.get_by_category(category)
        return self.registry.list_all()

    # ID: 46e53493-d92c-402d-83c8-b9516d394f81
    def get_action(self, action_id: str) -> ActionDefinition | None:
        """
        Get action definition by ID.
        """
        return self.registry.get(action_id)
