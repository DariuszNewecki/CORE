# src/will/autonomy/proposal_execution_pipeline.py
"""
ProposalExecutor pipeline-stage helpers.

Collaborator module for ProposalExecutor. Houses module-level async/sync
functions that implement each stage of the proposal execution pipeline
(pre-flight, claim, action loop, commit, consequence recording, rollback,
result envelope). Keeps ProposalExecutor a thin orchestrator over reusable
primitives.

LAYER: will/autonomy — internal collaborator of ProposalExecutor. No
direct database access (uses service_registry like the orchestrator);
no file writes outside what the orchestrated atomic actions perform.
"""

from __future__ import annotations

from typing import Any

from body.services.service_registry import service_registry
from shared.infrastructure.git_service import StagingContaminationError
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 41e70408-632f-4485-ba5f-23cfb688b53d
def capture_git_sha(git_service, phase: str, proposal_id: str) -> str | None:
    """Return the current git HEAD SHA, or None if unavailable.

    Wraps ``git_service.get_current_commit()``. Returns None when
    *git_service* is None or the call raises. *phase* ("pre" or "post")
    parametrises the log output:

    - ``"pre"`` logs an INFO line with the captured SHA on success
      (useful when a later proposal failure needs the working tree
      restored to this commit).
    - ``"post"`` is silent on success.

    Failures from either phase are logged at WARNING with the proposal_id
    and the exception. Fail-soft — proposal execution proceeds with a
    None SHA, downstream code (compute_changed_files, record_consequence)
    handles missing SHAs gracefully.
    """
    if git_service is None:
        return None
    try:
        sha = git_service.get_current_commit()
        if phase == "pre":
            logger.info("Pre-execution HEAD: %s", sha)
        return sha
    except Exception as sha_err:
        logger.warning(
            "Could not capture %s-execution SHA for %s: %s",
            phase,
            proposal_id,
            sha_err,
        )
        return None


# ID: 4de2ac6b-7733-45eb-81cf-2f2897095459
async def resolve_deferred_findings(proposal_id: str) -> None:
    """Flip findings deferred to *proposal_id* from 'deferred_to_proposal'
    to 'resolved' — the success-side mirror of §7a revival.

    Fail-soft: any error is logged and swallowed. The resolution step
    happens after a proposal has already been marked completed; failure
    here must not unwind completion. Logs an INFO when one or more
    findings are flipped; silent when there were none.
    """
    try:
        bb_service = await service_registry.get_blackboard_service()
        resolution = await bb_service.resolve_deferred_entries_for_completed_proposal(
            proposal_id
        )
        if resolution and resolution.get("resolved_count", 0) > 0:
            logger.info(
                "ProposalExecutor: resolved %d deferred finding(s) "
                "for completed proposal %s",
                resolution["resolved_count"],
                proposal_id,
            )
    except Exception as resolve_err:
        logger.warning(
            "Failed to resolve deferred findings for proposal %s: %s",
            proposal_id,
            resolve_err,
        )


# ID: 4095ae72-e22a-48bd-b8a0-41707a5b2bdf
async def record_consequence(
    proposal_id: str,
    pre_sha: str | None,
    post_sha: str | None,
    changed_files: list[str],
    finding_ids: list[str],
    policies: list[str],
    declared_production: list[str] | None = None,
) -> None:
    """Record the consequence log entry for a successfully executed proposal.

    Fail-soft: any exception during the consequence-service call is
    logged and swallowed. Consequence recording is observational —
    failure here must not unwind the proposal completion that has
    already been committed to the proposal-row state.

    *finding_ids* comes from
    ``proposal.constitutional_constraints['finding_ids']`` (the open
    findings this proposal was meant to resolve); *policies* comes from
    ``proposal.scope.policies`` (the rules that authorized the changes).

    ADR-129 D2: *declared_production* is the union of _sandbox_target_paths
    and files_produced computed by compute_production_set() — the same set
    that drove commit_paths(). Persisted so CommitAuthorshipAuditWorker can
    compare it against the actual git diff post-commit.
    """
    try:
        consequence_svc = await service_registry.get_consequence_log_service()
        await consequence_svc.record(
            proposal_id=proposal_id,
            pre_execution_sha=pre_sha,
            post_execution_sha=post_sha,
            files_changed=[{"path": p} for p in changed_files],
            findings_resolved=finding_ids,
            authorized_by_rules=policies,
            declared_production=declared_production or [],
        )
    except Exception as cons_err:
        logger.warning(
            "Failed to record consequence for %s: %s",
            proposal_id,
            cons_err,
        )


# ID: b38dbf84-ec1c-473d-8f42-d8b613e9a4c8
async def compute_changed_files(
    git_service,
    pre_sha: str | None,
    post_sha: str | None,
    proposal_id: str,
) -> list[str]:
    """Return paths changed between two git SHAs, or [] on missing/failure.

    Delegates to ``GitService.diff_file_names`` (ADR-129). Returns [] if
    either SHA is missing, *git_service* is None, or the git call fails —
    non-fatal: consequence recording prefers incomplete data over a failed
    proposal completion.

    *proposal_id* is included for log attribution only.
    """
    if not (pre_sha and post_sha) or git_service is None:
        return []
    try:
        result = await git_service.diff_file_names(pre_sha, post_sha)
        return result if result is not None else []
    except Exception as diff_err:
        logger.warning(
            "Could not determine changed files for %s: %s",
            proposal_id,
            diff_err,
        )
        return []


# ID: 550df549-9b2c-4adc-bf05-f33bce4defd0
def rollback_proposal(
    git_service,
    proposal_id: str,
    action_results: dict[str, Any],
    pre_sha: str | None,
) -> None:
    """Restore the action's production set after proposal failure.

    Per ADR-101 D3, rollback restores the same set that would have been
    committed on the success path — the paths the action's sandbox
    actually touched, not the proposal's permission scope. Restoring
    ``scope.files`` (the pre-ADR-101 behavior) would clobber concurrent
    architect edits on scope paths the action did not modify, which is
    the symmetric violation of D1: the rollback "speaks for" bytes the
    action did not author.

    Computes the production set the same way :func:`commit_proposal_changes`
    does and passes it to ``git_service.restore_paths``. No-op when
    *git_service* is None, *pre_sha* is None, or the production set is
    empty (sandbox-only writes that never reached the main tree need no
    rollback). Fail-soft: a rollback failure is logged at WARNING and
    swallowed — the proposal is already marked failed regardless.
    """
    if git_service is None or pre_sha is None:
        return
    try:
        production = compute_production_set(action_results)
        if not production:
            logger.debug(
                "Proposal %s produced no main-tree changes — nothing to rollback "
                "(ADR-101 D3)",
                proposal_id,
            )
            return
        git_service.restore_paths(production)
        logger.info(
            "Reverted production set for proposal %s (count=%d, sha=%s)",
            proposal_id,
            len(production),
            pre_sha,
        )
    except Exception as rollback_err:
        logger.warning(
            "Rollback failed for proposal %s: %s",
            proposal_id,
            rollback_err,
        )


# ID: a096add6-5be4-4917-b872-061674977646
def commit_proposal_changes(
    git_service,
    proposal_id: str,
    proposal_goal: str,
    action_results: dict[str, Any],
) -> bool:
    """Commit the proposal's actual production to git.

    Per ADR-101 D2, the commit set is derived from the action's actual
    production — the union of ``data['_sandbox_target_paths']`` (paths
    the SandboxLifecycle observed modified inside the hermetic worktree,
    stamped by ActionExecutor after successful propagate_changes) and
    ``data['files_produced']`` (paths the action explicitly declared as
    produced, the fix.modularity pattern from #297). The proposal's
    permission scope (``scope.files``) does NOT participate; it remains
    a permission boundary, not a production postcondition.

    Commits with message ``fix({proposal_id[:16]}): {goal}``. Returns
    ``True`` on success or when there is nothing to commit (empty
    production set). Returns ``False`` only when a
    ``StagingContaminationError`` (ADR-129 D1) blocks the commit;
    the executor uses this to route to ``mark_failed`` rather than
    ``mark_completed`` (ADR-129 D7).

    Other git errors (e.g. pre-commit hook unrecoverable failure) are
    still logged as warnings and return ``True`` — execution succeeded
    and the proposal is completed; only the git record is missing.
    ``StagingContaminationError`` is different because the commit was
    intentionally refused, not merely failed.
    """
    if git_service is None:
        return True
    try:
        paths_to_commit = compute_production_set(action_results)
        if not paths_to_commit:
            logger.info(
                "Proposal %s produced no changes — no commit emitted (ADR-101 D2)",
                proposal_id,
            )
            return True
        git_service.commit_paths(
            paths_to_commit,
            f"fix({proposal_id[:16]}): {proposal_goal}",
        )
        logger.info("Git commit created for proposal %s", proposal_id)
        return True
    except StagingContaminationError as d1_err:
        logger.warning(
            "Git commit REFUSED for proposal %s — ADR-129 D1 staging contamination: %s",
            proposal_id,
            d1_err,
        )
        return False
    except Exception as git_err:
        logger.warning(
            "Git commit failed for proposal %s — changes applied but not committed: %s",
            proposal_id,
            git_err,
        )
        return True


# ID: 6f3a8d9c-2b71-4a85-9e1c-7d2f8b4a6e09
def compute_production_set(action_results: dict[str, Any]) -> list[str]:
    """Union of paths the executed actions actually authored.

    Per ADR-101 D2 this is the authoritative production boundary; both
    the commit set (:func:`commit_proposal_changes`) and the rollback
    target (:func:`rollback_proposal`) derive from it. The proposal's
    permission scope (``scope.files``) is NOT included — that's a
    permission boundary, not a production postcondition.

    Sources unioned:

    - ``data['_sandbox_target_paths']`` — paths the SandboxLifecycle
      observed modified inside the hermetic worktree (ADR-071 D2.2).
      Stamped by ActionExecutor after a successful propagate_changes;
      absent when the action did not run sandboxed (CLI direct, dry-run,
      ``ActionImpact`` outside ``{WRITE_CODE, WRITE_METADATA}``).
    - ``data['files_produced']`` — paths the action explicitly declared
      as produced. The :mod:`fix.modularity` pattern (#297) writes new
      package files that exist outside any pre-declared scope; the
      action lists them here so they reach git.

    Non-string and empty entries are filtered out defensively so a
    malformed action result can't corrupt the git invocation.
    """
    produced: set[str] = set()
    for result in action_results.values():
        data = result.get("data") or {}
        for key in ("_sandbox_target_paths", "files_produced"):
            for path in data.get(key) or []:
                if isinstance(path, str) and path:
                    produced.add(path)
    return sorted(produced)
