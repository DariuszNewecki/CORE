-- 20260722_active_finding_dedup.sql
--
-- Atomic active-finding dedup (blackboard ledger-design defect).
--
-- Root cause: sensors post a NEW open finding row every cycle under a constant
-- subject (no dedup pre-check), so a single standing condition manufactures
-- hundreds of duplicate open rows. The BlackboardShopManager stale sensor then
-- flags each row, producing 810 per-row-unique `blackboard.entry_stale::` alerts
-- that dominate the open-findings count. See the diagnosis for the full trace.
--
-- Canonical active-finding identity: (subject, resolution_mechanism) for
-- entry_type='finding', across all NON-TERMINAL statuses. Validated empirically:
-- 0 subjects carry more than one resolution_mechanism.
--
-- This migration has TWO STAGES. Stage 1 (columns) is safe on a populated table.
-- Stage 2 (the UNIQUE index) CANNOT be created while duplicate active rows exist
-- — it must run only AFTER the reconciliation collapses duplicates. On a fresh
-- schema (CI ephemeral DB, schema.sql) there are no duplicates, so both stages
-- apply together; that is why schema.sql carries the index directly.

-- ---------------------------------------------------------------------------
-- STAGE 1 — history columns (idempotent; safe on the live populated table)
-- ---------------------------------------------------------------------------
ALTER TABLE core.blackboard_entries
    ADD COLUMN IF NOT EXISTS occurrence_count integer NOT NULL DEFAULT 1;

ALTER TABLE core.blackboard_entries
    ADD COLUMN IF NOT EXISTS first_payload jsonb;

-- last_seen_at is the OBSERVATION timestamp: set only when a finding is (re)posted
-- by its sensor. Distinct from updated_at, which the touch trigger bumps on ANY
-- mutation (claim, resolve, ...) — backfilling from updated_at would re-import the
-- exact claim/touch ambiguity this column removes (a long-ago-observed but
-- recently-claimed row would look fresh). Backfill from created_at, the true
-- first/only observation time for historical rows; reconciliation later
-- overwrites duplicated identities with max(created_at) per group.
ALTER TABLE core.blackboard_entries
    ADD COLUMN IF NOT EXISTS last_seen_at timestamp with time zone;
UPDATE core.blackboard_entries SET last_seen_at = created_at WHERE last_seen_at IS NULL;
ALTER TABLE core.blackboard_entries ALTER COLUMN last_seen_at SET DEFAULT now();
ALTER TABLE core.blackboard_entries ALTER COLUMN last_seen_at SET NOT NULL;

-- Backfill first_payload for existing findings BEFORE reconciliation. Otherwise a
-- pre-migration singleton keeps first_payload NULL, and its next dedup upsert
-- overwrites payload with the latest evidence — permanently losing the original.
-- (Reconciliation may subsequently replace a duplicated identity's canonical
-- value with the deterministically earliest payload.)
UPDATE core.blackboard_entries SET first_payload = payload
    WHERE entry_type = 'finding' AND first_payload IS NULL;

COMMENT ON COLUMN core.blackboard_entries.occurrence_count IS
    'Number of times this standing finding was observed (dedup upsert increments). first observation = 1.';
COMMENT ON COLUMN core.blackboard_entries.first_payload IS
    'Payload captured at first observation; retained across dedup updates (original history). NULL for pre-migration rows and non-findings.';
COMMENT ON COLUMN core.blackboard_entries.last_seen_at IS
    'Last OBSERVATION time (sensor (re)post). Set only by the dedup upsert, never by the updated_at touch trigger. Staleness and recovered-target logic key on this, not updated_at (which is generic mutation time).';

-- ---------------------------------------------------------------------------
-- STAGE 2 — the DB-enforced uniqueness invariant.
-- RUN ONLY AFTER reconciliation (20260722_active_finding_reconcile.sql).
-- Kept commented here so an operator applies it explicitly post-reconcile;
-- creating it against duplicates will (correctly) fail.
-- ---------------------------------------------------------------------------
-- CREATE UNIQUE INDEX CONCURRENTLY uq_active_finding_identity
--     ON core.blackboard_entries (subject, resolution_mechanism)
--     WHERE entry_type = 'finding'
--       AND status IN ('open', 'claimed', 'awaiting_reaudit');
