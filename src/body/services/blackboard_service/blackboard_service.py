# src/body/services/blackboard_service/blackboard_service.py
# blackboard_service.py
"""State-transition write methods — UPDATE to terminal and non-terminal statuses."""

from __future__ import annotations

from sqlalchemy import text


# ID: a3842b9b-9285-49d3-bd7e-4fb8f8cbf6b7
class BlackboardService:
    # ID: 1b4d6e9f-2c7a-4f08-9b53-8a6d2e4c1f3b
    async def resolve_stale_alerts_for_terminal_targets(self) -> int:
        """
        Resolve open ``blackboard.entry_stale::*`` findings whose target entry
        has reached a terminal status (or no longer exists).

        The stale-entry sensor (BlackboardShopManager) posts an alert when an
        entry exceeds its SLA tier. The alert is then itself a finding that
        stays open until something resolves it. Without this sweep, alerts
        accumulate forever once their target reaches a terminal state — they
        become meta-noise that the dashboard's open-findings count surfaces
        as growing backlog.

        Terminal target statuses mirror ``fetch_stale_entries`` (the inverse
        relation): resolved, abandoned, suppressed, dry_run_complete,
        deferred_to_proposal, indeterminate. A target row that no longer
        exists is also treated as terminal — there is nothing left to act on.

        Returns the count of stale-alert rows resolved.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries AS alert
                        SET status = 'resolved',
                            resolved_at = now(),
                            updated_at = now()
                        WHERE alert.entry_type = 'finding'
                          AND alert.status = 'open'
                          AND alert.subject LIKE 'blackboard.entry_stale::%'
                          AND NOT EXISTS (
                              SELECT 1
                              FROM core.blackboard_entries AS target
                              WHERE target.id::text = alert.payload->>'entry_id'
                                AND target.status NOT IN (
                                    'resolved',
                                    'abandoned',
                                    'suppressed',
                                    'dry_run_complete',
                                    'deferred_to_proposal',
                                    'indeterminate'
                                )
                          )
                        """
                    )
                )
                return result.rowcount or 0

    # ID: 6d2f0c8a-9e3b-4a51-b7c8-14e5d6f2a0b9
    async def resolve_dry_run_entries_for_namespace(self, namespace_prefix: str) -> int:
        """
        Resolve all open audit.remediation.dry_run entries whose subject
        matches the given namespace prefix.

        Called by AuditViolationSensor when it completes a cycle with zero
        violations — confirming that any dry-run entries for this namespace
        describe violations that no longer exist.

        Only resolves entries in 'open' status. Returns count of rows updated.

        Subject pattern matched: 'audit.remediation.dry_run::<namespace_prefix>%'
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'resolved',
                            resolved_at = now(),
                            updated_at = now()
                        WHERE entry_type = 'finding'
                          AND subject LIKE 'audit.remediation.dry_run::'
                                            || :namespace_prefix || '%'
                          AND status = 'open'
                        """
                    ),
                    {"namespace_prefix": namespace_prefix},
                )
                return result.rowcount or 0

    # ID: 3d4e5f6a-7b8c-9d0e-1f2a-3b4c5d6e7f8a
    async def resolve_entries(self, entry_ids: list[str]) -> int:
        """
        Mark each entry in *entry_ids* as resolved, provided it is still in
        a non-terminal status ('open' or 'claimed').

        Historically the WHERE clause filtered status = 'open' only, which
        silently no-op'd the claim→resolve path used by workers that claim
        findings before acting on them. This left every such caller leaking
        claims — the entries_resolved counters in their reports were always
        zero because the UPDATE never matched.

        The predicate now accepts either 'open' or 'claimed' so the caller
        pattern is:
          - fetch_open_findings → resolve_entries  (TestRunnerSensor)

        All updates run inside a single transaction. Returns the count of
        rows actually updated (entries already terminalized or missing are
        not counted).

        Scope note: as of ADR-015 D4, neither ViolationRemediatorWorker
        path calls this method. The happy path uses defer_entries_to_proposal
        so the §7/§7a CORE-Finding.md Finding→Proposal linkage is
        preserved; the dedup-subsume path uses resolve_entries_for_proposal
        so the subsuming proposal_id is recorded in payload (URS Q1.F).
        This bare-resolve method remains in use by TestRunnerSensor —
        a caller that legitimately has no proposal_id to record.

        Covers:
          - TestRunnerSensor (direct)
        """
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
                                updated_at = now()
                            WHERE id = cast(:entry_id as uuid)
                              AND status IN ('open', 'claimed')
                            """
                        ),
                        {"entry_id": entry_id},
                    )
                    resolved_count += result.rowcount
        return resolved_count

    # ID: a7b2c8d3-e4f5-6789-abcd-ef0123456789
    async def release_claimed_entries(self, entry_ids: list[str]) -> int:
        """
        Reset claimed entries back to open status and clear claimed_by.

        Used when a worker claims findings but cannot act on them (e.g.
        unmappable violations with no registered remediation action).
        Releasing prevents them from staying claimed forever.

        Only updates entries currently in 'claimed' status.
        Returns the count of rows actually updated.
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import ServiceRegistry

        released = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'open',
                                claimed_by = NULL,
                                updated_at = now()
                            WHERE id = cast(:entry_id as uuid)
                              AND status = 'claimed'
                            """
                        ),
                        {"entry_id": entry_id},
                    )
                    released += result.rowcount
        return released

    # ID: 4c7a9e2f-b518-4d63-a0e1-d6f3b82c5a10
    async def abandon_entries(self, entry_ids: list[str]) -> int:
        """
        Mark entries as abandoned. Terminal state — no worker reclaims them.
        Only updates entries currently in 'claimed' status.
        Returns the count of rows actually updated.
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import ServiceRegistry

        abandoned = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'abandoned',
                                resolved_at = now(),
                                updated_at = now()
                            WHERE id = cast(:entry_id as uuid)
                              AND status = 'claimed'
                            """
                        ),
                        {"entry_id": entry_id},
                    )
                    abandoned += result.rowcount
        return abandoned

    # ID: d3a1f7b2-8c4e-4a9d-b6e5-1f0c3d7a2e89
    async def mark_indeterminate(self, entry_ids: list[str]) -> int:
        """
        Mark claimed entries as indeterminate.

        Used when a worker claims findings but reaches an inconclusive
        outcome — the entry is neither resolved nor releasable back to
        open.  Only updates entries currently in 'claimed' status.
        Returns the count of rows actually updated.
        """
        if not entry_ids:
            return 0

        from body.services.service_registry import ServiceRegistry

        updated = 0
        async with ServiceRegistry.session() as session:
            async with session.begin():
                for entry_id in entry_ids:
                    result = await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'indeterminate',
                                resolved_at = now(),
                                updated_at = now()
                            WHERE id = cast(:entry_id as uuid)
                              AND status = 'claimed'
                            """
                        ),
                        {"entry_id": entry_id},
                    )
                    updated += result.rowcount
        return updated

    # ID: 8d586156-b04f-4d7a-a7b9-5a52b099b9b1
    async def resolve_indeterminate_entry(
        self,
        entry_id: str,
        reason: str,
        resolved_by: str = "cli_admin",
        resolution_authority: str = "human.cli_operator",
    ) -> int:
        """
        Close a single indeterminate finding with an operator-provided reason.

        Indeterminate is terminal from the audit sensor's perspective — the
        sensor delegates to a human and will not re-evaluate the row. Without
        this method there is no path to close the finding once the underlying
        condition is addressed out-of-band (manual refactor, threshold change
        via ADR, or operator judgement that the finding is stale). The §7a
        revival path covers the deferred_to_proposal branch but has no
        symmetric counterpart for indeterminate.

        Mirrors the operator-attribution shape of reject_proposal: reason,
        resolved_by, and resolution_authority are stamped into payload under
        a 'resolution' key so the audit trail survives. Only acts on rows
        currently in 'indeterminate' status — returns 1 on success, 0 if the
        row has already transitioned or does not exist.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'resolved',
                            resolved_at = now(),
                            updated_at = now(),
                            payload = jsonb_set(
                                payload,
                                '{resolution}',
                                jsonb_build_object(
                                    'reason', cast(:reason as text),
                                    'resolved_by', cast(:resolved_by as text),
                                    'resolution_authority', cast(:authority as text),
                                    'resolved_at', to_char(now() at time zone 'UTC',
                                                           'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                                ),
                                true
                            )
                        WHERE id = cast(:entry_id as uuid)
                          AND status = 'indeterminate'
                        """
                    ),
                    {
                        "entry_id": entry_id,
                        "reason": reason,
                        "resolved_by": resolved_by,
                        "authority": resolution_authority,
                    },
                )
                return result.rowcount or 0

    # ID: 77d705b6-bafe-481b-9d73-3bbefdd85470
    async def adjudicate_awaiting_reaudit_findings(
        self,
        subject_prefix: str,
        current_violation_subjects: set[str],
        resolved_by: str,
    ) -> dict[str, list[str]]:
        """
        Drain the awaiting_reaudit queue for a subject prefix (ADR-045, ADR-072).

        Implements the drainer release pass. For each finding currently in
        'awaiting_reaudit' whose subject begins with ``subject_prefix``,
        decide based on the caller's current-state evaluation:

        - Subject present in *current_violation_subjects*: transition to
          'open'. The condition still holds; the remediator should pick it
          up on its next tick.
        - Subject absent from *current_violation_subjects*: transition to
          'resolved'. The drainer re-evaluated and the underlying condition
          has cleared (including the deleted-source case per ADR-072).
          payload.resolution is stamped with *resolved_by* attribution so
          the audit trail records why this row closed without operator
          action.

        Per ADR-072, every quarantine-capable namespace must call this
        method from a registered drainer worker. Caller passes the full
        subject prefix (e.g. ``python::<rule_namespace>`` under the ADR-091
        D2 canonical format — applies to audit, test-runner, and coherence
        sensor namespaces).

        The two transitions run in one transaction. Returns lists of
        released and resolved subjects for the drainer's release-pass
        report.
        """
        from body.services.service_registry import ServiceRegistry

        released_subjects: list[str] = []
        resolved_subjects: list[str] = []

        async with ServiceRegistry.session() as session:
            async with session.begin():
                pending = await session.execute(
                    text(
                        """
                        SELECT id, subject
                        FROM core.blackboard_entries
                        WHERE entry_type = 'finding'
                          AND status = 'awaiting_reaudit'
                          AND (subject = :prefix
                               OR subject LIKE :prefix || '.%'
                               OR subject LIKE :prefix || '::%')
                        FOR UPDATE
                        """
                    ),
                    {"prefix": subject_prefix},
                )
                rows = pending.fetchall()

                release_ids: list[str] = []
                resolve_ids: list[str] = []
                for row in rows:
                    entry_id = str(row[0])
                    subject = str(row[1])
                    if subject in current_violation_subjects:
                        release_ids.append(entry_id)
                        released_subjects.append(subject)
                    else:
                        resolve_ids.append(entry_id)
                        resolved_subjects.append(subject)

                if release_ids:
                    await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'open',
                                updated_at = now()
                            WHERE id = ANY(cast(:ids as uuid[]))
                              AND status = 'awaiting_reaudit'
                            """
                        ),
                        {"ids": release_ids},
                    )

                if resolve_ids:
                    await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'resolved',
                                resolved_at = now(),
                                updated_at = now(),
                                payload = jsonb_set(
                                    payload,
                                    '{resolution}',
                                    jsonb_build_object(
                                        'reason', 'audit re-evaluation: condition no longer present',
                                        'resolved_by', cast(:resolved_by as text),
                                        'resolution_authority', 'system.audit',
                                        'resolved_at', to_char(now() at time zone 'UTC',
                                                               'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                                    ),
                                    true
                                )
                            WHERE id = ANY(cast(:ids as uuid[]))
                              AND status = 'awaiting_reaudit'
                            """
                        ),
                        {"ids": resolve_ids, "resolved_by": resolved_by},
                    )

        return {
            "released_subjects": released_subjects,
            "resolved_subjects": resolved_subjects,
        }

    # ID: 0c2f1a8d-3e6b-4c9f-a7d4-5b8e2f1c4a7d
    async def sweep_terminal_telemetry(
        self,
        subject_prefixes: tuple[str, ...],
        ttl_days: int,
        batch_max: int,
    ) -> int:
        """
        ADR-082 Mechanism 1 — hard DELETE for terminal telemetry past TTL.

        Removes ``core.blackboard_entries`` rows whose subject starts with any
        prefix in *subject_prefixes*, whose status is already terminal
        ('resolved' or 'abandoned'), and whose created_at is older than
        *ttl_days*. Mirrors ADR-044's ``llm_gate_verdicts`` cache sweep shape.

        The row cap (*batch_max*) is a constitutional rail per
        ``feedback_destructive_autonomous_needs_rails_first``: even with the
        TTL filter, a misconfigured prefix list could otherwise scan and
        delete millions of rows in one transaction. DELETEs select via a
        bounded subquery so PostgreSQL's lack of DELETE…LIMIT is sidestepped
        cleanly.

        Returns the count of rows actually deleted. Empty *subject_prefixes*
        is a no-op (returns 0) — the empty allowlist is fail-closed, not
        fail-open.
        """
        if not subject_prefixes:
            return 0

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        DELETE FROM core.blackboard_entries
                        WHERE id IN (
                            SELECT id FROM core.blackboard_entries
                            WHERE status IN ('resolved', 'abandoned')
                              AND subject LIKE ANY(
                                  ARRAY(
                                      SELECT p || '%%'
                                      FROM unnest(cast(:prefixes as text[])) AS p
                                  )
                              )
                              AND created_at < now() - make_interval(days => :days)
                            LIMIT :batch_max
                        )
                        """
                    ),
                    {
                        "prefixes": list(subject_prefixes),
                        "days": int(ttl_days),
                        "batch_max": int(batch_max),
                    },
                )
                return result.rowcount or 0

    # ID: 8a5f3d6c-2b9e-4f17-c0d8-9e4a1b6f3c8e
    async def sweep_delegate_open_findings(
        self,
        subjects: tuple[str, ...],
        ttl_days: int,
        batch_max: int,
    ) -> int:
        """
        ADR-082 Mechanism 2 — status transition open → resolved for stale
        DELEGATE-class findings.

        Updates ``core.blackboard_entries`` rows whose subject equals one of
        *subjects*, whose status is 'open', and whose created_at is older than
        *ttl_days*. Sets status='resolved', resolved_at=now(), updated_at=now(),
        and stamps payload.resolution with an attribution block so the audit
        trail records why the row closed without operator action.

        Preserves the row (no DELETE) per the audit-trail principle: the
        writer-as-sensor's matching run.complete report already carries the
        original event payload, so the OPEN finding's content is recoverable
        even after auto-resolution. Status transition is the cheaper
        rollback path than DELETE if the TTL turns out to be misconfigured.

        Row cap (*batch_max*) is the rail per
        ``feedback_destructive_autonomous_needs_rails_first``. Empty
        *subjects* is a no-op — fail-closed allowlist.

        Returns the count of rows updated.
        """
        if not subjects:
            return 0

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        UPDATE core.blackboard_entries
                        SET status = 'resolved',
                            resolved_at = now(),
                            updated_at = now(),
                            payload = jsonb_set(
                                payload,
                                '{resolution}',
                                jsonb_build_object(
                                    'reason', 'ADR-082 TTL sweep: governor inattention exceeded retention window',
                                    'resolved_by', 'blackboard_shop_manager',
                                    'resolution_authority', 'system.ttl_sweep',
                                    'resolved_at', to_char(now() at time zone 'UTC',
                                                           'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                                ),
                                true
                            )
                        WHERE id IN (
                            SELECT id FROM core.blackboard_entries
                            WHERE entry_type = 'finding'
                              AND status = 'open'
                              AND subject = ANY(cast(:subjects as text[]))
                              AND created_at < now() - make_interval(days => :days)
                            LIMIT :batch_max
                        )
                        """
                    ),
                    {
                        "subjects": list(subjects),
                        "days": int(ttl_days),
                        "batch_max": int(batch_max),
                    },
                )
                return result.rowcount or 0

    # ID: 54c114b0-4c6d-484f-8b20-d9ff5fa24caf
    async def update_entry_status(self, entry_id: str, status: str) -> None:
        """
        Update the status of a single blackboard entry by ID.

        Covers:
          - PromptExtractorWorker._mark_finding

        Sets resolved_at on transition to a terminal status (resolved, abandoned,
        indeterminate, suppressed), matching the hygiene rule established by
        commit 59ff25be and the pattern used by the direct-SQL _mark_findings /
        _mark_finding paths. Without this clause, callers routing through this
        method (ProposalConsumerWorker._mark_finding,
        ViolationRemediator._mark_finding) produced terminal rows with NULL
        resolved_at, distorting any query that uses resolved_at as a temporal
        filter. Discovered 2026-04-27 during Band B verification sweep: 26/26
        abandoned rows post-59ff25be carried NULL resolved_at, all attributable
        to this path. 'suppressed' joined the terminal set per #263.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            await session.execute(
                text(
                    """
                    UPDATE core.blackboard_entries
                    SET status = :status,
                        resolved_at = CASE
                            WHEN :status IN ('resolved', 'abandoned', 'indeterminate', 'suppressed')
                                THEN now()
                            ELSE resolved_at
                        END,
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"status": status, "id": entry_id},
            )
            await session.commit()
