-- 20261102_1390_system_config_row.sql
--
-- Gives every database its core.system_config singleton row (#1390 G5).
--
-- BACKGROUND
--
-- Until now only `core-admin llm-resources setup` (#1375) and the external-run
-- seed created the row, so a database installed from schema.sql had none, and
-- every reader substituted its own default without saying so (operating_mode,
-- llm_enabled, log_retention_months). A fresh install now gets the row from
-- schema.sql's seed block; this migration gives it to an existing database
-- that never ran setup. The values are the column defaults -- the values the
-- readers were already falling back to -- so no running behaviour changes.
--
-- Forward-only. Re-running is a no-op: the INSERT matches only an empty table.

BEGIN;

INSERT INTO core.system_config (id)
SELECT gen_random_uuid()
 WHERE NOT EXISTS (SELECT 1 FROM core.system_config);

COMMIT;
