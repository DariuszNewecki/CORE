-- FILE: sql/001_consolidated_schema.sql
--
-- This is the single, canonical source of truth for the CORE operational database schema.
-- It is generated from a clean snapshot of the working database and is designed to be
-- IDEMPOTENT. It can be run safely on a new or existing database.
--

-- =============================================================================
-- SECTION 1: CORE SCHEMA & HELPERS
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS core;

CREATE OR REPLACE FUNCTION core.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- =============================================================================
-- SECTION 2: MIGRATION & AUDIT TABLES
-- =============================================================================
CREATE TABLE IF NOT EXISTS core._migrations (
    id text NOT NULL PRIMARY KEY,
    applied_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS core.audit_runs (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    commit_sha character(40),
    score numeric(4,3),
    passed boolean NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone
);

-- =============================================================================
-- SECTION 3: KNOWLEDGE & SYMBOL CATALOG
-- =============================================================================
CREATE TABLE IF NOT EXISTS core.domains (
    key text NOT NULL PRIMARY KEY,
    title text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS core.capabilities (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    title text NOT NULL,
    owner text NOT NULL,
    implementing_files jsonb,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    name text NOT NULL,
    objective text,
    domain text DEFAULT 'general'::text NOT NULL,
    tags jsonb DEFAULT '[]'::jsonb NOT NULL,
    status text DEFAULT 'Active'::text NOT NULL,
    CONSTRAINT capabilities_status_chk_new CHECK ((status = ANY (ARRAY['Active'::text, 'Draft'::text, 'Deprecated'::text])))
);

CREATE TABLE IF NOT EXISTS core.symbols (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    module text NOT NULL,
    qualname text NOT NULL,
    kind text NOT NULL,
    ast_signature text NOT NULL,
    fingerprint text NOT NULL, -- <<< THIS IS THE FIX: No longer UNIQUE
    state text DEFAULT 'discovered'::text NOT NULL,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_seen timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    uuid text UNIQUE,
    symbol_path text UNIQUE,
    is_public boolean NOT NULL DEFAULT true,
    key text,
    vector_id text,
    CONSTRAINT symbols_kind_chk CHECK ((kind = ANY (ARRAY['function'::text, 'class'::text, 'method'::text, 'module'::text]))),
    CONSTRAINT symbols_state_chk CHECK ((state = ANY (ARRAY['discovered'::text, 'classified'::text, 'bound'::text, 'verified'::text, 'deprecated'::text])))
);

CREATE TABLE IF NOT EXISTS core.symbol_capabilities (
    symbol_uuid text NOT NULL,
    capability_key text NOT NULL,
    PRIMARY KEY (symbol_uuid, capability_key)
);

CREATE TABLE IF NOT EXISTS core.symbol_capability_links (
    symbol_id uuid NOT NULL REFERENCES core.symbols(id) ON DELETE CASCADE,
    capability_id uuid NOT NULL REFERENCES core.capabilities(id) ON DELETE CASCADE,
    confidence numeric NOT NULL,
    source text NOT NULL,
    verified boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    PRIMARY KEY (symbol_id, capability_id, source),
    CONSTRAINT symbol_capability_links_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))),
    CONSTRAINT symbol_capability_links_source_check CHECK ((source = ANY (ARRAY['auditor-infer'::text, 'manual'::text, 'rule'::text])))
);

-- =============================================================================
-- SECTION 4: OPERATIONAL & RUNTIME TABLES
-- =============================================================================
CREATE TABLE IF NOT EXISTS core.llm_resources (
    name text NOT NULL PRIMARY KEY,
    provided_capabilities jsonb DEFAULT '[]'::jsonb NOT NULL,
    env_prefix text NOT NULL UNIQUE,
    performance_metadata jsonb
);

CREATE TABLE IF NOT EXISTS core.cognitive_roles (
    role text NOT NULL PRIMARY KEY,
    description text,
    assigned_resource text REFERENCES core.llm_resources(name),
    required_capabilities jsonb DEFAULT '[]'::jsonb NOT NULL
);

CREATE TABLE IF NOT EXISTS core.cli_commands (
    name text NOT NULL PRIMARY KEY,
    module text NOT NULL,
    entrypoint text NOT NULL,
    summary text,
    category text
);

CREATE TABLE IF NOT EXISTS core.runtime_services (
    name text NOT NULL PRIMARY KEY,
    implementation text NOT NULL UNIQUE
);

-- =============================================================================
-- SECTION 5: GOVERNANCE & PROPOSAL TABLES
-- =============================================================================
CREATE TABLE IF NOT EXISTS core.proposals (
    id bigserial PRIMARY KEY,
    target_path text NOT NULL,
    content_sha256 character(64) NOT NULL,
    justification text NOT NULL,
    risk_tier text DEFAULT 'low'::text,
    is_critical boolean DEFAULT false NOT NULL,
    status text DEFAULT 'open'::text NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    created_by text NOT NULL,
    CONSTRAINT proposals_risk_tier_check CHECK ((risk_tier = ANY (ARRAY['low'::text, 'medium'::text, 'high'::text]))),
    CONSTRAINT proposals_status_check CHECK ((status = ANY (ARRAY['open'::text, 'approved'::text, 'rejected'::text, 'superseded'::text])))
);

CREATE TABLE IF NOT EXISTS core.proposal_signatures (
    proposal_id bigint NOT NULL REFERENCES core.proposals(id) ON DELETE CASCADE,
    approver_identity text NOT NULL,
    signature_base64 text NOT NULL,
    signed_at timestamp with time zone DEFAULT now() NOT NULL,
    is_valid boolean DEFAULT true NOT NULL,
    PRIMARY KEY (proposal_id, approver_identity)
);

-- =============================================================================
-- SECTION 6: EXPORT & MANIFEST TABLES
-- =============================================================================
CREATE TABLE IF NOT EXISTS core.export_manifests (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    exported_at timestamp with time zone DEFAULT now() NOT NULL,
    who text,
    environment text,
    notes text
);

CREATE TABLE IF NOT EXISTS core.export_digests (
    path text NOT NULL PRIMARY KEY,
    sha256 text NOT NULL,
    manifest_id uuid NOT NULL REFERENCES core.export_manifests(id) ON DELETE CASCADE,
    exported_at timestamp with time zone DEFAULT now() NOT NULL
);

CREATE TABLE IF NOT EXISTS core.northstar (
    id uuid DEFAULT gen_random_uuid() NOT NULL PRIMARY KEY,
    mission text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);

-- =============================================================================
-- SECTION 7: VIEWS, INDEXES & TRIGGERS
-- =============================================================================

-- VIEWS
CREATE OR REPLACE VIEW core.v_orphan_symbols AS
 SELECT s.id, s.module, s.qualname, s.kind, s.ast_signature, s.fingerprint, s.state, s.first_seen, s.last_seen, s.created_at, s.updated_at
   FROM (core.symbols s
     LEFT JOIN core.symbol_capability_links l ON ((l.symbol_id = s.id)))
  WHERE ((l.symbol_id IS NULL) AND (s.state <> 'deprecated'::text));

CREATE OR REPLACE VIEW core.v_verified_coverage AS
 SELECT c.id AS capability_id, c.name, count(l.symbol_id) AS verified_symbols
   FROM (core.capabilities c
     LEFT JOIN core.symbol_capability_links l ON (((l.capability_id = c.id) AND (l.verified = true))))
  GROUP BY c.id, c.name;

CREATE OR REPLACE VIEW core.knowledge_graph AS
SELECT
    s.uuid,
    s.key AS capability,
    s.symbol_path,
    s.module as file_path,
    s.qualname as name,
    s.kind as type,
    s.qualname as title,
    'TBD' as intent,
    'unassigned_agent' as owner,
    s.state as status,
    s.is_public,
    s.fingerprint as structural_hash,
    s.vector_id,
    s.updated_at AS last_updated,
    '[]'::jsonb AS tags,
    '[]'::jsonb AS calls,
    '[]'::jsonb AS parameters,
    '[]'::jsonb AS base_classes,
    (s.kind = 'class') AS is_class,
    (s.qualname LIKE 'Test%') AS is_test,
    0 AS line_number,
    0 AS end_line_number,
    NULL AS source_code,
    NULL AS docstring,
    NULL AS entry_point_type,
    NULL AS entry_point_justification,
    NULL AS parent_class_key,
    (s.kind = 'function' AND s.qualname LIKE 'async%') AS is_async
FROM
    core.symbols s;

-- INDEXES
CREATE UNIQUE INDEX IF NOT EXISTS capabilities_domain_name_uidx ON core.capabilities USING btree (lower(domain), lower(name));
CREATE UNIQUE INDEX IF NOT EXISTS uq_symbols_key ON core.symbols (key) WHERE key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_domains_key ON core.domains USING btree (key);
CREATE INDEX IF NOT EXISTS idx_symbol_capabilities_capability_key ON core.symbol_capabilities USING btree (capability_key);
CREATE INDEX IF NOT EXISTS links_capability_idx ON core.symbol_capability_links USING btree (capability_id);
CREATE INDEX IF NOT EXISTS links_symbol_idx ON core.symbol_capability_links USING btree (symbol_id);
CREATE INDEX IF NOT EXISTS links_verified_idx ON core.symbol_capability_links USING btree (verified);
-- NO LONGER UNIQUE: CREATE UNIQUE INDEX IF NOT EXISTS symbols_fingerprint_uidx ON core.symbols USING btree (fingerprint);
CREATE INDEX IF NOT EXISTS symbols_qualname_idx ON core.symbols USING btree (qualname);
CREATE INDEX IF NOT EXISTS symbols_state_idx ON core.symbols USING btree (state);

-- TRIGGERS
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_capabilities_updated_at') THEN
    CREATE TRIGGER trg_capabilities_updated_at BEFORE UPDATE ON core.capabilities FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_symbols_updated_at') THEN
    CREATE TRIGGER trg_symbols_updated_at BEFORE UPDATE ON core.symbols FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();
  END IF;
END$$;