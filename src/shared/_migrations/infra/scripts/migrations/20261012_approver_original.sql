-- 20261012_approver_original.sql
--
-- One approver principal (governor redesign 2026-10-12): approved_by holds the
-- principal ('governor', or the worker tag for automatic approvals); the
-- identity originally recorded (an OS account, a free-text name, 'unknown')
-- moves to approved_by_original, so no history is lost.
--
-- Adds the column only; the data move is a governor-run script.
-- Idempotent; one transaction.

BEGIN;

ALTER TABLE core.autonomous_proposals
    ADD COLUMN IF NOT EXISTS approved_by_original text;

COMMIT;
