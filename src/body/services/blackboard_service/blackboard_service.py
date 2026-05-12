# src/body/services/blackboard_service/blackboard_service.py
# blackboard_service.py
"""State-transition write methods — UPDATE to terminal and non-terminal statuses."""

from __future__ import annotations

from sqlalchemy import text


# ID: a3842b9b-9285-49d3-bd7e-4fb8f8cbf6b7
class BlackboardService:
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
