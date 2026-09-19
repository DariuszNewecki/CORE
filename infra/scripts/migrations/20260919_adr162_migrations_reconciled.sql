-- 20260919_adr162_migrations_reconciled.sql
--
-- ADR-162 D7 (R7-A): the migration ledger gains a `reconciled` marker.
--
-- true  = the row was recorded WITHOUT executing the file, because the entry is
--         declared `reconcilable` in infra/migrations/manifest.yaml and its
--         `verify` probe already proved the complete postcondition (D12 §2);
-- false = the file was executed by the ledger engine (or the row is part of a
--         fresh-install seed / verified baseline adoption).
--
-- The engine brings the ledger to this structure itself before it records
-- anything (it must be able to describe its own rows before this entry is
-- reached in manifest order); this entry ledgers the change so that fresh
-- installs, hop-equivalence and status probes see it like any other
-- migration. Idempotent; runs in one transaction (leading BEGIN / trailing
-- COMMIT are stripped by the engine, kept for `psql -f` readability).

BEGIN;

ALTER TABLE core._migrations
    ADD COLUMN IF NOT EXISTS reconciled boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN core._migrations.reconciled IS
    'ADR-162 D7: true when recorded without execution because the manifest entry is reconcilable and its verify probe already held; false when executed or seeded.';

COMMIT;
