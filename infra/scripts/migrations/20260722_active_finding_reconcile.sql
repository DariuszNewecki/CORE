-- 20260722_active_finding_reconcile.sql
--
-- Historical reconciliation for the active-finding dedup defect. Run AFTER
-- 20260722_active_finding_dedup.sql (Stage 1 columns) and ONLY with all
-- blackboard writers quiesced (daemon + api down). Idempotent: re-running
-- resolves 0 rows. Nothing is deleted — duplicates are RESOLVED with a retained
-- reason and their history is aggregated into the surviving canonical row.
--
-- Ordering safety (Blocker 3): the whole thing runs in ONE transaction under a
-- SHARE ROW EXCLUSIVE lock, and the unique index is created inside it (plain,
-- not CONCURRENTLY — safe because writers are quiesced and the table is locked),
-- so no duplicate can appear between reconciliation and enforcement.

BEGIN;

-- Block any stray writer for the duration (belt-and-suspenders on top of the
-- runbook's daemon-down quiesce).
LOCK TABLE core.blackboard_entries IN SHARE ROW EXCLUSIVE MODE;

-- Per duplicated identity, deterministically aggregate the group's history.
-- Tie-break on id so the choice is stable across runs.
CREATE TEMP TABLE _recon_groups ON COMMIT DROP AS
SELECT
    subject,
    resolution_mechanism,
    (array_agg(id      ORDER BY created_at ASC,  id ASC))[1] AS canonical_id,
    (array_agg(payload ORDER BY created_at ASC,  id ASC))[1] AS first_payload_val,
    (array_agg(payload ORDER BY created_at DESC, id DESC))[1] AS latest_payload_val,
    max(created_at)       AS last_obs,
    sum(occurrence_count) AS total_occ
FROM core.blackboard_entries
WHERE entry_type = 'finding'
  AND status IN ('open', 'claimed', 'awaiting_reaudit')
  AND subject NOT LIKE 'blackboard.entry_stale::%'
GROUP BY subject, resolution_mechanism
HAVING count(*) > 1;

-- Phase 1a — fold the aggregated history into the canonical (earliest) row.
UPDATE core.blackboard_entries e
SET first_payload    = g.first_payload_val,   -- earliest = original history
    payload          = g.latest_payload_val,  -- newest = latest evidence
    last_seen_at     = g.last_obs,            -- max observation time
    occurrence_count = g.total_occ,           -- summed occurrences
    updated_at       = now()
FROM _recon_groups g
WHERE e.id = g.canonical_id;

-- Phase 1b — resolve the non-canonical duplicate rows, retaining the reason.
UPDATE core.blackboard_entries e
SET status = 'resolved',
    resolved_at = now(),
    updated_at = now(),
    payload = jsonb_set(
        COALESCE(e.payload, '{}'::jsonb),
        '{reconciliation_reason}',
        '"duplicate_open_row_reconciliation"'::jsonb
    )
FROM _recon_groups g
WHERE e.subject = g.subject
  AND e.resolution_mechanism = g.resolution_mechanism
  AND e.entry_type = 'finding'
  AND e.status IN ('open', 'claimed', 'awaiting_reaudit')
  AND e.id <> g.canonical_id;

-- Phase 3 — enforce the invariant. Non-concurrent is safe here: writers are
-- quiesced and the table is locked, and after 1a/1b there is exactly one
-- non-terminal finding per (subject, resolution_mechanism).
CREATE UNIQUE INDEX IF NOT EXISTS uq_active_finding_identity
    ON core.blackboard_entries (subject, resolution_mechanism)
    WHERE entry_type = 'finding'
      AND status IN ('open', 'claimed', 'awaiting_reaudit');

COMMIT;

-- Phase 2 (stale-alert closure) is NOT done here: run the resolver
-- (BlackboardService.resolve_stale_alerts_for_terminal_targets) after the
-- compatible code is deployed and the daemon restarted, so the alerts whose
-- targets just became terminal/recovered close under the new logic.
