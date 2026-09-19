-- 20260919e_adr052_phase4_drop_runtime_settings.sql
--
-- ADR-162 U5a — historical reconstruction (backfill).
--
-- Origin: ADR-052 Phase 4 ("Drop runtime_settings"). Phases 1–3 (ledgered:
-- 20260516_adr_052_phase1/2/3 + governor decisions + orphan-key retirement)
-- moved every runtime_settings key into the typed tables (system_config,
-- llm_resources, secret_store) or retired it, recording each key's journey in
-- core.config_migration_log. Phase 4 (commit 09988391, 2026-07-06, #328)
-- removed all code paths and stated the gate that the released Phase 3 file
-- also records: the table may be dropped only once EVERY config_migration_log
-- row carries a non-null migrated_at. The governor performed the DROP on the
-- live database by hand; schema.sql captured it at 8d02e21b (2026-07-14).
--
-- This migration encodes that gate instead of trusting it: it REFUSES (and the
-- engine rolls back, recording nothing) when any runtime_settings key has not
-- been migrated or retired — a key without a config_migration_log row, or with
-- migrated_at IS NULL. It never uses CASCADE and never discards unaccounted
-- data; the refusal names the keys so the operator can complete ADR-052
-- Phases 2–3 (or retire the keys by governor decision) first.
-- config_migration_log itself is retained as the audit trail.
--
-- On a database where the table is already gone (a fresh install from
-- schema.sql, or v2.10.1) the entry is reconciled by its probe, not executed.
-- Idempotent; one transaction.

BEGIN;

DO $$
DECLARE
    unresolved text;
BEGIN
    IF to_regclass('core.runtime_settings') IS NULL THEN
        RETURN;  -- already dropped; nothing to verify
    END IF;
    SELECT string_agg(rs.key, ', ' ORDER BY rs.key)
      INTO unresolved
      FROM core.runtime_settings rs
     WHERE NOT EXISTS (
               SELECT 1 FROM core.config_migration_log cml
                WHERE cml.env_key = rs.key
                  AND cml.migrated_at IS NOT NULL
           );
    IF unresolved IS NOT NULL THEN
        RAISE EXCEPTION USING
            MESSAGE = 'ADR-052 Phase 4 refused: core.runtime_settings still holds '
                      'keys not recorded as migrated or retired in '
                      'core.config_migration_log: ' || unresolved,
            HINT = 'Complete ADR-052 Phases 2-3 for these keys (or retire them by '
                   'governor decision, marking config_migration_log.migrated_at) '
                   'and re-run core-admin database migrate --write.';
    END IF;
END $$;

DROP TABLE IF EXISTS core.runtime_settings;

COMMIT;
