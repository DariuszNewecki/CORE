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

import dataclasses
import inspect
import json
import time
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

from body.atomic.registry import ActionCategory, ActionDefinition, action_registry
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action
from shared.governance_token import authorize_execution
from shared.infrastructure.intent.action_risk import load_action_risk
from shared.logger import _current_run_id, getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)

# ADR-071 D2.2 Phase 2: action impacts that warrant hermetic worktree
# sandboxing. WRITE_DATA targets databases/external systems (not the
# source tree), so the worktree isolation does nothing for it.
_SANDBOXED_IMPACTS = frozenset({ActionImpact.WRITE_CODE, ActionImpact.WRITE_METADATA})


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

        # Overlay impact_level from .intent/enforcement/config/action_risk.yaml
        # onto every registered ActionDefinition. @register_action no longer
        # accepts impact_level — it is governed externally. See ADR-008.
        risk_mapping = load_action_risk()
        self.registry.apply_risk_config(risk_mapping)

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
        exec_context, scoped_git = self._build_execution_context(
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
                self._propagate_sandbox_changes(scoped_git)

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

    # ID: a9b3e7c1-4d2f-4e85-9a17-6b8c3d5e7f12
    def _build_execution_context(
        self,
        definition: ActionDefinition,
        write: bool,
        pre_execution_sha: str | None,
    ) -> tuple[CoreContext, Any]:
        """Decide whether to sandbox this execution and build the context.

        Returns (context_to_pass_to_action, scoped_git_or_None). When
        sandboxing applies, the returned context is a shallow copy of
        self.core_context with `git_service` and `file_handler` repointed
        at a fresh ScopedGitService rooted at `pre_execution_sha`. The
        caller MUST call `scoped_git.cleanup()` in a finally block.

        Gate (all required):
          - pre_execution_sha is not None (autonomous call path)
          - write is True (dry-runs need no isolation)
          - the action's @atomic_action metadata declares impact ∈
            {WRITE_CODE, WRITE_METADATA}

        Note on IntentGuard: the FileHandler constructor wires an
        IntentGuard via get_intent_guard(), which is a process singleton
        bound to the first repo_path it sees. A scoped FileHandler reuses
        that singleton — paths are still validated against governance,
        but using main-repo .intent/ state (the current governance frame)
        rather than the worktree's snapshot. That's the correct default:
        we want to honour governance as-of-now, not as-of-proposal.
        """
        if (
            pre_execution_sha is None
            or not write
            or self.core_context.git_service is None
        ):
            return self.core_context, None

        metadata = getattr(definition.executor, "_atomic_action_metadata", None)
        if metadata is None or metadata.impact not in _SANDBOXED_IMPACTS:
            return self.core_context, None

        from shared.infrastructure.storage.file_handler import FileHandler

        scoped_git = self.core_context.git_service.create_worktree(pre_execution_sha)
        try:
            scoped_file_handler = FileHandler(str(scoped_git.repo_path))
        except Exception:
            scoped_git.cleanup()
            raise

        scoped_context = dataclasses.replace(
            self.core_context,
            git_service=scoped_git,
            file_handler=scoped_file_handler,
        )
        logger.info(
            "ActionExecutor: %s sandboxed in %s at sha %s",
            definition.action_id,
            scoped_git.repo_path,
            pre_execution_sha[:12],
        )
        return scoped_context, scoped_git

    # ID: b1d2c5f9-3a48-4e67-8b91-2c5f8a3d6e90
    def _propagate_sandbox_changes(self, scoped_git: Any) -> None:
        """Copy files modified inside the sandbox back to the main tree.

        Walks `scoped_git.status_porcelain()` and for each modified or
        untracked entry, copies the worktree-side bytes through the main
        FileHandler's write_runtime_bytes surface (canonical write path,
        no re-syntax-check, no auto-newline injection — byte-identical).

        Before copying anything, checks the main tree for uncommitted
        modifications in the sandbox's target paths. If any overlap, raises
        — the exception bubbles into execute()'s outer try and turns the
        action result into a loud failure, rather than silently overwriting
        the governor's concurrent edits. This is the safety mechanism the
        ADR-071 D2.2 plan describes as "loud failure rather than silent
        contamination". The b11f4dba race shape is closed: worker either
        propagates cleanly (no overlap) or refuses (overlap detected).

        Deletions are not propagated: the no_direct_writes rule (#451)
        forbids @atomic_action functions from invoking unlink/rmdir, so
        a `D`-status entry here would itself be a constitutional
        violation. We log and skip rather than silently deleting from
        the main tree.
        """
        sandbox_root = scoped_git.repo_path
        file_handler = self.core_context.file_handler

        try:
            porcelain = scoped_git.status_porcelain()
        except Exception as exc:
            logger.error(
                "ActionExecutor: sandbox status read failed (%s); "
                "main tree NOT updated to avoid partial propagation",
                exc,
            )
            return

        if not porcelain:
            logger.debug(
                "ActionExecutor: sandbox produced no changes for %s", sandbox_root
            )
            return

        # Collect intended target paths. Porcelain v1 format is "XY path"
        # but GitService.status_porcelain strips the wrapping stdout, which
        # eats the leading space of the first line when X (staged) is
        # unmodified — so " M foo" arrives as "M foo". Split on first
        # whitespace to recover {status_token, path} regardless.
        target_paths: set[str] = set()
        for line in porcelain.splitlines():
            parts = line.split(None, 1)
            if len(parts) != 2:
                continue
            status_token, rel = parts[0], parts[1].strip().strip('"')
            if "D" in status_token:
                logger.warning(
                    "ActionExecutor: sandbox reports deletion of %s — "
                    "atomic actions cannot delete files (#451); skipping",
                    rel,
                )
                continue
            target_paths.add(rel)

        if not target_paths:
            return

        # Conflict check: is the main tree dirty on any target path?
        try:
            main_porcelain = self.core_context.git_service.status_porcelain()
        except Exception as exc:
            logger.error(
                "ActionExecutor: main tree status read failed (%s); "
                "refusing to propagate without a conflict check",
                exc,
            )
            raise RuntimeError(
                f"ADR-071 D2.2: cannot verify main tree cleanliness ({exc}); "
                "refusing to propagate sandbox changes"
            ) from exc

        main_dirty: set[str] = set()
        for line in main_porcelain.splitlines():
            parts = line.split(None, 1)
            if len(parts) == 2:
                main_dirty.add(parts[1].strip().strip('"'))

        conflict = sorted(target_paths & main_dirty)
        if conflict:
            raise RuntimeError(
                "ADR-071 D2.2: refusing to propagate sandbox changes — "
                f"main tree has uncommitted changes in {len(conflict)} "
                f"sandbox target file(s): {conflict[:5]}"
                f"{' ...' if len(conflict) > 5 else ''}. "
                "Commit or revert those changes, then re-run."
            )

        copied = 0
        for rel in sorted(target_paths):
            src = sandbox_root / rel
            if not src.exists():
                logger.warning(
                    "ActionExecutor: sandbox entry %s missing on disk; skipping",
                    rel,
                )
                continue
            file_handler.write_validated_bytes(rel, src.read_bytes())
            copied += 1

        logger.info(
            "ActionExecutor: propagated %d file(s) from sandbox to main tree",
            copied,
        )

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
        DELIBERATE STUB — NOT AN OVERSIGHT.

        Inline authorization is intentionally deferred. Enforcement is
        delegated to the audit → consequence chain loop (ADR-015,
        ADR-017, ADR-019). This method will be hardened when the
        enforcement loop has produced sufficient ViolationExecutor
        discovery data to define meaningful authorization policies.

        Fill point: this method, single location. Interface contract is
        already in place; only the policy evaluation body is missing.
        """
        if definition.impact_level == "dangerous" and write:
            logger.warning(
                "Dangerous action %s requested in write mode — "
                "authorization enforcement deferred to audit loop",
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
            logger.warning("Non-blocking audit log failure: %s", e)

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
