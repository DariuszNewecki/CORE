-- 20260919d_users_display_name.sql
--
-- ADR-162 U5a — historical reconstruction (backfill).
--
-- Origin: `core.users.display_name text` was added to the live database out of
-- band ("UI-added column", schema.sql regeneration 8d02e21b, 2026-07-14). No
-- commit, migration or runtime code introduced it; no code reads or writes it
-- today. It is part of the canonical schema.sql, so an upgraded database must
-- carry it to be equivalent to a fresh install.
--
-- Nullable, no default, no data transformation. Idempotent; one transaction.

BEGIN;

ALTER TABLE core.users
    ADD COLUMN IF NOT EXISTS display_name text;

COMMIT;
