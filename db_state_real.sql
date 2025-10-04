--
-- PostgreSQL database dump
--

\restrict rpnmaqgPqCoFD00V5NkH19WZqL8KsPiaYo7hxwmzoGus2lvY0HKmArP9Q7SisTz

-- Dumped from database version 16.8 (Ubuntu 16.8-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.10 (Ubuntu 16.10-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'SQL_ASCII';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: core; Type: SCHEMA; Schema: -; Owner: core
--

CREATE SCHEMA core;


ALTER SCHEMA core OWNER TO core;

--
-- Name: apply_symbols_staging(); Type: FUNCTION; Schema: core; Owner: lira_user
--

CREATE FUNCTION core.apply_symbols_staging() RETURNS void
    LANGUAGE plpgsql
    AS $_$
DECLARE
  v_now TIMESTAMPTZ := now();
BEGIN
  INSERT INTO core.symbols (
    id, uuid, symbol_path, module, qualname, kind, ast_signature,
    fingerprint, state, first_seen, last_seen, created_at, updated_at
  )
  SELECT
    gen_random_uuid(),
    s.uuid,
    s.symbol_path,
    COALESCE(
      NULLIF(regexp_replace(regexp_replace(s.file_path, '\.py$', '', 'g'), '[/\\]', '.', 'g'),''),
      'unknown'
    ) AS module,
    s.symbol_path AS qualname,
    'module'      AS kind,
    ''            AS ast_signature,
    s.structural_hash AS fingerprint,
    'discovered'  AS state,
    v_now, v_now, v_now, v_now
  FROM (
    SELECT * FROM public.core_symbols_staging
    UNION ALL
    SELECT * FROM core.core_symbols_staging
  ) s
  ON CONFLICT (symbol_path) DO UPDATE
    SET fingerprint = EXCLUDED.fingerprint,
        last_seen   = v_now,
        updated_at  = v_now;

  TRUNCATE TABLE public.core_symbols_staging;
  TRUNCATE TABLE core.core_symbols_staging;
END;
$_$;


ALTER FUNCTION core.apply_symbols_staging() OWNER TO lira_user;

--
-- Name: set_updated_at(); Type: FUNCTION; Schema: core; Owner: core
--

CREATE FUNCTION core.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;


ALTER FUNCTION core.set_updated_at() OWNER TO core;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _migrations; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core._migrations (
    id text NOT NULL,
    applied_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE core._migrations OWNER TO core;

--
-- Name: audit_runs; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.audit_runs (
    id bigint NOT NULL,
    source text NOT NULL,
    commit_sha character(40),
    score numeric(4,3),
    passed boolean NOT NULL,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone
);


ALTER TABLE core.audit_runs OWNER TO core;

--
-- Name: audit_runs_id_seq; Type: SEQUENCE; Schema: core; Owner: core
--

CREATE SEQUENCE core.audit_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE core.audit_runs_id_seq OWNER TO core;

--
-- Name: audit_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: core
--

ALTER SEQUENCE core.audit_runs_id_seq OWNED BY core.audit_runs.id;


--
-- Name: capabilities; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.capabilities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
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


ALTER TABLE core.capabilities OWNER TO core;

--
-- Name: cli_commands; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.cli_commands (
    name text NOT NULL,
    module text NOT NULL,
    entrypoint text NOT NULL,
    summary text,
    category text
);


ALTER TABLE core.cli_commands OWNER TO core;

--
-- Name: cognitive_roles; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.cognitive_roles (
    role text NOT NULL,
    description text,
    assigned_resource text,
    required_capabilities jsonb DEFAULT '[]'::jsonb NOT NULL
);


ALTER TABLE core.cognitive_roles OWNER TO core;

--
-- Name: core_symbols_staging; Type: TABLE; Schema: core; Owner: lira_user
--

CREATE TABLE core.core_symbols_staging (
    uuid text,
    symbol_path text,
    file_path text,
    structural_hash text,
    is_public boolean DEFAULT true
);


ALTER TABLE core.core_symbols_staging OWNER TO lira_user;

--
-- Name: domains; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.domains (
    key text NOT NULL,
    title text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE core.domains OWNER TO core;

--
-- Name: export_digests; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.export_digests (
    path text NOT NULL,
    sha256 text NOT NULL,
    manifest_id uuid NOT NULL,
    exported_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE core.export_digests OWNER TO core;

--
-- Name: export_manifests; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.export_manifests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    exported_at timestamp with time zone DEFAULT now() NOT NULL,
    who text,
    environment text,
    notes text
);


ALTER TABLE core.export_manifests OWNER TO core;

--
-- Name: llm_resources; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.llm_resources (
    name text NOT NULL,
    provided_capabilities jsonb DEFAULT '[]'::jsonb NOT NULL,
    env_prefix text NOT NULL,
    performance_metadata jsonb
);


ALTER TABLE core.llm_resources OWNER TO core;

--
-- Name: northstar; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.northstar (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    mission text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE core.northstar OWNER TO core;

--
-- Name: proposal_signatures; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.proposal_signatures (
    proposal_id bigint NOT NULL,
    approver_identity text NOT NULL,
    signature_base64 text NOT NULL,
    signed_at timestamp with time zone DEFAULT now() NOT NULL,
    is_valid boolean DEFAULT true NOT NULL
);


ALTER TABLE core.proposal_signatures OWNER TO core;

--
-- Name: proposals; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.proposals (
    id bigint NOT NULL,
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


ALTER TABLE core.proposals OWNER TO core;

--
-- Name: proposals_id_seq; Type: SEQUENCE; Schema: core; Owner: core
--

CREATE SEQUENCE core.proposals_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE core.proposals_id_seq OWNER TO core;

--
-- Name: proposals_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: core
--

ALTER SEQUENCE core.proposals_id_seq OWNED BY core.proposals.id;


--
-- Name: runtime_services; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.runtime_services (
    name text NOT NULL,
    implementation text NOT NULL
);


ALTER TABLE core.runtime_services OWNER TO core;

--
-- Name: symbol_capabilities; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.symbol_capabilities (
    symbol_uuid text NOT NULL,
    capability_key text NOT NULL
);


ALTER TABLE core.symbol_capabilities OWNER TO core;

--
-- Name: symbol_capability_links; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.symbol_capability_links (
    symbol_id uuid NOT NULL,
    capability_id uuid NOT NULL,
    confidence numeric NOT NULL,
    source text NOT NULL,
    verified boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT symbol_capability_links_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))),
    CONSTRAINT symbol_capability_links_source_check CHECK ((source = ANY (ARRAY['auditor-infer'::text, 'manual'::text, 'rule'::text])))
);


ALTER TABLE core.symbol_capability_links OWNER TO core;

--
-- Name: symbols; Type: TABLE; Schema: core; Owner: core
--

CREATE TABLE core.symbols (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    module text NOT NULL,
    qualname text NOT NULL,
    kind text NOT NULL,
    ast_signature text NOT NULL,
    fingerprint text NOT NULL,
    state text DEFAULT 'discovered'::text NOT NULL,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_seen timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    uuid text,
    symbol_path text,
    CONSTRAINT symbols_kind_chk CHECK ((kind = ANY (ARRAY['function'::text, 'class'::text, 'method'::text, 'module'::text]))),
    CONSTRAINT symbols_state_chk CHECK ((state = ANY (ARRAY['discovered'::text, 'classified'::text, 'bound'::text, 'verified'::text, 'deprecated'::text])))
);


ALTER TABLE core.symbols OWNER TO core;

--
-- Name: v_orphan_symbols; Type: VIEW; Schema: core; Owner: core
--

CREATE VIEW core.v_orphan_symbols AS
 SELECT s.id,
    s.module,
    s.qualname,
    s.kind,
    s.ast_signature,
    s.fingerprint,
    s.state,
    s.first_seen,
    s.last_seen,
    s.created_at,
    s.updated_at
   FROM (core.symbols s
     LEFT JOIN core.symbol_capability_links l ON ((l.symbol_id = s.id)))
  WHERE ((l.symbol_id IS NULL) AND (s.state <> 'deprecated'::text));


ALTER VIEW core.v_orphan_symbols OWNER TO core;

--
-- Name: v_verified_coverage; Type: VIEW; Schema: core; Owner: core
--

CREATE VIEW core.v_verified_coverage AS
 SELECT c.id AS capability_id,
    c.name,
    count(l.symbol_id) AS verified_symbols
   FROM (core.capabilities c
     LEFT JOIN core.symbol_capability_links l ON (((l.capability_id = c.id) AND (l.verified = true))))
  GROUP BY c.id, c.name;


ALTER VIEW core.v_verified_coverage OWNER TO core;

--
-- Name: audit_runs id; Type: DEFAULT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.audit_runs ALTER COLUMN id SET DEFAULT nextval('core.audit_runs_id_seq'::regclass);


--
-- Name: proposals id; Type: DEFAULT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.proposals ALTER COLUMN id SET DEFAULT nextval('core.proposals_id_seq'::regclass);


--
-- Name: _migrations _migrations_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core._migrations
    ADD CONSTRAINT _migrations_pkey PRIMARY KEY (id);


--
-- Name: audit_runs audit_runs_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.audit_runs
    ADD CONSTRAINT audit_runs_pkey PRIMARY KEY (id);


--
-- Name: capabilities capabilities_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.capabilities
    ADD CONSTRAINT capabilities_pkey PRIMARY KEY (id);


--
-- Name: cli_commands cli_commands_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.cli_commands
    ADD CONSTRAINT cli_commands_pkey PRIMARY KEY (name);


--
-- Name: cognitive_roles cognitive_roles_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.cognitive_roles
    ADD CONSTRAINT cognitive_roles_pkey PRIMARY KEY (role);


--
-- Name: domains domains_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.domains
    ADD CONSTRAINT domains_pkey PRIMARY KEY (key);


--
-- Name: export_digests export_digests_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.export_digests
    ADD CONSTRAINT export_digests_pkey PRIMARY KEY (path);


--
-- Name: export_manifests export_manifests_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.export_manifests
    ADD CONSTRAINT export_manifests_pkey PRIMARY KEY (id);


--
-- Name: llm_resources llm_resources_env_prefix_key; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.llm_resources
    ADD CONSTRAINT llm_resources_env_prefix_key UNIQUE (env_prefix);


--
-- Name: llm_resources llm_resources_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.llm_resources
    ADD CONSTRAINT llm_resources_pkey PRIMARY KEY (name);


--
-- Name: northstar northstar_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.northstar
    ADD CONSTRAINT northstar_pkey PRIMARY KEY (id);


--
-- Name: proposal_signatures proposal_signatures_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.proposal_signatures
    ADD CONSTRAINT proposal_signatures_pkey PRIMARY KEY (proposal_id, approver_identity);


--
-- Name: proposals proposals_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.proposals
    ADD CONSTRAINT proposals_pkey PRIMARY KEY (id);


--
-- Name: runtime_services runtime_services_implementation_key; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.runtime_services
    ADD CONSTRAINT runtime_services_implementation_key UNIQUE (implementation);


--
-- Name: runtime_services runtime_services_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.runtime_services
    ADD CONSTRAINT runtime_services_pkey PRIMARY KEY (name);


--
-- Name: symbol_capabilities symbol_capabilities_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.symbol_capabilities
    ADD CONSTRAINT symbol_capabilities_pkey PRIMARY KEY (symbol_uuid, capability_key);


--
-- Name: symbol_capability_links symbol_capability_links_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.symbol_capability_links
    ADD CONSTRAINT symbol_capability_links_pkey PRIMARY KEY (symbol_id, capability_id, source);


--
-- Name: symbols symbols_pkey; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.symbols
    ADD CONSTRAINT symbols_pkey PRIMARY KEY (id);


--
-- Name: symbols symbols_symbol_path_uidx; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.symbols
    ADD CONSTRAINT symbols_symbol_path_uidx UNIQUE (symbol_path);


--
-- Name: symbols symbols_uuid_key; Type: CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.symbols
    ADD CONSTRAINT symbols_uuid_key UNIQUE (uuid);


--
-- Name: capabilities_domain_name_uidx; Type: INDEX; Schema: core; Owner: core
--

CREATE UNIQUE INDEX capabilities_domain_name_uidx ON core.capabilities USING btree (lower(domain), lower(name));


--
-- Name: core_symbols_staging_symbol_path_idx; Type: INDEX; Schema: core; Owner: lira_user
--

CREATE INDEX core_symbols_staging_symbol_path_idx ON core.core_symbols_staging USING btree (symbol_path);


--
-- Name: idx_domains_key; Type: INDEX; Schema: core; Owner: core
--

CREATE INDEX idx_domains_key ON core.domains USING btree (key);


--
-- Name: idx_symbol_capabilities_capability_key; Type: INDEX; Schema: core; Owner: core
--

CREATE INDEX idx_symbol_capabilities_capability_key ON core.symbol_capabilities USING btree (capability_key);


--
-- Name: links_capability_idx; Type: INDEX; Schema: core; Owner: core
--

CREATE INDEX links_capability_idx ON core.symbol_capability_links USING btree (capability_id);


--
-- Name: links_symbol_idx; Type: INDEX; Schema: core; Owner: core
--

CREATE INDEX links_symbol_idx ON core.symbol_capability_links USING btree (symbol_id);


--
-- Name: links_verified_idx; Type: INDEX; Schema: core; Owner: core
--

CREATE INDEX links_verified_idx ON core.symbol_capability_links USING btree (verified);


--
-- Name: symbols_fingerprint_uidx; Type: INDEX; Schema: core; Owner: core
--

CREATE UNIQUE INDEX symbols_fingerprint_uidx ON core.symbols USING btree (fingerprint);


--
-- Name: symbols_qualname_idx; Type: INDEX; Schema: core; Owner: core
--

CREATE INDEX symbols_qualname_idx ON core.symbols USING btree (qualname);


--
-- Name: symbols_state_idx; Type: INDEX; Schema: core; Owner: core
--

CREATE INDEX symbols_state_idx ON core.symbols USING btree (state);


--
-- Name: capabilities trg_capabilities_updated_at; Type: TRIGGER; Schema: core; Owner: core
--

CREATE TRIGGER trg_capabilities_updated_at BEFORE UPDATE ON core.capabilities FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


--
-- Name: symbols trg_symbols_updated_at; Type: TRIGGER; Schema: core; Owner: core
--

CREATE TRIGGER trg_symbols_updated_at BEFORE UPDATE ON core.symbols FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


--
-- Name: cognitive_roles cognitive_roles_assigned_resource_fkey; Type: FK CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.cognitive_roles
    ADD CONSTRAINT cognitive_roles_assigned_resource_fkey FOREIGN KEY (assigned_resource) REFERENCES core.llm_resources(name);


--
-- Name: export_digests export_digests_manifest_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.export_digests
    ADD CONSTRAINT export_digests_manifest_id_fkey FOREIGN KEY (manifest_id) REFERENCES core.export_manifests(id) ON DELETE CASCADE;


--
-- Name: symbol_capability_links fk_capability; Type: FK CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.symbol_capability_links
    ADD CONSTRAINT fk_capability FOREIGN KEY (capability_id) REFERENCES core.capabilities(id) ON DELETE CASCADE;


--
-- Name: proposal_signatures proposal_signatures_proposal_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.proposal_signatures
    ADD CONSTRAINT proposal_signatures_proposal_id_fkey FOREIGN KEY (proposal_id) REFERENCES core.proposals(id) ON DELETE CASCADE;


--
-- Name: symbol_capability_links symbol_capability_links_symbol_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: core
--

ALTER TABLE ONLY core.symbol_capability_links
    ADD CONSTRAINT symbol_capability_links_symbol_id_fkey FOREIGN KEY (symbol_id) REFERENCES core.symbols(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict rpnmaqgPqCoFD00V5NkH19WZqL8KsPiaYo7hxwmzoGus2lvY0HKmArP9Q7SisTz

