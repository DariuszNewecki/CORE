# src/will/workers/proposal_consumer_effects.py
"""
ProposalConsumer post-execution side-effects.

Collaborator module for ProposalConsumerWorker. Translates ProposalExecutor
outcomes into blackboard side-effects:

- Success aftermath: forward each action's finding_to_post (ADR-011
  attribution), post `python::test.coverage::*` for each changed src/*.py file.
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


# ID: c8e4f7a2-9b3d-4e1a-8c5f-2d6e9a1b3c4f
def summarize_flow_step_failures(
    action_results: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    """Extract optional-step failures from flow-kind action_results.

    ADR-046 D3b: surfaces silent auto-heal failures in the per-proposal
    entry of proposal_consumer_worker.run.complete. Only flow-kind entries
    are inspected; only steps with ok=False AND required=False contribute
    (required-step failures already sink the proposal and surface through
    the existing failure channel).
    """
    failures: list[dict[str, Any]] = []
    for ref_key, ar in (action_results or {}).items():
        if not isinstance(ar, dict) or ar.get("kind") != "flow":
            continue
        data = ar.get("data") or {}
        flow_id = data.get("flow_id") or ref_key.split(":", 1)[0]
        for step in data.get("steps") or []:
            if not isinstance(step, dict):
                continue
            if step.get("required", True) or step.get("ok", True):
                continue
            step_data = step.get("data") or {}
            failures.append(
                {
                    "flow_id": flow_id,
                    "step_ref_id": step.get("ref_id"),
                    "step_kind": step.get("kind"),
                    "step_error": step_data.get("error"),
                }
            )
    return failures


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
       sees it before any test-coverage entries for the same file
       (per the original ordering invariant from the worker's run loop).
    2. For each changed file ending in .py under src/: post a
       `python::test.coverage::<path>` finding (ADR-091 D2 canonical
       format) carrying the post-execution sha.

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
                # ADR-091 D2 canonical format. ProposalConsumerWorker is
                # class:acting (no declared mandate.scope.rule_namespace),
                # so post_artifact_finding's validation falls under the
                # Phase-1 transition allowance and emits the canonical
                # subject without raising.
                await worker.post_artifact_finding(
                    artifact_type="python",
                    sub_namespace="test.coverage",
                    identity_key_value=path,
                    payload={
                        "source_file": path,
                        "proposal_id": proposal_id,
                        "post_execution_sha": post_execution_sha,
                    },
                )
            except Exception as test_req_err:
                logger.warning(
                    "Could not post test.coverage finding for proposal %s: %s",
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
    yields a proposal rather than executing it (typically because the
    working tree is dirty under ADR-021 D5).

    Posted terminal-at-creation via post_observation(status='abandoned')
    per the observability-TTL fix (2026-05-25): no in-code resolver
    consumes these findings, so prior posts as status='open' accumulated
    forever and produced perpetual stale-alerts from
    BlackboardShopManager. The prior docstring's claim of "resolved when
    proposal completes/fails" was aspirational — only 57 rows have ever
    been resolved historically, all by manual SQL on 2026-05-12 (single
    governor-triggered purge). If a real proposal-completion resolver is
    implemented later, the contract here can be downgraded from
    terminal-at-creation back to open + lifecycle-linked.

    Idempotent by subject is no longer load-bearing now that emissions
    are terminal — a terminal entry never blocks fresh detection — but
    the dedup lookup is retained as a cheap guard against double-post
    races within a single consumer tick.

    Fail-soft: lookup or post errors are logged. On lookup failure we
    fall back to posting — better a duplicate than a silenced yield. The
    worker's run-loop accounting (yielded += 1) is not disturbed either
    way.
    """
    colliding = result.get("colliding_paths", []) or []
    yield_reason = result.get("yield_reason", "scope_collision")
    subject = f"autonomy.yielded.scope_collision::{proposal_id}"

    from body.services.service_registry import service_registry

    try:
        bb_service = await service_registry.get_blackboard_service()
        existing = await bb_service.fetch_open_finding_subjects_by_prefix(subject)
        if subject in existing:
            logger.info(
                "ProposalConsumerWorker: yield finding already open for "
                "proposal %s — skipping duplicate post",
                proposal_id,
            )
            return
    except Exception as lookup_err:
        logger.warning(
            "Yield-finding dedup lookup failed for proposal %s "
            "(falling back to post): %s",
            proposal_id,
            lookup_err,
        )

    try:
        await worker.post_observation(
            subject=subject,
            payload={
                "proposal_id": proposal_id,
                "goal": goal,
                "yield_reason": yield_reason,
                "colliding_paths": colliding,
            },
            status="abandoned",
        )
    except Exception as post_err:
        logger.warning(
            "Could not post yield finding for proposal %s: %s",
            proposal_id,
            post_err,
        )
