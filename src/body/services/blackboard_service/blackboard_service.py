# src/body/services/blackboard_service/blackboard_service.py
# blackboard_service.py
"""State-transition write methods — UPDATE to terminal and non-terminal statuses."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


CORE_ROLE = "facade"  # ADR-095 D3


def _retired_rule_in_subject(
    subject: str, known_rule_ids: set[str], known_namespaces: set[str]
) -> str | None:
    """Return the retired rule id embedded in an audit-violation *subject*, or None.

    The safety-critical targeting predicate for the #657 retired-rule sweep,
    extracted pure so it is unit-testable without a database. A subject is a
    retired-rule orphan iff ALL hold:
      - canonical ``<lang>::<rule>::<identity>`` shape (>=3 ``::`` segments);
      - the rule segment is dotted (a rule id, not a bare identity);
      - the rule's namespace is still governed (``known_namespaces``);
      - the full rule id is absent from the live registry (``known_rule_ids``).
    Worker observations (``loop_hold.sample::x``, ``governance.edge5.orphan_sha
    ::<id>``) and live-rule findings return None.
    """
    parts = subject.split("::")
    if len(parts) < 3:
        return None
    rule = parts[1]
    if "." not in rule:
        return None
    if rule.split(".", 1)[0] not in known_namespaces:
        return None
    if rule in known_rule_ids:
        return None
    return rule


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

    # ID: 46b1652f-d096-4f31-8ea3-8bfec88a48e3
    async def release_orphaned_claims(
        self,
        *,
        live_uuids: list[str],
        grace_seconds: int,
        reclaim_cap_n: int,
        batch_max: int,
    ) -> dict[str, list[str]]:
        """Reap claims held by workers that are provably gone (ADR-104 D1-D3).

        A claim is *orphaned* iff all hold:
          1. ``status = 'claimed'``;
          2. ``claimed_at < now() - grace_seconds`` (the grace window — per
             ADR-104 ratification #2 the caller passes
             ``worker_alive_threshold_sec`` here, so "past grace" and "not
             alive" read off one clock); and
          3. ``claimed_by`` is NOT in ``live_uuids`` (the currently-alive
             worker uuids from ``WorkerRegistryService.fetch_alive_workers``).

        Each orphaned claim's ``orphan_release_count`` is incremented. When
        the new count reaches ``reclaim_cap_n`` the entry is *abandoned*
        (terminal, ``resolved_at`` set) instead of re-opened — the ADR-104 D3
        rail that breaks a crash -> reclaim -> crash loop on an unprocessable
        finding. Otherwise it is reset to ``status='open'``,
        ``claimed_by=NULL`` (the ``release_claimed_entries`` semantics) so a
        live worker reclaims it.

        Bounded by ``batch_max`` (ADR-070 D8 rail). This method performs the
        state transitions only; per
        ``architecture.blackboard.worker_only_inserts`` the findings that
        announce reaps (ADR-104 D4) are posted by the calling Worker
        (BlackboardShopManager), not here.

        Fail-safe (ADR-104 D5): an empty ``live_uuids`` would make condition
        (3) vacuously true for every claim — mass-reaping on a registry
        glitch. This method refuses an empty ``live_uuids``; the primary D5
        guard lives in the caller, this is defense in depth.

        Returns ``{'released': [entry_id, ...], 'abandoned': [entry_id, ...]}``
        as string ids, so the caller posts one finding per reaped entry.
        """
        empty: dict[str, list[str]] = {"released": [], "abandoned": []}
        if not live_uuids:
            return empty

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                selected = await session.execute(
                    text(
                        """
                        SELECT id::text, orphan_release_count
                        FROM core.blackboard_entries
                        WHERE status = 'claimed'
                          AND claimed_at < now() - make_interval(secs => :grace)
                          AND claimed_by <> ALL(cast(:live_uuids as uuid[]))
                        ORDER BY claimed_at ASC
                        LIMIT :batch_max
                        """
                    ),
                    {
                        "grace": grace_seconds,
                        "live_uuids": live_uuids,
                        "batch_max": batch_max,
                    },
                )
                rows = selected.fetchall()
                if not rows:
                    return empty

                to_abandon = [r[0] for r in rows if (r[1] + 1) >= reclaim_cap_n]
                to_release = [r[0] for r in rows if (r[1] + 1) < reclaim_cap_n]

                if to_release:
                    await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'open',
                                claimed_by = NULL,
                                orphan_release_count = orphan_release_count + 1,
                                updated_at = now()
                            WHERE id = ANY(cast(:ids as uuid[]))
                              AND status = 'claimed'
                            """
                        ),
                        {"ids": to_release},
                    )

                if to_abandon:
                    await session.execute(
                        text(
                            """
                            UPDATE core.blackboard_entries
                            SET status = 'abandoned',
                                resolved_at = now(),
                                orphan_release_count = orphan_release_count + 1,
                                updated_at = now()
                            WHERE id = ANY(cast(:ids as uuid[]))
                              AND status = 'claimed'
                            """
                        ),
                        {"ids": to_abandon},
                    )

        return {"released": to_release, "abandoned": to_abandon}

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
                                -- ADR-091 D2-A1: a finding delegated to the
                                -- governor is closed by a human, never by the
                                -- reaudit sensor. The transition owns the field.
                                resolution_mechanism = 'human',
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

    # ID: a091392a-11e2-4ee5-be56-b01e864f404d
    async def resolve_findings_with_retired_rules(
        self,
        known_rule_ids: set[str],
        known_namespaces: set[str],
    ) -> dict[str, Any]:
        """Resolve non-terminal findings whose rule id has left the registry (#657).

        When a rule is renamed or retired (e.g. #490), in-flight findings keep
        the dead rule id. The audit sensor's resolution pass keys on *live* rule
        ids, so those findings can never be cleared and strand forever in the
        governor inbox / lane. This sweep closes that gap.

        Safety rails:
        - **Fail-closed**: an empty ``known_rule_ids`` means the registry did not
          load; the sweep no-ops rather than mass-resolving every finding.
        - **Precise targeting**: only canonical audit-violation subjects of the
          form ``<lang>::<rule>::<identity>`` (>=3 ``::`` segments) where the
          rule segment carries a dot AND its namespace is still governed
          (``known_namespaces``) AND the full rule id is absent from
          ``known_rule_ids``. Worker observations like ``loop_hold.sample::x``
          or ``governance.edge5.orphan_sha::<id>`` (no rule segment) are
          structurally excluded.
        - **Scope**: active statuses only — open/claimed/indeterminate/
          awaiting_reaudit. ``deferred_to_proposal`` is left to the proposal
          lifecycle; terminal rows are untouched.

        Stamps a ``resolution`` payload key (authority ``system.rule_registry
        _sweep``) so the close is auditable. Returns
        ``{resolved, retired_rules, scanned}``.
        """
        if not known_rule_ids:
            logger.warning(
                "retired-rule sweep skipped: empty rule registry (fail-closed)."
            )
            return {"resolved": 0, "retired_rules": [], "scanned": 0, "skipped": True}

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                candidates = (
                    await session.execute(
                        text(
                            """
                            SELECT id, subject FROM core.blackboard_entries
                            WHERE entry_type = 'finding'
                              AND status IN ('open', 'claimed', 'indeterminate',
                                             'awaiting_reaudit')
                              AND subject LIKE '%::%::%'
                            """
                        )
                    )
                ).fetchall()

                orphan_ids: list[str] = []
                retired_rules: set[str] = set()
                for entry_id, subject in candidates:
                    rule = _retired_rule_in_subject(
                        subject, known_rule_ids, known_namespaces
                    )
                    if rule is None:
                        continue
                    orphan_ids.append(str(entry_id))
                    retired_rules.add(rule)

                if orphan_ids:
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
                                        'reason', cast(:reason as text),
                                        'resolved_by', 'rule_registry_sweep',
                                        'resolution_authority',
                                            'system.rule_registry_sweep',
                                        'resolved_at', to_char(
                                            now() at time zone 'UTC',
                                            'YYYY-MM-DD"T"HH24:MI:SS"Z"')
                                    ),
                                    true
                                )
                            WHERE id = ANY(cast(:ids as uuid[]))
                            """
                        ),
                        {
                            "ids": orphan_ids,
                            "reason": (
                                "Rule id no longer in the active registry "
                                "(renamed/retired); orphaned finding with no live "
                                "rule to clear it. Auto-resolved by the retired-rule "
                                "sweep (#657)."
                            ),
                        },
                    )

        if orphan_ids:
            logger.info(
                "retired-rule sweep: resolved %d orphaned findings across "
                "retired rules %s",
                len(orphan_ids),
                sorted(retired_rules),
            )
        return {
            "resolved": len(orphan_ids),
            "retired_rules": sorted(retired_rules),
            "scanned": len(candidates),
        }

    # ID: 466173fe-4d83-47a8-981d-f8760ad2a927
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

    # ID: 6ca715c7-53db-47bd-ba68-8986fce5fc83
    async def sweep_telemetry_keep_last_n_per_subject(
        self,
        subject_prefixes: tuple[str, ...],
        keep_last: int,
        batch_max: int,
    ) -> int:
        """
        Issue #568 — count-based retention for slow-callback telemetry.

        Time-based TTL is the wrong shape for telemetry that fires on slow
        callbacks: well-behaved (rare-emitting) workers have their entire
        window pruned away while hot emitters still leave hundreds of rows.
        This sweep partitions rows by subject (each
        ``loop_hold.sample::<worker_stem>`` is its own ordered sequence),
        keeps the most recent *keep_last* per subject, and DELETEs the rest.

        Partitioning by subject (not worker_uuid) lets the worker name carry
        the grouping; a single worker with a stable UUID across restarts
        still keeps its full history, and a worker that gets re-UUID'd
        retains its emission stream because the subject stays stable.

        The *batch_max* cap is a constitutional rail per
        ``feedback_destructive_autonomous_needs_rails_first``. PostgreSQL's
        DELETE…LIMIT limitation is sidestepped by selecting through a
        bounded subquery against a CTE.

        Returns the count of rows actually deleted. Empty *subject_prefixes*
        or *keep_last* <= 0 is a no-op (returns 0) — fail-closed.
        """
        if not subject_prefixes or keep_last <= 0:
            return 0

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                result = await session.execute(
                    text(
                        """
                        WITH ranked AS (
                            SELECT id,
                                ROW_NUMBER() OVER (
                                    PARTITION BY subject
                                    ORDER BY created_at DESC
                                ) AS rn
                            FROM core.blackboard_entries
                            WHERE subject LIKE ANY(
                                ARRAY(
                                    SELECT p || '%%'
                                    FROM unnest(cast(:prefixes as text[])) AS p
                                )
                            )
                        )
                        DELETE FROM core.blackboard_entries
                        WHERE id IN (
                            SELECT id FROM ranked
                            WHERE rn > :keep_last
                            LIMIT :batch_max
                        )
                        """
                    ),
                    {
                        "prefixes": list(subject_prefixes),
                        "keep_last": int(keep_last),
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
                        -- ADR-091 D2-A1: a transition into 'indeterminate'
                        -- hands closing authority to a human; the field must
                        -- track that (else a reaudit finding masquerades in
                        -- the reaudit queue forever). ELSE preserves the
                        -- existing mechanism for every other transition.
                        resolution_mechanism = CASE
                            WHEN :status = 'indeterminate' THEN 'human'
                            ELSE resolution_mechanism
                        END,
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
