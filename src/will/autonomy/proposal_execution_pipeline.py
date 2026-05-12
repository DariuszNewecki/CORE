# src/will/autonomy/proposal_execution_pipeline.py
"""
ProposalExecutor pipeline-stage helpers.

Collaborator module for ProposalExecutor. Houses module-level async/sync
functions that implement each stage of the proposal execution pipeline
(pre-flight, claim, action loop, commit, consequence recording, rollback,
result envelope). Keeps ProposalExecutor a thin orchestrator and lets
execute_batch() share the same primitives as execute() instead of
inlining a parallel copy.

LAYER: will/autonomy — internal collaborator of ProposalExecutor. No
direct database access (uses service_registry like the orchestrator);
no file writes outside what the orchestrated atomic actions perform.
"""

from __future__ import annotations

import asyncio
from typing import Any

from body.services.service_registry import service_registry
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
        )
    except Exception as cons_err:
        logger.warning(
            "Failed to record consequence for %s: %s",
            proposal_id,
            cons_err,
        )


# ID: b38dbf84-ec1c-473d-8f42-d8b613e9a4c8
async def compute_changed_files(
    repo_path: str,
    pre_sha: str | None,
    post_sha: str | None,
    proposal_id: str,
) -> list[str]:
    """Return paths changed between two git SHAs, or [] on missing/failure.

    Runs ``git diff --name-only <pre> <post>`` in *repo_path*. Used by
    ProposalExecutor to record which files an executed proposal touched
    so the consequence log captures the actual diff (not just the
    declared scope.files). Returns [] if either SHA is missing or the
    subprocess call fails — non-fatal: consequence recording prefers
    incomplete data over a failed proposal completion.

    *proposal_id* is included for log attribution only.
    """
    if not (pre_sha and post_sha):
        return []
    try:
        diff_proc = await asyncio.create_subprocess_exec(
            "git",
            "diff",
            "--name-only",
            pre_sha,
            post_sha,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=repo_path,
        )
        stdout, _ = await diff_proc.communicate()
        return [f for f in stdout.decode().strip().splitlines() if f]
    except Exception as diff_err:
        logger.warning(
            "Could not determine changed files for %s: %s",
            proposal_id,
            diff_err,
        )
        return []


def rollback_proposal(
    git_service,
    proposal_id: str,
    scope_files: list[str],
    pre_sha: str | None,
) -> None:
    """Restore the working tree to pre-execution state after proposal failure.

    Reverts the proposal's declared scope.files via
    ``git_service.restore_paths``. No-op when *git_service* is None or
    *pre_sha* is None (nothing to restore to). Fail-soft: a rollback
    failure is logged at WARNING and swallowed — the proposal is already
    marked failed regardless.
    """
    if git_service is None or pre_sha is None:
        return
    try:
        git_service.restore_paths(scope_files)
        logger.info(
            "Reverted scope files for proposal %s (count=%d, sha=%s)",
            proposal_id,
            len(scope_files),
            pre_sha,
        )
    except Exception as rollback_err:
        logger.warning(
            "Rollback failed for proposal %s: %s",
            proposal_id,
            rollback_err,
        )


def commit_proposal_changes(
    git_service,
    proposal_id: str,
    proposal_goal: str,
    scope_files: list[str],
    action_results: dict[str, Any],
) -> None:
    """Commit the proposal's changes to git.

    Stages the declared scope.files plus anything actions reported in
    ``data['files_produced']`` (issue #297: fix.modularity writes new
    package files outside scope.files). Commits with message
    ``fix({proposal_id[:16]}): {goal}``.

    No-op when *git_service* is None.

    Fail-soft: the commit failing is advisory. Execution has already
    happened and the proposal row is already marked completed; we don't
    unwind that over a commit failure. Warning is logged, control
    returns normally.
    """
    if git_service is None:
        return
    try:
        paths_to_commit = sorted(set(scope_files) | _files_produced_by(action_results))
        git_service.commit_paths(
            paths_to_commit,
            f"fix({proposal_id[:16]}): {proposal_goal}",
        )
        logger.info("Git commit created for proposal %s", proposal_id)
    except Exception as git_err:
        logger.warning(
            "Git commit failed for proposal %s — changes applied but not committed: %s",
            proposal_id,
            git_err,
        )


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
