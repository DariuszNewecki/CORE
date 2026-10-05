-- 20261005c_adr169_changes_and_outside_writes.sql
--
-- ADR-169 slice 3.
--
-- D4 — core.state_changes: for each path that changed between two state
-- observations, three independent facts: governance provenance
-- (proposal / direct / unknown), producer provenance (authenticated /
-- git-asserted / unknown — git author metadata is asserted, never
-- authenticated), and persistence (committed / uncommitted).
--
-- D5 — core.outside_writes: every write CORE makes outside its own
-- repository (project new / onboard / scout / adopt-pack): target root, path,
-- operation, content hash, and what produced it. No content is stored.
--
-- Both append-only (ADR-169 D1): UPDATE is refused by trigger; DELETE stays
-- possible for a future retention rule.
--
-- Idempotent; one transaction.

BEGIN;

CREATE TABLE IF NOT EXISTS core.state_changes (
    change_id uuid DEFAULT gen_random_uuid() NOT NULL,
    observation_id uuid NOT NULL,
    previous_observation_id uuid NOT NULL,
    path text NOT NULL,
    governance_provenance text NOT NULL,
    producer_provenance text NOT NULL,
    persistence text NOT NULL,
    commit_sha text,
    producer_identity text,
    proposal_id text,
    CONSTRAINT state_changes_pkey PRIMARY KEY (change_id),
    CONSTRAINT state_changes_governance_provenance_check
        CHECK (governance_provenance = ANY (ARRAY['proposal'::text, 'direct'::text, 'unknown'::text])),
    CONSTRAINT state_changes_producer_provenance_check
        CHECK (producer_provenance = ANY (ARRAY['authenticated'::text, 'git-asserted'::text, 'unknown'::text])),
    CONSTRAINT state_changes_persistence_check
        CHECK (persistence = ANY (ARRAY['committed'::text, 'uncommitted'::text])),
    CONSTRAINT state_changes_observation_id_fkey
        FOREIGN KEY (observation_id) REFERENCES core.state_observations(observation_id) ON DELETE CASCADE,
    CONSTRAINT state_changes_previous_observation_id_fkey
        FOREIGN KEY (previous_observation_id) REFERENCES core.state_observations(observation_id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_state_changes_observation_id
    ON core.state_changes USING btree (observation_id);
CREATE INDEX IF NOT EXISTS idx_state_changes_path
    ON core.state_changes USING btree (path text_pattern_ops);

COMMENT ON TABLE core.state_changes IS
    'ADR-169 D4: per changed path between two state observations -- governance provenance, producer provenance (git-asserted is never authenticated), persistence. Append-only.';

CREATE TABLE IF NOT EXISTS core.outside_writes (
    write_id uuid DEFAULT gen_random_uuid() NOT NULL,
    recorded_at timestamp with time zone DEFAULT now() NOT NULL,
    target_root text NOT NULL,
    path text NOT NULL,
    operation text NOT NULL,
    content_hash text,
    produced_by text NOT NULL,
    proposal_id text,
    CONSTRAINT outside_writes_pkey PRIMARY KEY (write_id),
    CONSTRAINT outside_writes_operation_check
        CHECK (operation = ANY (ARRAY['write'::text, 'delete'::text]))
);

CREATE INDEX IF NOT EXISTS idx_outside_writes_recorded_at
    ON core.outside_writes USING btree (recorded_at DESC);

COMMENT ON TABLE core.outside_writes IS
    'ADR-169 D5: every write CORE makes outside its own repository -- target, path, operation, sha256 of the written bytes, producer. No content. Append-only.';

CREATE OR REPLACE FUNCTION core.adr169_append_only() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    RAISE EXCEPTION '% is append-only (ADR-169)', TG_TABLE_NAME;
END;
$$;

DROP TRIGGER IF EXISTS trg_state_changes_append_only ON core.state_changes;
CREATE TRIGGER trg_state_changes_append_only
    BEFORE UPDATE ON core.state_changes
    FOR EACH ROW EXECUTE FUNCTION core.adr169_append_only();

DROP TRIGGER IF EXISTS trg_outside_writes_append_only ON core.outside_writes;
CREATE TRIGGER trg_outside_writes_append_only
    BEFORE UPDATE ON core.outside_writes
    FOR EACH ROW EXECUTE FUNCTION core.adr169_append_only();

COMMIT;
