# src/will/workers/proposal_consumer_effects.py
"""
ProposalConsumer post-execution side-effects.

Collaborator module for ProposalConsumerWorker. Translates ProposalExecutor
outcomes into blackboard side-effects:

- Success aftermath: forward each action's finding_to_post (ADR-011
  attribution), post `python::test.coverage::*` for each changed src/*.py file.

All posts flow through the passed-in Worker instance so attribution
(self._worker_uuid, self._phase) is correct per ADR-011 — these helpers
do not post on their own account.

ADR-101 D4 retired the pre-claim scope-collision check; the corresponding
yield-aftermath helper (`apply_yield_effects`) has been removed. Historical
`autonomy.yielded.scope_collision::*` entries remain on the blackboard for
audit-trail purposes and are still classified by the dashboard's Type A
filter.

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
       finding_to_post: forward it to the blackboard via
       worker.post_artifact_finding using the typed parameters carried by
       the action's finding_to_post dict (ADR-091 D5 Phase 6 — typed
       finding_to_post replaces the legacy {subject, payload} shape).
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
        artifact_type = finding_to_post.get("artifact_type")
        sub_namespace = finding_to_post.get("sub_namespace")
        identity_key_value = finding_to_post.get("identity_key_value")
        payload = finding_to_post.get("payload")
        if (
            not artifact_type
            or not sub_namespace
            or not identity_key_value
            or payload is None
        ):
            logger.warning(
                "Malformed finding_to_post from action %s "
                "(missing artifact_type/sub_namespace/identity_key_value/"
                "payload): %r",
                aid,
                finding_to_post,
            )
            continue
        try:
            await worker.post_artifact_finding(
                artifact_type=artifact_type,
                sub_namespace=sub_namespace,
                identity_key_value=identity_key_value,
                payload=payload,
            )
            logger.info(
                "ProposalConsumerWorker: posted finding %s::%s::%s from action %s",
                artifact_type,
                sub_namespace,
                identity_key_value,
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
