-- 20260502_drop_worker_registry_status.sql
--
-- ADR-020 — Worker liveness derived from heartbeat.
--
-- Retires core.worker_registry.status. Liveness is derived from
-- last_heartbeat against per-worker SLAs declared in .intent/workers/*.yaml.
--
-- Step 1 deletes the 20 historical 'abandoned' rows that accumulated from a
-- removed write path. After the column drop their abandonment signal would be
-- lost; preserving them post-drop would falsely inflate the silent_workers
-- counter in core.system_health_log because every one of them carries a stale
-- last_heartbeat (oldest 2026-03-13, newest 2026-04-07). They represent
-- decommissioned worker UUIDs from prior daemon generations and have no
-- corresponding .intent/workers/ declaration.
--
-- Step 2 drops the column. After this point the schema declares no liveness
-- state machine; last_heartbeat is the canonical signal.
--
-- Forward-only. No rollback.

BEGIN;

DELETE FROM core.worker_registry WHERE status = 'abandoned';

ALTER TABLE core.worker_registry DROP COLUMN status;

COMMIT;
