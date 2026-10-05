-- 20261005b_adr169_cycle_trigger.sql
--
-- ADR-169 D1 slice 2 — the state ledger gains a third trigger, 'cycle': the
-- StateSensor worker appends an observation each cycle in which CORE's state
-- differs from the latest recorded observation (between boots and audit runs).
--
-- Widens the trigger CHECK only; existing rows already satisfy it.
--
-- Idempotent; one transaction.

BEGIN;

ALTER TABLE core.state_observations
    DROP CONSTRAINT IF EXISTS state_observations_trigger_check;
ALTER TABLE core.state_observations
    ADD CONSTRAINT state_observations_trigger_check
        CHECK (trigger = ANY (ARRAY['boot'::text, 'audit_run'::text, 'cycle'::text]));

COMMIT;
