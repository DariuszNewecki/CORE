# src/will/autonomy/proposal_executor.py
"""
Proposal Executor - Execute approved proposals through ActionExecutor

Bridge between A3 proposals and the action execution system.

CONSTITUTIONAL (current):
- Will orchestrates execution flow.
- DB session acquisition is delegated to ServiceRegistry (in Body).
- ProposalRepository remains the DB abstraction for proposal persistence.
- This module does NOT import AsyncSession (architectural boundary).
"""

from __future__ import annotations

import asyncio
import time
from typing import Any
from uuid import UUID

from body.atomic.executor import ActionExecutor
from body.flows.executor import FlowExecutor
from body.services.service_registry import service_registry
from mind.governance.violation_report import extract_error_data
from shared.exceptions import GovernanceInstrumentError
from shared.infrastructure.intent.autonomy_dirty_tree import (
    load_autonomy_dirty_tree_policy,
)
from shared.infrastructure.intent.vocabulary_projection import (
    VocabularyProjectionError,
    load_vocabulary_projection,
)
from shared.logger import getLogger
from will.autonomy.proposal import ProposalStatus
from will.autonomy.proposal_repository import ProposalRepository
from will.autonomy.proposal_state_manager import ProposalStateManager


logger = getLogger(__name__)


def _files_produced_by(action_results: dict[str, Any]) -> set[str]:
    """Collect every path actions reported via ``data['files_produced']``.

    Some actions — notably ``fix.modularity`` — write new files outside
    the proposal's declared ``scope.files``. Each such action lists those
    paths in its ``ActionResult.data['files_produced']``. The commit step
    unions this set with the declared scope so new files land in git
    alongside the scope-declared edits. Issue #297.

    Non-string and empty entries are filtered out defensively so a
    malformed action result can't corrupt the git-add invocation.
    """
    produced: set[str] = set()
    for result in action_results.values():
        data = result.get("data") or {}
        for path in data.get("files_produced") or []:
            if isinstance(path, str) and path:
                produced.add(path)
    return produced


# ID: 69e9d2f1-3246-4a09-a5a8-fc0e1e882f47
class ProposalExecutor:
    """
    Executes approved proposals through ActionExecutor.

    Constitutional Note:
    - No AsyncSession import here (boundary rule).
    - Session is acquired via service_registry.session() (Body-owned mechanism).
    """

    def __init__(self, core_context):
        self.core_context = core_context
        self.action_executor = ActionExecutor(core_context)
        logger.debug("ProposalExecutor initialized")

    async def _check_scope_collision(self, proposal) -> dict | None:
        """
        Pre-claim scope-collision check per ADR-021 D5.

        Returns a yield result dict if the dirty working tree intersects
        proposal.scope.files (or, under any_dirty mode, if the working
        tree is dirty at all). Returns None if it is safe to proceed.

        Mode is read from .intent/enforcement/config/autonomy_dirty_tree.yaml.
        On loader sentinel, treats mode as any_dirty (conservative halt).
        """
        if self.core_context.git_service is None:
            return None

        policy = load_autonomy_dirty_tree_policy()
        if policy.get("_error"):
            logger.warning(
                "autonomy_dirty_tree policy unavailable (%s) — defaulting to any_dirty",
                policy.get("reason"),
            )
            mode = "any_dirty"
        else:
            mode = policy["mode"]

        try:
            porcelain = self.core_context.git_service.status_porcelain()
        except RuntimeError as status_err:
            logger.warning(
                "Could not read working-tree status — proceeding cautiously: %s",
                status_err,
            )
            return None

        dirty_paths: set[str] = set()
        for line in porcelain.splitlines():
            if len(line) < 4:
                continue
            path = line[3:]
            if " -> " in path:
                path = path.split(" -> ", 1)[1]
            if path:
                dirty_paths.add(path)

        if not dirty_paths:
            return None

        scope_files = set(proposal.scope.files)
        intersection = dirty_paths & scope_files

        if mode == "any_dirty" or intersection:
            colliding = (
                sorted(intersection)
                if mode == "intersection_only"
                else sorted(dirty_paths)
            )
            return {
                "ok": False,
                "yielded": True,
                "yield_reason": "scope_collision"
                if mode == "intersection_only"
                else "any_dirty",
                "colliding_paths": colliding,
                "proposal_id": proposal.proposal_id,
                "duration_sec": 0.0,
            }

        return None

    # ID: 5bb8175a-6a30-4548-8597-977a43fcb0b7
    async def execute(
        self,
        proposal_id: str,
        claimed_by: UUID,
        write: bool = False,
    ) -> dict[str, Any]:
        start_time = time.time()

        # DEGRADED pre-check (ADR-023 D4): refuse to execute proposals while
        # the vocabulary projection is broken. Caller (ProposalConsumerWorker)
        # should treat this as blocked, not failed — re-queue when restored.
        projection = load_vocabulary_projection()
        if isinstance(projection, VocabularyProjectionError):
            raise GovernanceInstrumentError(
                instrument="vocabulary_projection",
                reason=projection.reason,
            )

        async with service_registry.session() as session:
            repo = ProposalRepository(session)

            # 1. Load proposal
            logger.info("Loading proposal: %s", proposal_id)
            proposal = await repo.get(proposal_id)

            if not proposal:
                error = f"Proposal not found: {proposal_id}"
                logger.error(error)
                return {
                    "ok": False,
                    "error": error,
                    "duration_sec": time.time() - start_time,
                }

            logger.info(
                "Loaded proposal: %s (status=%s, actions=%d)",
                proposal.proposal_id,
                proposal.status.value,
                len(proposal.actions),
            )

            # 2. Validate status
            if proposal.status != ProposalStatus.APPROVED:
                error = f"Proposal not approved (status={proposal.status.value})"
                logger.error(error)
                return {
                    "ok": False,
                    "error": error,
                    "proposal_id": proposal.proposal_id,
                    "status": proposal.status.value,
                    "duration_sec": time.time() - start_time,
                }

            # Pre-claim scope-collision check (ADR-021 D5)
            collision = await self._check_scope_collision(proposal)
            if collision is not None:
                logger.info(
                    "Proposal %s yielded pre-claim: %s (colliding=%d)",
                    proposal.proposal_id,
                    collision["yield_reason"],
                    len(collision["colliding_paths"]),
                )
                return collision

            # 3. Mark as executing via claim.proposal atomic action (only if write=True)
            if write:
                state_manager = ProposalStateManager(session)
                claim_result = await self.action_executor.execute(
                    "claim.proposal",
                    proposal_id=proposal.proposal_id,
                    claimed_by=claimed_by,
                    write=write,
                )
                if not claim_result.ok:
                    return {
                        "ok": False,
                        "error": (
                            f"claim.proposal failed: "
                            f"{claim_result.data.get('error', 'rowcount=0')}"
                        ),
                        "proposal_id": proposal.proposal_id,
                        "duration_sec": time.time() - start_time,
                    }
            else:
                logger.info("DRY-RUN mode - not updating proposal status")

            # Capture pre-execution HEAD so we can restore the working tree on failure.
            pre_execution_sha = None
            if self.core_context.git_service:
                try:
                    pre_execution_sha = (
                        self.core_context.git_service.get_current_commit()
                    )
                    logger.info("Pre-execution HEAD: %s", pre_execution_sha)
                except Exception as sha_err:
                    logger.warning("Could not capture pre-execution SHA: %s", sha_err)

            changed_files: list[str] = []
            post_execution_sha: str | None = None
            failure_reason: str | None = None

            # 4. Execute actions in order
            action_results: dict[str, Any] = {}
            all_ok = True

            sorted_actions = sorted(proposal.actions, key=lambda a: a.order)

            logger.info("Executing %d actions...", len(sorted_actions))

            for action in sorted_actions:
                action_start = time.time()
                ref_id = action.ref_id
                ref_kind = action.ref_kind

                logger.info(
                    "Executing %s %d/%d: %s",
                    ref_kind,
                    action.order + 1,
                    len(sorted_actions),
                    ref_id,
                )

                try:
                    params = {
                        k: v for k, v in action.parameters.items() if k != "write"
                    }

                    if ref_kind == "flow":
                        flow_executor = FlowExecutor(self.core_context)
                        result = await flow_executor.execute(
                            flow_id=ref_id,
                            write=write,
                            **params,
                        )
                    else:
                        result = await self.action_executor.execute(
                            action_id=ref_id,
                            write=write,
                            **params,
                        )

                    action_duration = time.time() - action_start

                    action_results[f"{ref_id}:{action.order}"] = {
                        "ok": result.ok,
                        "duration_sec": action_duration,
                        "data": result.data,
                        "order": action.order,
                        "kind": ref_kind,
                    }

                    if not result.ok:
                        all_ok = False
                        logger.warning(
                            "%s %s failed: %s",
                            ref_kind.capitalize(),
                            ref_id,
                            (result.data or {}).get("error", "Unknown error"),
                        )
                    else:
                        logger.info(
                            "%s %s completed successfully (%.2fs)",
                            ref_kind.capitalize(),
                            ref_id,
                            action_duration,
                        )

                except Exception as e:
                    action_duration = time.time() - action_start
                    all_ok = False

                    logger.error(
                        "Exception executing %s %s: %s",
                        ref_kind,
                        ref_id,
                        e,
                        exc_info=True,
                    )

                    action_results[f"{ref_id}:{action.order}"] = {
                        "ok": False,
                        "duration_sec": action_duration,
                        "data": extract_error_data(e, error_type=type(e).__name__),
                        "order": action.order,
                        "kind": ref_kind,
                    }

            # 5. Update final status
            total_duration = time.time() - start_time

            if write:
                if all_ok:
                    await state_manager.mark_completed(
                        proposal.proposal_id,
                        results=action_results,
                    )
                    logger.info(
                        "Proposal completed successfully: %s (%.2fs)",
                        proposal.proposal_id,
                        total_duration,
                    )
                    # Git commit — stage the declared scope plus anything actions
                    # reported as produced (#297: fix.modularity writes new package
                    # files outside scope.files). Failure is advisory: execution
                    # already happened, we don't unwind it over a commit failure.
                    if self.core_context.git_service:
                        try:
                            paths_to_commit = sorted(
                                set(proposal.scope.files)
                                | _files_produced_by(action_results)
                            )
                            self.core_context.git_service.commit_paths(
                                paths_to_commit,
                                f"fix({proposal.proposal_id[:16]}): {proposal.goal}",
                            )
                            logger.info(
                                "Git commit created for proposal %s",
                                proposal.proposal_id,
                            )
                        except Exception as git_err:
                            logger.warning(
                                "Git commit failed for proposal %s — changes applied "
                                "but not committed: %s",
                                proposal.proposal_id,
                                git_err,
                            )

                    # -- Consequence recording --
                    # Delegated to ConsequenceLogService (Body layer).
                    try:
                        post_execution_sha = (
                            self.core_context.git_service.get_current_commit()
                            if self.core_context.git_service
                            else None
                        )
                    except Exception:
                        post_execution_sha = None
                        logger.warning(
                            "Could not capture post-execution SHA for %s",
                            proposal.proposal_id,
                        )

                    changed_files = []
                    if pre_execution_sha and post_execution_sha:
                        try:
                            diff_proc = await asyncio.create_subprocess_exec(
                                "git",
                                "diff",
                                "--name-only",
                                pre_execution_sha,
                                post_execution_sha,
                                stdout=asyncio.subprocess.PIPE,
                                stderr=asyncio.subprocess.PIPE,
                                cwd=str(self.core_context.git_service.repo_path),
                            )
                            stdout, _ = await diff_proc.communicate()
                            changed_files = [
                                f for f in stdout.decode().strip().splitlines() if f
                            ]
                        except Exception as diff_err:
                            logger.warning(
                                "Could not determine changed files for %s: %s",
                                proposal.proposal_id,
                                diff_err,
                            )

                    try:
                        consequence_svc = (
                            await service_registry.get_consequence_log_service()
                        )
                        await consequence_svc.record(
                            proposal_id=proposal.proposal_id,
                            pre_execution_sha=pre_execution_sha,
                            post_execution_sha=post_execution_sha,
                            files_changed=[{"path": p} for p in changed_files],
                            findings_resolved=proposal.constitutional_constraints.get(
                                "finding_ids", []
                            ),
                            authorized_by_rules=proposal.scope.policies,
                        )
                    except Exception as cons_err:
                        logger.warning(
                            "Failed to record consequence for %s: %s",
                            proposal.proposal_id,
                            cons_err,
                        )

                    # Success-side mirror of §7a revival: flip findings
                    # deferred to this proposal to 'resolved'. Failure of
                    # the resolution step must not unwind completion.
                    try:
                        bb_service = await service_registry.get_blackboard_service()
                        resolution = await bb_service.resolve_deferred_entries_for_completed_proposal(
                            proposal.proposal_id
                        )
                        if resolution and resolution.get("resolved_count", 0) > 0:
                            logger.info(
                                "ProposalExecutor: resolved %d deferred finding(s) "
                                "for completed proposal %s",
                                resolution["resolved_count"],
                                proposal.proposal_id,
                            )
                    except Exception as resolve_err:
                        logger.warning(
                            "Failed to resolve deferred findings for proposal %s: %s",
                            proposal.proposal_id,
                            resolve_err,
                        )

                else:
                    failed_actions = [
                        aid for aid, res in action_results.items() if not res["ok"]
                    ]
                    reason = f"Actions failed: {', '.join(failed_actions)}"
                    failure_reason = reason
                    await state_manager.mark_failed(
                        proposal.proposal_id, reason=reason, results=action_results
                    )
                    logger.error(
                        "Proposal failed: %s - %s", proposal.proposal_id, reason
                    )
                    # Restore the working tree to pre-execution state.
                    if self.core_context.git_service and pre_execution_sha is not None:
                        try:
                            self.core_context.git_service.restore_paths(
                                proposal.scope.files
                            )
                            logger.info(
                                "Reverted scope files to pre-execution state (count=%d, sha=%s)",
                                len(proposal.scope.files),
                                pre_execution_sha,
                            )
                        except Exception as rollback_err:
                            logger.warning(
                                "Rollback failed for proposal %s: %s",
                                proposal.proposal_id,
                                rollback_err,
                            )
            else:
                logger.info("DRY-RUN complete - no status updates")

            # 6. Return results
            return {
                "ok": all_ok,
                "proposal_id": proposal.proposal_id,
                "goal": proposal.goal,
                "write": write,
                "actions_executed": len(action_results),
                "actions_succeeded": sum(1 for r in action_results.values() if r["ok"]),
                "actions_failed": sum(
                    1 for r in action_results.values() if not r["ok"]
                ),
                "action_results": action_results,
                "changed_files": changed_files,
                "post_execution_sha": post_execution_sha,
                "failure_reason": failure_reason,
                "duration_sec": total_duration,
            }

    # ID: 5e4800f3-ea82-483c-9ecb-1a27a43e516d
    async def execute_batch(
        self,
        proposal_ids: list[str],
        claimed_by: UUID,
        write: bool = False,
    ) -> dict[str, Any]:
        """
        DORMANT — no production callers as of 2026-05-02. Preserved as an
        intentional batch-processing design feature. When activated, the
        calling worker must add §7a revival orchestration per ADR-011:
        revive_findings_for_failed_proposal + post revival report via
        self.post_report() for each failed proposal. Do not wire a caller
        without adding that orchestration.
        """
        start_time = time.time()
        results: dict[str, Any] = {}

        logger.info("Executing batch of %d proposals...", len(proposal_ids))

        # Single session reused for the whole batch
        async with service_registry.session() as session:
            repo = ProposalRepository(session)

            for proposal_id in proposal_ids:
                try:
                    # Inline execute logic but reusing the same session/repo
                    single_start = time.time()

                    proposal = await repo.get(proposal_id)
                    if not proposal:
                        results[proposal_id] = {
                            "ok": False,
                            "error": f"Proposal not found: {proposal_id}",
                            "duration_sec": time.time() - single_start,
                        }
                        continue

                    if proposal.status != ProposalStatus.APPROVED:
                        results[proposal_id] = {
                            "ok": False,
                            "error": f"Proposal not approved (status={proposal.status.value})",
                            "proposal_id": proposal.proposal_id,
                            "status": proposal.status.value,
                            "duration_sec": time.time() - single_start,
                        }
                        continue

                    # Pre-claim scope-collision check (ADR-021 D5)
                    collision = await self._check_scope_collision(proposal)
                    if collision is not None:
                        logger.info(
                            "Proposal %s yielded pre-claim: %s (colliding=%d)",
                            proposal.proposal_id,
                            collision["yield_reason"],
                            len(collision["colliding_paths"]),
                        )
                        results[proposal_id] = collision
                        continue

                    if write:
                        state_manager = ProposalStateManager(session)
                        claim_result = await self.action_executor.execute(
                            "claim.proposal",
                            proposal_id=proposal.proposal_id,
                            claimed_by=claimed_by,
                            write=write,
                        )
                        if not claim_result.ok:
                            results[proposal_id] = {
                                "ok": False,
                                "error": (
                                    f"claim.proposal failed: "
                                    f"{claim_result.data.get('error', 'rowcount=0')}"
                                ),
                                "proposal_id": proposal.proposal_id,
                                "duration_sec": time.time() - single_start,
                            }
                            continue

                    pre_execution_sha = None
                    if self.core_context.git_service:
                        try:
                            pre_execution_sha = (
                                self.core_context.git_service.get_current_commit()
                            )
                        except Exception as sha_err:
                            logger.warning(
                                "Could not capture pre-execution SHA for batch proposal %s: %s",
                                proposal.proposal_id,
                                sha_err,
                            )

                    changed_files: list[str] = []
                    post_execution_sha: str | None = None
                    failure_reason: str | None = None

                    action_results: dict[str, Any] = {}
                    all_ok = True
                    sorted_actions = sorted(proposal.actions, key=lambda a: a.order)

                    for action in sorted_actions:
                        action_start = time.time()
                        ref_id = action.ref_id
                        ref_kind = action.ref_kind

                        try:
                            params = {
                                k: v
                                for k, v in action.parameters.items()
                                if k != "write"
                            }

                            if ref_kind == "flow":
                                flow_executor = FlowExecutor(self.core_context)
                                r = await flow_executor.execute(
                                    flow_id=ref_id,
                                    write=write,
                                    **params,
                                )
                                step_ok = r.ok
                                step_data = r.data
                            else:
                                r = await self.action_executor.execute(
                                    action_id=ref_id,
                                    write=write,
                                    **params,
                                )
                                step_ok = r.ok
                                step_data = r.data

                            action_results[f"{ref_id}:{action.order}"] = {
                                "ok": step_ok,
                                "duration_sec": time.time() - action_start,
                                "data": step_data,
                                "order": action.order,
                                "kind": ref_kind,
                            }
                            if not step_ok:
                                all_ok = False
                        except Exception as e:
                            all_ok = False
                            action_results[f"{ref_id}:{action.order}"] = {
                                "ok": False,
                                "duration_sec": time.time() - action_start,
                                "data": {
                                    "error": str(e),
                                    "error_type": type(e).__name__,
                                },
                                "order": action.order,
                                "kind": ref_kind,
                            }

                    if write:
                        if all_ok:
                            await state_manager.mark_completed(
                                proposal.proposal_id,
                                results=action_results,
                            )
                            # Git commit per proposal in batch — same advisory
                            # semantics as single execute: log warning, don't unwind.
                            # #297: union scope with files_produced so new files
                            # land in git alongside scope-declared edits.
                            if self.core_context.git_service:
                                try:
                                    paths_to_commit = sorted(
                                        set(proposal.scope.files)
                                        | _files_produced_by(action_results)
                                    )
                                    self.core_context.git_service.commit_paths(
                                        paths_to_commit,
                                        f"fix({proposal.proposal_id[:16]}): {proposal.goal}",
                                    )
                                except Exception as git_err:
                                    logger.warning(
                                        "Git commit failed for batch proposal %s: %s",
                                        proposal.proposal_id,
                                        git_err,
                                    )
                            # -- Consequence recording --
                            try:
                                post_execution_sha = (
                                    self.core_context.git_service.get_current_commit()
                                    if self.core_context.git_service
                                    else None
                                )
                            except Exception:
                                post_execution_sha = None
                                logger.warning(
                                    "Could not capture post-execution SHA for batch proposal %s",
                                    proposal.proposal_id,
                                )

                            changed_files = []
                            if pre_execution_sha and post_execution_sha:
                                try:
                                    diff_proc = await asyncio.create_subprocess_exec(
                                        "git",
                                        "diff",
                                        "--name-only",
                                        pre_execution_sha,
                                        post_execution_sha,
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE,
                                        cwd=str(
                                            self.core_context.git_service.repo_path
                                        ),
                                    )
                                    stdout, _ = await diff_proc.communicate()
                                    changed_files = [
                                        f
                                        for f in stdout.decode().strip().splitlines()
                                        if f
                                    ]
                                except Exception as diff_err:
                                    logger.warning(
                                        "Could not determine changed files for batch proposal %s: %s",
                                        proposal.proposal_id,
                                        diff_err,
                                    )

                            try:
                                consequence_svc = (
                                    await service_registry.get_consequence_log_service()
                                )
                                await consequence_svc.record(
                                    proposal_id=proposal.proposal_id,
                                    pre_execution_sha=pre_execution_sha,
                                    post_execution_sha=post_execution_sha,
                                    files_changed=[{"path": p} for p in changed_files],
                                    findings_resolved=proposal.constitutional_constraints.get(
                                        "finding_ids", []
                                    ),
                                    authorized_by_rules=proposal.scope.policies,
                                )
                            except Exception as cons_err:
                                logger.warning(
                                    "Failed to record consequence for batch proposal %s: %s",
                                    proposal.proposal_id,
                                    cons_err,
                                )

                        else:
                            failed_actions = [
                                aid
                                for aid, res in action_results.items()
                                if not res["ok"]
                            ]
                            reason = f"Actions failed: {', '.join(failed_actions)}"
                            failure_reason = reason
                            await state_manager.mark_failed(
                                proposal.proposal_id,
                                reason=reason,
                                results=action_results,
                            )
                            if (
                                self.core_context.git_service
                                and pre_execution_sha is not None
                            ):
                                try:
                                    self.core_context.git_service.restore_paths(
                                        proposal.scope.files
                                    )
                                    logger.info(
                                        "Reverted scope files for batch proposal %s (count=%d, sha=%s)",
                                        proposal.proposal_id,
                                        len(proposal.scope.files),
                                        pre_execution_sha,
                                    )
                                except Exception as rollback_err:
                                    logger.warning(
                                        "Rollback failed for batch proposal %s: %s",
                                        proposal.proposal_id,
                                        rollback_err,
                                    )

                    results[proposal_id] = {
                        "ok": all_ok,
                        "proposal_id": proposal.proposal_id,
                        "goal": proposal.goal,
                        "write": write,
                        "actions_executed": len(action_results),
                        "actions_succeeded": sum(
                            1 for r in action_results.values() if r["ok"]
                        ),
                        "actions_failed": sum(
                            1 for r in action_results.values() if not r["ok"]
                        ),
                        "action_results": action_results,
                        "changed_files": changed_files,
                        "post_execution_sha": post_execution_sha,
                        "failure_reason": failure_reason,
                        "duration_sec": time.time() - single_start,
                    }

                except Exception as e:
                    logger.error(
                        "Batch execution failed for %s: %s",
                        proposal_id,
                        e,
                        exc_info=True,
                    )
                    results[proposal_id] = {
                        "ok": False,
                        "error": str(e),
                        "error_type": type(e).__name__,
                    }

        total_duration = time.time() - start_time
        succeeded = sum(1 for r in results.values() if r.get("ok", False))
        failed = len(results) - succeeded

        logger.info(
            "Batch execution complete: %d succeeded, %d failed (%.2fs)",
            succeeded,
            failed,
            total_duration,
        )

        return {
            "ok": failed == 0,
            "total": len(proposal_ids),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
            "duration_sec": total_duration,
        }
