-- 20261005_adr169_state_observations.sql
--
-- ADR-169 D1 — the state ledger. CORE records an observation of its own state
-- at daemon boot and with every persisted audit run: repository HEAD, the
-- working-tree paths that differ from HEAD, the law of record and the law
-- evaluated (ADR-169 D2) with their relationship, and the identity of the
-- code a booting process loaded.
--
-- Append-only (ADR-169 D1): rows are never updated. An UPDATE is refused by
-- trigger; DELETE stays possible for a future retention rule.
--
-- Idempotent; one transaction.

BEGIN;

CREATE TABLE IF NOT EXISTS core.state_observations (
    observation_id uuid DEFAULT gen_random_uuid() NOT NULL,
    observed_at timestamp with time zone DEFAULT now() NOT NULL,
    trigger text NOT NULL,
    repo_root text NOT NULL,
    head_sha text,
    dirty_paths jsonb DEFAULT '[]'::jsonb NOT NULL,
    law_relationship text NOT NULL,
    law_record_digest text,
    law_evaluated_digest text,
    law_drift_paths jsonb DEFAULT '[]'::jsonb NOT NULL,
    loaded_code_identity text,
    audit_run_id uuid,
    CONSTRAINT state_observations_pkey PRIMARY KEY (observation_id),
    CONSTRAINT state_observations_trigger_check
        CHECK (trigger = ANY (ARRAY['boot'::text, 'audit_run'::text])),
    CONSTRAINT state_observations_law_relationship_check
        CHECK (law_relationship = ANY (ARRAY['MATCH'::text, 'DRIFT'::text, 'UNKNOWN'::text])),
    CONSTRAINT state_observations_audit_run_id_fkey
        FOREIGN KEY (audit_run_id) REFERENCES core.audit_runs(run_id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_state_observations_observed_at
    ON core.state_observations USING btree (observed_at DESC);

COMMENT ON TABLE core.state_observations IS
    'ADR-169 D1 state ledger: append-only observations of HEAD, dirty paths, law of record vs law evaluated, and loaded code identity.';

CREATE OR REPLACE FUNCTION core.state_observations_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION 'core.state_observations is append-only (ADR-169 D1)';
END;
$$;

DROP TRIGGER IF EXISTS trg_state_observations_append_only ON core.state_observations;
CREATE TRIGGER trg_state_observations_append_only
    BEFORE UPDATE ON core.state_observations
    FOR EACH ROW EXECUTE FUNCTION core.state_observations_append_only();

COMMIT;
