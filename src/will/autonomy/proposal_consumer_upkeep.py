# src/will/autonomy/proposal_consumer_upkeep.py
"""
Pre-execution upkeep for ProposalConsumerWorker.

Before each cycle executes approved proposals, the worker fast-forwards
CORE's clone (ADR-132 D10 · D2) and delivers CORE's generated tests as a
pull request. Both post through the passed-in Worker so blackboard entries
carry Worker attribution per ADR-011.

Split out of will/workers/proposal_consumer_worker.py (modularity.needs_split,
#1280); the worker keeps thin _sync_upstream/_deliver_tests wrappers.
"""

from __future__ import annotations

import asyncio
from typing import Any

from shared.logger import getLogger


logger = getLogger(__name__)

# ADR-132 D10 · D2: one open finding while CORE's clone cannot follow upstream.
_SYNC_SUBJECT = "repo_sync::clone"
# One open finding while generated tests wait for a GitHub token to travel.
_DELIVERY_SUBJECT = "test_delivery::waiting"


# ID: 1e91f21d-3f29-4341-8b07-0741b166d694
async def sync_upstream(worker: Any, ctx: Any) -> None:
    """ADR-132 D10 · D2: fast-forward CORE's clone before executing.

    Inert while no upstream is configured. A sync that cannot proceed
    (diverged, failed, an interrupted sync it refuses to guess about)
    is one open finding for the governor, resolved once a later sync
    succeeds; CORE keeps working on its current HEAD meanwhile.
    """
    from body.infrastructure.repo_sync import (
        SyncOutcome,
        SyncRecoveryRefused,
        repo_sync_for,
    )
    from body.services.service_registry import service_registry

    outcome: SyncOutcome | None
    state: str
    reason: str | None
    try:
        outcome = await asyncio.to_thread(repo_sync_for(ctx).sync_if_free)
        state, reason = outcome.state, outcome.reason
    except SyncRecoveryRefused as exc:
        outcome, state, reason = None, "recovery_refused", str(exc)

    if state in ("disabled", "busy"):
        return
    blackboard = await service_registry.get_blackboard_service()
    open_rows = await blackboard.fetch_open_findings(
        prefix=f"{_SYNC_SUBJECT}%", limit=10
    )
    if state in ("diverged", "failed", "recovery_refused"):
        if not open_rows:
            await worker.post_finding(
                subject=_SYNC_SUBJECT,
                payload={
                    "state": state,
                    "reason": reason,
                    "from": outcome.from_sha if outcome else None,
                    "upstream": outcome.to_sha if outcome else None,
                    "message": (
                        "CORE's clone could not follow upstream; it keeps "
                        "working on its current HEAD until this is resolved."
                    ),
                },
                resolution_mechanism="human",
            )
        return
    if open_rows:
        await blackboard.resolve_entries([row["id"] for row in open_rows])
    if outcome is not None and (
        state == "fast_forwarded" or outcome.recovered is not None
    ):
        await worker.post_report(
            subject="proposal_consumer_worker.repo_sync",
            payload={
                "state": state,
                "from": outcome.from_sha,
                "to": outcome.to_sha,
                "recovered": outcome.recovered,
            },
        )


# ID: 2a3cc9a3-cfea-44b4-9d08-bf25adc9db2c
async def deliver_tests(worker: Any, ctx: Any) -> None:
    """CORE's generated tests reach GitHub as one pull request into main
    (body.infrastructure.delivery_branch). While they cannot (no token),
    one open finding says how many wait; it resolves once they travel.
    Never raises: delivery must not stop proposal execution.
    """
    from dataclasses import asdict

    from body.infrastructure.delivery_branch import DELIVERY_BRANCH, run_delivery
    from body.services.service_registry import service_registry

    try:
        outcome = await run_delivery(ctx)
        if outcome.state in ("none", "busy", "current") and not outcome.dropped:
            return
        blackboard = await service_registry.get_blackboard_service()
        open_rows = await blackboard.fetch_open_findings(
            prefix=f"{_DELIVERY_SUBJECT}%", limit=10
        )
        if outcome.state == "waiting":
            if not open_rows:
                await worker.post_finding(
                    subject=_DELIVERY_SUBJECT,
                    payload={
                        **asdict(outcome),
                        "branch": DELIVERY_BRANCH,
                        "message": (
                            f"{outcome.pending_commits} generated test "
                            f"commit(s) wait on CORE's branch {DELIVERY_BRANCH}; "
                            f"delivering them as a pull request {outcome.reason}."
                        ),
                    },
                    resolution_mechanism="human",
                )
            return
        if outcome.state in ("delivered", "nothing") and open_rows:
            await blackboard.resolve_entries([row["id"] for row in open_rows])
        if outcome.state in ("delivered", "failed") or outcome.dropped:
            await worker.post_report(
                subject="proposal_consumer_worker.test_delivery",
                payload=asdict(outcome),
            )
    except Exception as exc:
        logger.warning("ProposalConsumerWorker: test delivery failed: %s", exc)
