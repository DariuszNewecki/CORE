# src/body/services/blackboard_service/blackboard_proposal_service.py
# blackboard_proposal_service.py
"""Proposal-lifecycle methods that implement the finding↔proposal contract per CORE-Finding.md §7/§7a"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: f83444e2-fae1-46f0-a704-d592d62a116e
class BlackboardProposalService:
    # ID: 7f2a3c51-b9d0-48e4-9d2b-4a6f1e8c0b52
    async def defer_entries_to_proposal(
        self, entry_ids: list[str], proposal_id: str
    ) -> int:
        """
        Transition findings to 'deferred_to_proposal' terminal status and
        write the proposal_id into each finding's payload.

        Implements CORE-Finding.md §7 row 4:
          > The rule has an active RemediationMap entry. A Proposal has been
          > created. The `proposal_id` field in the payload MUST be set to
          > the created Proposal's ID.

        Only transitions entries currently in 'open' or 'claimed' — matches
        the predicate used by resolve_entries. Entries in any other status
        are left untouched and not counted.

        Sets resolved_at because 'deferred_to_proposal' is terminal per
        the blackboard_entry_status enum declaration in
        .intent/META/enums.json.

        Payload merge uses the 'payload = payload || jsonb_build_object(...)'
        idiom already established elsewhere in this service. If an earlier
        proposal_id was written (e.g. in unusual retry flows), this call
        overwrites it with the current value — last-writer-wins, which
        matches the semantic "this finding is now linked to THIS proposal."

        Returns the count of rows actually updated.

        Covers:
          - ViolationRemediatorWorker._defer_to_proposal
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import ServiceRegistry

        deferred_count = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'deferred_to_proposal',
                                resolved_at = now(),
                                updated_at = now(),
                                payload = payload || jsonb_build_object(
                                    'proposal_id', cast(:proposal_id as text)
                                )
                            WHERE id = cast(:entry_id as uuid)
                              AND status IN ('open', 'claimed')
                            """
                        ),
                        {"entry_id": entry_id, "proposal_id": proposal_id},
                    )
                    deferred_count += result.rowcount
        return deferred_count

    # ID: 96677af7-969f-4c5b-8271-87bf885b1d33
    async def defer_delegated_finding_to_proposal(
        self, entry_id: str, proposal_id: str
    ) -> int:
        """
        Defer a DELEGATED finding to an assisted-lane proposal (ADR-109 D4).

        The assisted-lane analogue of ``defer_entries_to_proposal``. A
        delegated finding lives at ``status='indeterminate'`` with
        ``resolution_mechanism='human'`` — the governor-inbox predicate — NOT
        at 'open'/'claimed'. The autonomous defer predicate would therefore
        silently match zero rows on it. This method owns the
        delegated→deferred transition for the lane so the assisted and
        autonomous paths stay distinct surfaces (the autonomous
        ``defer_entries_to_proposal`` predicate is left untouched).

        Writes ``proposal_id`` into the finding payload (CORE-Finding §7 row 4)
        and moves the finding out of the governor inbox into
        'deferred_to_proposal' (tracked, not parked). On proposal reject the
        lane revives it back to ``indeterminate+human`` (ADR-109 D4, ADR-010
        §7a) rather than the autonomous ``awaiting_reaudit`` path.

        Returns the count of rows actually updated (0 or 1).
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'deferred_to_proposal',
                            resolved_at = now(),
                            updated_at = now(),
                            payload = payload || jsonb_build_object(
                                'proposal_id', cast(:proposal_id as text)
                            )
                        WHERE id = cast(:entry_id as uuid)
                          AND status = 'indeterminate'
                          AND resolution_mechanism = 'human'
                        """
                    ),
                    {"entry_id": entry_id, "proposal_id": proposal_id},
                )
                return result.rowcount

    # ID: 6b658019-7399-466b-bfc9-642f144cc03a
    async def claim_delegated_finding(self, entry_id: str, agent: str) -> int:
        """Mark a delegated finding as being worked by an external agent (ADR-109 §2).

        Claiming is a sub-state of 'delegated', not a status transition: the
        finding stays at ``indeterminate+human`` (still in the governor inbox /
        lane queue per the D4 lifecycle — ``indeterminate+human`` → agent claims
        and submits → ``deferred_to_proposal``), so the queue predicate is
        unchanged. We only stamp ``lane_claimed_by`` / ``lane_claimed_at`` into
        the payload so the work is visibly in-progress rather than parked.

        ``claimed_by`` (the column) is deliberately untouched: it is a worker
        UUID for the autonomous claim machinery, whereas an external agent
        identity is a free-form string that belongs in the payload. Last-writer
        -wins — re-claiming overwrites the prior agent stamp.

        Returns the count of rows updated (0 if the finding is not a live lane
        item).
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET updated_at = now(),
                            payload = payload || jsonb_build_object(
                                'lane_claimed_by', cast(:agent as text),
                                'lane_claimed_at', cast(now() as text)
                            )
                        WHERE entry_type = 'finding'
                          AND status = 'indeterminate'
                          AND resolution_mechanism = 'human'
                          AND id = cast(:entry_id as uuid)
                        """
                    ),
                    {"entry_id": entry_id, "agent": agent},
                )
                return result.rowcount

    # ID: d4f68a3e-5138-4e99-8b4b-7e9d2e43c415
    async def revive_delegated_findings_for_rejected_proposal(
        self, proposal_id: str, reason: str
    ) -> dict[str, Any] | None:
        """Revive an assisted-lane finding when its proposal is rejected (ADR-109 D4).

        The assisted-lane analogue of ``revive_findings_for_failed_proposal``.
        That method's predicate requires ``resolution_mechanism='reaudit'`` and
        lands findings in ``awaiting_reaudit`` for machine re-adjudication — the
        autonomous-loop contract. A delegated finding carries
        ``resolution_mechanism='human'``, so the generic path would match zero
        rows and strand it at ``deferred_to_proposal`` forever.

        ADR-109 D4 is explicit: rejecting the agent's *diff* does not rescind the
        *delegation*. The finding returns straight to the lane queue
        (``indeterminate+human``) for another attempt — it does NOT round-trip
        through machine re-checking. We flip status back to 'indeterminate',
        keep ``resolution_mechanism='human'``, clear any claim, and re-stamp
        ``resolved_at`` so the row matches a freshly-delegated finding (the
        governor-inbox predicate is status='indeterminate' AND
        resolution_mechanism='human'). ``payload.proposal_id`` is left as-is; the
        next ``defer_delegated_finding_to_proposal`` overwrites it (last-writer
        -wins) if the finding is proposed again.

        Returns None if nothing matched (the proposal was not an assisted-lane
        proposal, or its finding already moved on); otherwise a dict with
        ``proposal_id``, ``reason``, ``revived_count``, ``revived_finding_ids``,
        ``revived_subjects``.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                update_result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'indeterminate',
                            resolution_mechanism = 'human',  -- ADR-091 D2-A1: indeterminate is governor-closed; co-assign at the mutation site, not only in the filter guard below
                            claimed_by = NULL,
                            claimed_at = NULL,
                            resolved_at = now(),
                            updated_at = now()
                        WHERE entry_type = 'finding'
                          AND resolution_mechanism = 'human'
                          AND status = 'deferred_to_proposal'
                          AND payload->>'proposal_id' = :proposal_id
                        RETURNING id, subject
                        """
                    ),
                    {"proposal_id": proposal_id},
                )
                rows = update_result.fetchall()

        if not rows:
            return None
        return {
            "proposal_id": proposal_id,
            "reason": reason,
            "revived_count": len(rows),
            "revived_finding_ids": [str(row[0]) for row in rows],
            "revived_subjects": [str(row[1]) for row in rows],
        }

    # ID: 5e2d8f1a-94c3-4b07-a8f2-3c7e9b1d6a45
    async def resolve_entries_for_proposal(
        self, entry_ids: list[str], proposal_id: str
    ) -> int:
        """
        Mark each entry in *entry_ids* as resolved AND store the subsuming
        *proposal_id* in its payload. Mirror of defer_entries_to_proposal,
        but with terminal status 'resolved' instead of 'deferred_to_proposal'.

        Used by ViolationRemediatorWorker's dedup-subsume path: when a
        finding is subsumed by an already-active proposal, it closes as
        'resolved' (the subsuming proposal does not track it in its scope,
        so the §7a revival path does not apply), but the payload pointer
        to the subsuming proposal_id makes the linkage auditable per URS
        Q1.F and ADR-015 D4.

        Bare resolve_entries (no proposal_id) remains in use by
        TestRemediatorWorker and TestRunnerSensor — those callers do not
        carry a proposal_id at the resolve site and should not be forced
        to invent one.

        Predicate matches resolve_entries and defer_entries_to_proposal:
        only entries currently in 'open' or 'claimed' transition; rows
        already terminalized or missing are not counted. All updates run
        inside a single transaction. Returns the count of rows actually
        updated.

        Covers:
          - ViolationRemediatorWorker._resolve_entries (dedup-subsume path)
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import ServiceRegistry

        resolved_count = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'resolved',
                                resolved_at = now(),
                                updated_at = now(),
                                payload = payload || jsonb_build_object(
                                    'proposal_id', cast(:proposal_id as text)
                                )
                            WHERE id = cast(:entry_id as uuid)
                              AND status IN ('open', 'claimed')
                            """
                        ),
                        {"entry_id": entry_id, "proposal_id": proposal_id},
                    )
                    resolved_count += result.rowcount
        return resolved_count

    # ID: e1c4b8a7-6f03-4d29-b8a2-9c5d7e0f3a14
    async def revive_findings_for_failed_proposal(
        self,
        proposal_id: str,
        failure_reason: str,
        remediation_cap_n: int | None = None,
    ) -> dict[str, Any] | None:
        """
        Restore findings that were deferred to a now-failed proposal back
        to active status, and return the revival outcome.

        Implements CORE-Finding.md §7a steps 1-2 (state transition only).
        §7a step 3 (posting a `report` entry recording the revival) is the
        calling Worker's responsibility per ADR-011 — this method is
        UPDATE-only. The Worker consumes this method's return value and
        posts the revival report via self.post_report() so the entry
        carries Worker attribution.

        Revival target is 'awaiting_reaudit', not 'open' (ADR-045). The
        finding's payload was authored when the violation was originally
        posted; after a proposal failure or rejection the underlying file
        may have been refactored, the rule's threshold may have moved, or
        the governor may judge the finding stale. Routing the finding
        through awaiting_reaudit gates the remediator's claim queue until
        AuditViolationSensor's next cycle re-evaluates the rule against
        the current file state and either releases the finding to 'open'
        (violation still holds) or resolves it (cleared). The previous
        immediate-revival-to-'open' behaviour produced a temporal race
        where the remediator could re-claim a stale finding before the
        audit sensor's next cycle ran.

        The UPDATE filter restricts to status = 'deferred_to_proposal'. This
        protects against retry races and against findings that drifted to
        some other status (abandoned, indeterminate) for unrelated reasons
        — only findings still parked on this proposal's deferral are
        revived. resolved_at is cleared so the row's terminal-state marker
        matches its new non-terminal status (ADR-010 hygiene rule, tracking
        the Option A+ convention from 2026-04-22).

        ``remediation_cap_n`` (ADR-104 D9 / #637) — the remediation-attempt
        rail. When None (the governor-reject path and any caller that does
        not count attempts), behaviour is exactly as above: every matching
        finding is revived, no counter touched. When an int, each finding's
        ``payload.remediation_attempt_count`` is incremented and, when this
        failure makes the count reach the cap, the finding is *abandoned*
        (terminal Type-B) instead of revived — breaking the
        generate → fail → revive → regenerate loop on a perpetually-failing
        remediation. This is the D3 orphan abandon-at-cap principle applied
        one trigger over (gate failure, not worker death); the abandoned
        finding keeps its original (non-Type-A) subject, so
        F19_CONVERGENCE_SQL counts it as ``stuck`` with no classifier
        change. Per ``architecture.blackboard.worker_only_inserts`` the
        terminal observation announcing the abandon (D4) is posted by the
        calling Worker, not here.

        Returns:
          None if nothing was revived or abandoned — nothing to report.
          Otherwise a dict with ``proposal_id``, ``failure_reason``,
          ``revived_count`` / ``revived_finding_ids`` / ``revived_subjects``
          and ``abandoned_count`` / ``abandoned_finding_ids`` /
          ``abandoned_subjects`` (the last three empty on the uncapped
          path). Both id and subject lists are returned — IDs for precise
          downstream queries, subjects for human-readable audit trails.

        The caller MUST NOT rely on this method raising on partial failure.
        Zero rows touched is a legitimate outcome when the failed proposal
        had no findings deferred to it (e.g. proposals created by paths
        other than ViolationRemediatorWorker); the caller receives None
        and skips posting a revival report.
        """
        from body.services.service_registry import ServiceRegistry

        abandoned_ids: list[str] = []
        abandoned_subjects: list[str] = []

        async with ServiceRegistry.session() as session:
            async with session.begin():
                if remediation_cap_n is None:
                    # Uncapped path (governor reject / callers that do not
                    # count attempts): single query-and-reset, RETURNING
                    # id, subject. Behaviour unchanged from pre-#637.
                    #
                    # ADR-091 D2 Revision B reaudit guard:
                    #   AND resolution_mechanism = 'reaudit'
                    # Only findings whose emitter declared
                    # resolution_mechanism='reaudit' may be parked into
                    # awaiting_reaudit; the predicate makes the invariant
                    # structural in SQL. See ADR-091 (Revision B (b)).
                    update_result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'awaiting_reaudit',
                                claimed_by = NULL,
                                claimed_at = NULL,
                                resolved_at = NULL,
                                updated_at = now()
                            WHERE entry_type = 'finding'
                              AND resolution_mechanism = 'reaudit'
                              AND status = 'deferred_to_proposal'
                              AND payload->>'proposal_id' = :proposal_id
                            RETURNING id, subject
                            """
                        ),
                        {"proposal_id": proposal_id},
                    )
                    rows = update_result.fetchall()
                    revived_ids = [str(row[0]) for row in rows]
                    revived_subjects = [str(row[1]) for row in rows]
                else:
                    # ADR-104 D9 (#637) capped path: select the candidates
                    # with their current attempt count, partition by whether
                    # THIS failure (count + 1) reaches the cap, then revive
                    # the under-cap set and abandon the at-cap set. Mirrors
                    # release_orphaned_claims' SELECT-partition-two-UPDATE
                    # shape (D3), with the counter living in the JSONB payload
                    # rather than a dedicated column.
                    selected = await session.execute(
                        text(
                            """
                            SELECT id::text, subject,
                                   COALESCE(
                                       (payload->>'remediation_attempt_count')::int,
                                       0
                                   )
                            FROM core.blackboard_entries
                            WHERE entry_type = 'finding'
                              AND resolution_mechanism = 'reaudit'
                              AND status = 'deferred_to_proposal'
                              AND payload->>'proposal_id' = :proposal_id
                            """
                        ),
                        {"proposal_id": proposal_id},
                    )
                    rows = selected.fetchall()
                    # (count + 1) is the attempt this failure represents.
                    to_abandon = [
                        (r[0], r[1]) for r in rows if (r[2] + 1) >= remediation_cap_n
                    ]
                    to_revive = [
                        (r[0], r[1]) for r in rows if (r[2] + 1) < remediation_cap_n
                    ]

                    if to_revive:
                        # reaudit guard preserved in the UPDATE WHERE.
                        await session.execute(
                            text(
                                """
                                UPDATE core.blackboard_entries
                                SET status = 'awaiting_reaudit',
                                    claimed_by = NULL,
                                    claimed_at = NULL,
                                    resolved_at = NULL,
                                    payload = jsonb_set(
                                        payload,
                                        '{remediation_attempt_count}',
                                        to_jsonb(COALESCE(
                                            (payload->>'remediation_attempt_count')::int,
                                            0
                                        ) + 1)
                                    ),
                                    updated_at = now()
                                WHERE id = ANY(cast(:ids as uuid[]))
                                  AND resolution_mechanism = 'reaudit'
                                  AND status = 'deferred_to_proposal'
                                """
                            ),
                            {"ids": [i for i, _ in to_revive]},
                        )

                    if to_abandon:
                        await session.execute(
                            text(
                                """
                                UPDATE core.blackboard_entries
                                SET status = 'abandoned',
                                    resolved_at = now(),
                                    payload = jsonb_set(
                                        payload,
                                        '{remediation_attempt_count}',
                                        to_jsonb(COALESCE(
                                            (payload->>'remediation_attempt_count')::int,
                                            0
                                        ) + 1)
                                    ),
                                    updated_at = now()
                                WHERE id = ANY(cast(:ids as uuid[]))
                                  AND status = 'deferred_to_proposal'
                                """
                            ),
                            {"ids": [i for i, _ in to_abandon]},
                        )

                    revived_ids = [i for i, _ in to_revive]
                    revived_subjects = [s for _, s in to_revive]
                    abandoned_ids = [i for i, _ in to_abandon]
                    abandoned_subjects = [s for _, s in to_abandon]

        logger.info(
            "Revived %d / abandoned %d finding(s) for failed proposal %s (reason: %s)",
            len(revived_ids),
            len(abandoned_ids),
            proposal_id,
            failure_reason,
        )

        if not revived_ids and not abandoned_ids:
            return None

        return {
            "proposal_id": proposal_id,
            "failure_reason": failure_reason,
            "revived_count": len(revived_ids),
            "revived_finding_ids": revived_ids,
            "revived_subjects": revived_subjects,
            "abandoned_count": len(abandoned_ids),
            "abandoned_finding_ids": abandoned_ids,
            "abandoned_subjects": abandoned_subjects,
        }

    # ID: 90c7c05a-a380-4d5a-9b1e-a911c3ed5d02
    async def resolve_deferred_entries_for_completed_proposal(
        self, proposal_id: str
    ) -> dict[str, Any] | None:
        """
        Mark findings deferred to a now-completed proposal as 'resolved'
        and return the resolution outcome.

        Success-side mirror of revive_findings_for_failed_proposal: flips
        every finding whose payload.proposal_id matches *proposal_id* and
        is still parked in 'deferred_to_proposal' to terminal 'resolved'
        status, closing the §7-style finding↔proposal lifecycle.

        The UPDATE filter restricts to status = 'deferred_to_proposal' so
        findings that drifted elsewhere (abandoned, manually overridden)
        are not retroactively re-terminalized. resolved_at is set per the
        ADR-010 hygiene rule for terminal-state rows.

        Unlike the failure-revival counterpart this method does not post
        a downstream report: no new entry is created (only existing rows
        are flipped), so the ADR-011 Worker-attribution rule does not
        apply. The caller (ProposalExecutor) is therefore not required
        to be a Worker subclass.

        Returns:
          None if no findings were resolved (resolved_count == 0) —
          nothing to report.
          dict with keys ``proposal_id``, ``resolved_count``,
          ``resolved_finding_ids``, ``resolved_subjects`` when one or
          more rows were resolved. Both id and subject lists are
          returned — IDs for precise downstream queries, subjects for
          human-readable audit trails.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                update_result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'resolved',
                            resolved_at = now(),
                            updated_at = now()
                        WHERE entry_type = 'finding'
                          AND status = 'deferred_to_proposal'
                          AND payload->>'proposal_id' = :proposal_id
                        RETURNING id, subject
                        """
                    ),
                    {"proposal_id": proposal_id},
                )
                rows = update_result.fetchall()
                resolved_ids = [str(row[0]) for row in rows]
                resolved_subjects = [str(row[1]) for row in rows]

        logger.info(
            "Resolved %d deferred finding(s) for completed proposal %s",
            len(resolved_ids),
            proposal_id,
        )

        if not resolved_ids:
            return None

        return {
            "proposal_id": proposal_id,
            "resolved_count": len(resolved_ids),
            "resolved_finding_ids": resolved_ids,
            "resolved_subjects": resolved_subjects,
        }

    # ID: fe689169-0fd6-490f-b097-afe69aee3784
    async def inherit_remediation_attempt_count(
        self, entry_ids: list[str], count: int
    ) -> None:
        """
        Set remediation_attempt_count = GREATEST(existing, count) in the
        payload of the given entries (ADR-104 D9 counter inheritance).

        Called by TestRemediatorWorker before deferring fresh findings to a
        new proposal so the accumulated count from prior abandoned cycles is
        carried forward. Only updates entries still in a pre-deferral status
        (open or claimed) to avoid touching entries mid-state-machine.
        """
        if not entry_ids or count <= 0:
            return

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET payload = jsonb_set(
                            payload,
                            '{remediation_attempt_count}',
                            to_jsonb(GREATEST(
                                COALESCE(
                                    (payload->>'remediation_attempt_count')::int,
                                    0
                                ),
                                :count
                            ))
                        ),
                        updated_at = now()
                        WHERE id = ANY(cast(:ids as uuid[]))
                          AND status IN ('open', 'claimed')
                        """
                    ),
                    {"ids": entry_ids, "count": count},
                )

    # ID: 995d1685-c278-4992-bed8-8bfac48cd4f9
    async def abandon_remediation_capped_findings(
        self, entry_ids: list[str], count: int
    ) -> list[str]:
        """
        Immediately abandon findings whose inherited remediation_attempt_count
        has already reached or exceeded the cap (ADR-104 D9 circuit breaker).

        Called by TestRemediatorWorker when the inherited count for a
        source_file equals or exceeds cap_n BEFORE a new proposal is created,
        so the loop terminates without wasting an LLM call on a proposal that
        would be abandoned immediately on failure.

        Sets status='abandoned' and stamps remediation_attempt_count=count in
        the payload. Only touches entries in 'open' or 'claimed' status.
        Returns the list of entry IDs that were actually abandoned (RETURNING).
        """
        if not entry_ids:
            return []

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'abandoned',
                            payload = jsonb_set(
                                payload,
                                '{remediation_attempt_count}',
                                to_jsonb(:count)
                            ),
                            updated_at = now()
                        WHERE id = ANY(cast(:ids as uuid[]))
                          AND status IN ('open', 'claimed')
                        RETURNING id::text
                        """
                    ),
                    {"ids": entry_ids, "count": count},
                )
                return [row[0] for row in result.fetchall()]
