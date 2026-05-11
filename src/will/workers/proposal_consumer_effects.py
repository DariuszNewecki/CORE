# src/will/workers/proposal_consumer_effects.py
"""
ProposalConsumer post-execution side-effects.

Collaborator module for ProposalConsumerWorker. Translates ProposalExecutor
outcomes into blackboard side-effects:

- Success aftermath: forward each action's finding_to_post (ADR-011
  attribution), post test.run_required for each changed src/*.py file.
- Yield aftermath: post the scope_collision finding so a downstream worker
  can observe the yield.

All posts flow through the passed-in Worker instance so attribution
(self._worker_uuid, self._phase) is correct per ADR-011 — these helpers
do not post on their own account.

LAYER: will/workers — internal collaborator of ProposalConsumerWorker.
No database access, no file writes, no LLM calls.
"""

from __future__ import annotations

from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)


# ID: 2b90edbd-f8b8-4d76-8350-3780ad6a2340
async def apply_success_effects(
    worker: Worker,
    proposal_id: str,
    result: dict[str, Any],
) -> None:
    """
    Post the blackboard entries that follow a successful proposal execution.

    Two emissions, in order:

    1. For each successful action whose ActionResult carried a
       finding_to_post: forward it to the blackboard via worker.post_finding.
       Runs first so a downstream worker reacting to the posted finding
       sees it before any test.run_required entries for the same file
       (per the original ordering invariant from the worker's run loop).
    2. For each changed file ending in .py under src/: post a
       test.run_required::<path> finding carrying the post-execution sha.

    Malformed or post-time errors are logged and swallowed — matches the
    pre-split fail-soft semantics so a single bad finding does not reverse
    the success accounting in the worker's run loop.
    """
    action_results = result.get("action_results", {}) or {}
    for aid, ar in action_results.items():
        if not ar.get("ok"):
            continue
        ar_data = ar.get("data") or {}
        finding_to_post = ar_data.get("finding_to_post")
        if not finding_to_post:
            continue
        subject = finding_to_post.get("subject")
        payload = finding_to_post.get("payload")
        if not subject or payload is None:
            logger.warning(
                "Malformed finding_to_post from action %s "
                "(missing subject/payload): %r",
                aid,
                finding_to_post,
            )
            continue
        try:
            await worker.post_finding(subject=subject, payload=payload)
            logger.info(
                "ProposalConsumerWorker: posted finding %s from action %s",
                subject,
                aid,
            )
        except Exception as post_err:
            logger.warning(
                "Could not post finding_to_post from action %s: %s",
                aid,
                post_err,
            )

    changed_files = result.get("changed_files", []) or []
    post_execution_sha = result.get("post_execution_sha")
    for path in changed_files:
        if path.startswith("src/") and path.endswith(".py"):
            try:
                await worker.post_finding(
                    subject=f"test.run_required::{path}",
                    payload={
                        "source_file": path,
                        "proposal_id": proposal_id,
                        "post_execution_sha": post_execution_sha,
                    },
                )
            except Exception as test_req_err:
                logger.warning(
                    "Could not post test.run_required for proposal %s: %s",
                    proposal_id,
                    test_req_err,
                )


# ID: 19c42f70-4275-4635-8df9-6568dfabf7a1
async def apply_yield_effects(
    worker: Worker,
    proposal_id: str,
    goal: str,
    result: dict[str, Any],
) -> None:
    """
    Post the autonomy.yielded.scope_collision finding when ProposalExecutor
    yields a proposal rather than executing it (typically because another
    in-flight proposal has overlapping scope).

    Fail-soft: a posting error is logged and swallowed so the worker's
    run-loop accounting (yielded += 1) is not disturbed.
    """
    colliding = result.get("colliding_paths", []) or []
    yield_reason = result.get("yield_reason", "scope_collision")
    try:
        await worker.post_finding(
            subject=f"autonomy.yielded.scope_collision::{proposal_id}",
            payload={
                "proposal_id": proposal_id,
                "goal": goal,
                "yield_reason": yield_reason,
                "colliding_paths": colliding,
            },
        )
    except Exception as post_err:
        logger.warning(
            "Could not post yield finding for proposal %s: %s",
            proposal_id,
            post_err,
        )
