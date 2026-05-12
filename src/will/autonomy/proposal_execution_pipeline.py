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

from shared.logger import getLogger


logger = getLogger(__name__)


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
