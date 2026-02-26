--
-- PostgreSQL database dump
--

-- Dumped from database version 16.8 (Ubuntu 16.8-0ubuntu0.24.04.1)
-- Dumped by pg_dump version 16.8 (Ubuntu 16.8-0ubuntu0.24.04.1)

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
-- Name: core; Type: SCHEMA; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE SCHEMA IF NOT EXISTS public;
CREATE SCHEMA IF NOT EXISTS core;


--
-- Name: SCHEMA core; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA core IS '
DECORATOR METADATA MIGRATION PATH:

Phase 1 (CURRENT): Decorators in source, policies in .intent/
- CORE can detect violations, suggest fixes
- Cannot autonomously generate new decorated functions

Phase 2 (NEXT): Enhanced policies added
- Add decorator_governance.yaml to .intent/charter/policies/
- CORE can now autonomously generate correct decorators
- Still requires source modification for changes

Phase 3 (FUTURE): Run this SQL migration
- Decorator metadata stored in DB
- CORE queries DB for decorator requirements
- Decorator rules updatable without code changes

Phase 4 (AUTONOMOUS): CORE.NG generates all code from DB
- Full autonomous code generation
- "Last programmer you''ll ever need"

USAGE EXAMPLES:

-- Check which symbols need decorators:
SELECT * FROM core.v_symbols_missing_decorators;

-- Get decorator stack for a symbol:
SELECT * FROM core.v_symbol_decorator_stack WHERE symbol_path = ''body.cli.check:audit'';

-- Generate decorator code:
SELECT core.generate_decorator_code(''symbol-uuid-here'');

-- Add decorator manually:
INSERT INTO core.symbol_decorators (symbol_id, decorator_id, order_index, parameters, source, reasoning)
SELECT
    s.id,
    dr.id,
    1,
    ''{"dangerous": false}''::jsonb,
    ''manual'',
    ''CLI command requires constitutional governance''
FROM core.symbols s, core.decorator_registry dr
WHERE s.symbol_path = ''body.cli.check:audit''
  AND dr.decorator_name = ''core_command'';
';



--
-- Name: SCHEMA public; Type: COMMENT; Schema: -; Owner: -
--

COMMENT ON SCHEMA public IS 'standard public schema';


--
-- Name: non_empty_text; Type: DOMAIN; Schema: core; Owner: -
--

CREATE DOMAIN core.non_empty_text AS text
	CONSTRAINT non_empty_text_check CHECK ((TRIM(BOTH FROM VALUE) <> ''::text));


--
-- Name: probability; Type: DOMAIN; Schema: core; Owner: -
--

CREATE DOMAIN core.probability AS numeric(3,2)
	CONSTRAINT probability_check CHECK (((VALUE >= (0)::numeric) AND (VALUE <= (1)::numeric)));


--
-- Name: semantic_version; Type: DOMAIN; Schema: core; Owner: -
--

CREATE DOMAIN core.semantic_version AS text;


--
-- Name: severity_level; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.severity_level AS ENUM (
    'info',
    'warning',
    'error',
    'critical'
);


--
-- Name: symbol_kind; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.symbol_kind AS ENUM (
    'function',
    'class',
    'method',
    'module'
);


--
-- Name: task_status; Type: TYPE; Schema: core; Owner: -
--

CREATE TYPE core.task_status AS ENUM (
    'pending',
    'planning',
    'executing',
    'validating',
    'completed',
    'failed',
    'blocked'
);


--
-- Name: analyze_index_usage(); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.analyze_index_usage() RETURNS TABLE(tablename text, indexname text, index_size text, idx_scan bigint, idx_tup_read bigint, idx_tup_fetch bigint, usage_ratio numeric)
    LANGUAGE sql SECURITY DEFINER
    AS $$
SELECT
    schemaname || '.' || relname as tablename,
    indexrelname as indexname,
    pg_size_pretty(pg_relation_size(indexrelid)) as index_size,
    idx_scan,
    idx_tup_read,
    idx_tup_fetch,
    CASE WHEN idx_scan > 0
        THEN round((idx_tup_fetch::numeric / NULLIF(idx_scan, 0)), 2)
        ELSE 0
    END as usage_ratio
FROM pg_stat_user_indexes
WHERE schemaname = 'core'
ORDER BY idx_scan DESC, relname;
$$;


--
-- Name: audit_symbols_changes(); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.audit_symbols_changes() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO core.symbols_audit (operation, symbol_id, new_data)
        VALUES ('I', NEW.id, to_jsonb(NEW));
    ELSIF TG_OP = 'UPDATE' THEN
        INSERT INTO core.symbols_audit (operation, symbol_id, old_data, new_data)
        VALUES ('U', NEW.id, to_jsonb(OLD), to_jsonb(NEW));
    ELSIF TG_OP = 'DELETE' THEN
        INSERT INTO core.symbols_audit (operation, symbol_id, old_data)
        VALUES ('D', OLD.id, to_jsonb(OLD));
    END IF;
    RETURN NULL;
END;
$$;


--
-- Name: cleanup_observability_logs(); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.cleanup_observability_logs() RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM core.observability_logs
    WHERE timestamp < NOW() - INTERVAL '90 days';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RAISE NOTICE 'Cleaned up % logs older than 90 days', deleted_count;
END;
$$;


--
-- Name: FUNCTION cleanup_observability_logs(); Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON FUNCTION core.cleanup_observability_logs() IS 'Delete logs older than 90 days per observability policy';


--
-- Name: cleanup_observability_metrics(); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.cleanup_observability_metrics() RETURNS void
    LANGUAGE plpgsql
    AS $$
DECLARE
    deleted_count INTEGER;
BEGIN
    DELETE FROM core.observability_metrics
    WHERE timestamp < NOW() - INTERVAL '1 year';

    GET DIAGNOSTICS deleted_count = ROW_COUNT;

    RAISE NOTICE 'Cleaned up % metrics older than 1 year', deleted_count;
END;
$$;


--
-- Name: FUNCTION cleanup_observability_metrics(); Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON FUNCTION core.cleanup_observability_metrics() IS 'Delete metrics older than 1 year per observability policy';


--
-- Name: generate_decorator_code(uuid); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.generate_decorator_code(p_symbol_id uuid) RETURNS text
    LANGUAGE plpgsql STABLE
    AS $$
DECLARE
    decorator_code text := '';
    rec record;
BEGIN
    FOR rec IN
        SELECT
            dr.decorator_name,
            sd.parameters,
            sd.order_index
        FROM core.symbol_decorators sd
        JOIN core.decorator_registry dr ON dr.id = sd.decorator_id
        WHERE sd.symbol_id = p_symbol_id
          AND sd.is_active = true
          AND dr.is_active = true
        ORDER BY sd.order_index
    LOOP
        -- Build decorator line
        decorator_code := decorator_code || '@' || rec.decorator_name;

        -- Add parameters if any
        IF rec.parameters IS NOT NULL AND rec.parameters != '{}'::jsonb THEN
            decorator_code := decorator_code || '(' ||
                             (SELECT string_agg(
                                 key || '=' ||
                                 CASE
                                     WHEN jsonb_typeof(value) = 'string' THEN '"' || value::text || '"'
                                     WHEN jsonb_typeof(value) = 'boolean' THEN value::text
                                     WHEN jsonb_typeof(value) = 'number' THEN value::text
                                     ELSE value::text
                                 END,
                                 ', '
                             )
                             FROM jsonb_each(rec.parameters)) ||
                             ')';
        END IF;

        decorator_code := decorator_code || E'\n';
    END LOOP;

    RETURN decorator_code;
END;
$$;


--
-- Name: FUNCTION generate_decorator_code(p_symbol_id uuid); Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON FUNCTION core.generate_decorator_code(p_symbol_id uuid) IS 'Generate Python decorator code for a symbol. Usage: SELECT core.generate_decorator_code(symbol_id);';


--
-- Name: get_symbol_id(text); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.get_symbol_id(path text) RETURNS uuid
    LANGUAGE sql STABLE
    AS $$
    SELECT id FROM core.symbols WHERE symbol_path = path;
$$;


--
-- Name: FUNCTION get_symbol_id(path text); Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON FUNCTION core.get_symbol_id(path text) IS 'Helper to look up symbol UUID by its natural key (symbol_path). Usage: get_symbol_id(''my.module:MyClass'')';


--
-- Name: refresh_materialized_view(text); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.refresh_materialized_view(view_name text) RETURNS TABLE(duration_ms integer, rows_affected integer)
    LANGUAGE plpgsql
    AS $$
DECLARE
    start_time timestamptz := now();
    rows_count integer;
    duration integer;
BEGIN
    INSERT INTO core.mv_refresh_log (view_name, last_refresh_started, triggered_by)
    VALUES (view_name, start_time, current_user)
    ON CONFLICT (view_name)
    DO UPDATE SET last_refresh_started = start_time, triggered_by = current_user;

    EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I', view_name);

    EXECUTE format('SELECT COUNT(*) FROM %I', view_name) INTO rows_count;

    duration := EXTRACT(EPOCH FROM (now() - start_time)) * 1000;

    UPDATE core.mv_refresh_log
    SET last_refresh_completed = now(),
        last_refresh_duration_ms = duration,
        rows_affected = rows_count
    WHERE mv_refresh_log.view_name = refresh_materialized_view.view_name;

    RETURN QUERY SELECT duration, rows_count;
END;
$$;


--
-- Name: FUNCTION refresh_materialized_view(view_name text); Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON FUNCTION core.refresh_materialized_view(view_name text) IS 'Refresh a materialized view with logging. Usage: SELECT * FROM core.refresh_materialized_view(''core.mv_symbol_usage_patterns'');';


--
-- Name: set_updated_at(); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;


--
-- Name: validate_symbol_array(); Type: FUNCTION; Schema: core; Owner: -
--

CREATE FUNCTION core.validate_symbol_array() RETURNS trigger
    LANGUAGE plpgsql
    AS $$
BEGIN
    -- Validate that all UUIDs in relevant_symbols array exist in symbols table
    IF NEW.relevant_symbols IS NOT NULL AND array_length(NEW.relevant_symbols, 1) > 0 THEN
        IF EXISTS (
            SELECT 1
            FROM unnest(NEW.relevant_symbols) AS sym_id
            LEFT JOIN core.symbols s ON s.id = sym_id
            WHERE s.id IS NULL
        ) THEN
            RAISE EXCEPTION 'Invalid symbol UUID found in relevant_symbols array';
        END IF;
    END IF;
    RETURN NEW;
END;
$$;


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: _migrations; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core._migrations (
    id text NOT NULL,
    applied_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: action_results; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.action_results (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    action_type character varying(100) NOT NULL,
    ok boolean NOT NULL,
    file_path character varying(500),
    error_message text,
    action_metadata jsonb,
    agent_id character varying(100),
    duration_ms integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: actions; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.actions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_id uuid NOT NULL,
    action_type text NOT NULL,
    target text,
    payload jsonb,
    result jsonb,
    success boolean NOT NULL,
    cognitive_role text NOT NULL,
    reasoning text,
    duration_ms integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT actions_action_type_check CHECK ((action_type = ANY (ARRAY['file_read'::text, 'file_write'::text, 'symbol_analysis'::text, 'llm_call'::text, 'shell_command'::text, 'validation'::text, 'vector_search'::text, 'test_run'::text])))
);


--
-- Name: agent_decisions; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.agent_decisions (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_id uuid NOT NULL,
    decision_point text NOT NULL,
    options_considered jsonb NOT NULL,
    chosen_option text NOT NULL,
    reasoning text NOT NULL,
    confidence core.probability NOT NULL,
    was_correct boolean,
    decided_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT agent_decisions_confidence_check CHECK ((((confidence)::numeric >= (0)::numeric) AND ((confidence)::numeric <= (1)::numeric)))
);


--
-- Name: agent_memory; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.agent_memory (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    cognitive_role text NOT NULL,
    memory_type text NOT NULL,
    content text NOT NULL,
    related_task_id uuid,
    relevance_score core.probability DEFAULT 1.0,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT agent_memory_memory_type_check CHECK ((memory_type = ANY (ARRAY['fact'::text, 'observation'::text, 'decision'::text, 'pattern'::text, 'error'::text]))),
    CONSTRAINT agent_memory_relevance_score_check CHECK ((((relevance_score)::numeric >= (0)::numeric) AND ((relevance_score)::numeric <= (1)::numeric)))
);


--
-- Name: audit_runs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.audit_runs (
    id bigint NOT NULL,
    source text NOT NULL,
    commit_sha character(40),
    score numeric(4,3),
    passed boolean NOT NULL,
    violations_found integer DEFAULT 0,
    started_at timestamp with time zone DEFAULT now() NOT NULL,
    finished_at timestamp with time zone
);


--
-- Name: audit_runs_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.audit_runs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_runs_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.audit_runs_id_seq OWNED BY core.audit_runs.id;


--
-- Name: capabilities; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.capabilities (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    name text NOT NULL,
    domain text DEFAULT 'general'::text NOT NULL,
    title text NOT NULL,
    objective text,
    owner text NOT NULL,
    dependencies jsonb DEFAULT '[]'::jsonb,
    test_coverage numeric(5,2),
    tags jsonb DEFAULT '[]'::jsonb NOT NULL,
    status text DEFAULT 'Active'::text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    key_suffix text,
    CONSTRAINT capabilities_status_check CHECK ((status = ANY (ARRAY['Active'::text, 'Draft'::text, 'Deprecated'::text]))),
    CONSTRAINT capabilities_tags_check CHECK ((jsonb_typeof(tags) = 'array'::text)),
    CONSTRAINT chk_test_coverage_range CHECK (((test_coverage >= (0)::numeric) AND (test_coverage <= (100)::numeric)))
);


--
-- Name: capability_cli_links; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.capability_cli_links (
    capability_id uuid NOT NULL,
    cli_command_name text NOT NULL
);


--
-- Name: cli_commands; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.cli_commands (
    name text NOT NULL,
    module text NOT NULL,
    entrypoint text NOT NULL,
    summary text,
    category text
);


--
-- Name: cognitive_roles; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.cognitive_roles (
    role text NOT NULL,
    description text,
    assigned_resource text,
    required_capabilities jsonb DEFAULT '[]'::jsonb,
    max_concurrent_tasks integer DEFAULT 1,
    specialization jsonb,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT cognitive_roles_required_capabilities_check CHECK ((jsonb_typeof(required_capabilities) = 'array'::text))
);


--
-- Name: constitutional_violations; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.constitutional_violations (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    rule_id text NOT NULL,
    symbol_id uuid,
    task_id uuid,
    severity text NOT NULL,
    description text NOT NULL,
    detected_at timestamp with time zone DEFAULT now() NOT NULL,
    resolved_at timestamp with time zone,
    resolution_notes text,
    CONSTRAINT constitutional_violations_severity_check CHECK ((severity = ANY (ARRAY['info'::text, 'warning'::text, 'error'::text, 'critical'::text])))
);


--
-- Name: context_packets; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.context_packets (
    packet_id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_id character varying(255) NOT NULL,
    task_type character varying(50) NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    privacy character varying(20) NOT NULL,
    remote_allowed boolean DEFAULT false NOT NULL,
    packet_hash character varying(64) NOT NULL,
    cache_key character varying(64),
    tokens_est integer DEFAULT 0 NOT NULL,
    size_bytes integer DEFAULT 0 NOT NULL,
    build_ms integer DEFAULT 0 NOT NULL,
    items_count integer DEFAULT 0 NOT NULL,
    redactions_count integer DEFAULT 0 NOT NULL,
    path text NOT NULL,
    metadata jsonb DEFAULT '{}'::jsonb NOT NULL,
    builder_version character varying(20) NOT NULL,
    CONSTRAINT context_packets_privacy_check CHECK (((privacy)::text = ANY ((ARRAY['local_only'::character varying, 'remote_allowed'::character varying])::text[]))),
    CONSTRAINT positive_metrics CHECK (((tokens_est >= 0) AND (size_bytes >= 0) AND (build_ms >= 0) AND (items_count >= 0) AND (redactions_count >= 0))),
    CONSTRAINT valid_task_type CHECK (((task_type)::text = ANY ((ARRAY['docstring.fix'::character varying, 'header.fix'::character varying, 'test.generate'::character varying, 'code.generate'::character varying, 'refactor'::character varying])::text[])))
);


--
-- Name: TABLE context_packets; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.context_packets IS 'Metadata for ContextPackage artifacts created by ContextService';


--
-- Name: COLUMN context_packets.packet_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.packet_id IS 'Unique identifier for this packet';


--
-- Name: COLUMN context_packets.task_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.task_id IS 'Associated task identifier';


--
-- Name: COLUMN context_packets.task_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.task_type IS 'Type of task (docstring.fix, test.generate, etc.)';


--
-- Name: COLUMN context_packets.privacy; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.privacy IS 'Privacy level: local_only or remote_allowed';


--
-- Name: COLUMN context_packets.remote_allowed; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.remote_allowed IS 'Whether packet can be sent to remote LLMs';


--
-- Name: COLUMN context_packets.packet_hash; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.packet_hash IS 'SHA256 hash of packet content for validation';


--
-- Name: COLUMN context_packets.cache_key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.cache_key IS 'Hash of task spec for cache lookup';


--
-- Name: COLUMN context_packets.tokens_est; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.tokens_est IS 'Estimated token count for packet';


--
-- Name: COLUMN context_packets.size_bytes; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.size_bytes IS 'Size of serialized packet in bytes';


--
-- Name: COLUMN context_packets.build_ms; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.build_ms IS 'Time taken to build packet in milliseconds';


--
-- Name: COLUMN context_packets.items_count; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.items_count IS 'Number of items in context array';


--
-- Name: COLUMN context_packets.redactions_count; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.redactions_count IS 'Number of redactions applied';


--
-- Name: COLUMN context_packets.path; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.path IS 'File path to serialized packet YAML';


--
-- Name: COLUMN context_packets.metadata; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.metadata IS 'Extensible metadata (provenance, stats, etc.)';


--
-- Name: COLUMN context_packets.builder_version; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.context_packets.builder_version IS 'Version of ContextBuilder that created packet';


--
-- Name: decorator_inference_rules; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.decorator_inference_rules (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    rule_name text NOT NULL,
    priority integer DEFAULT 100 NOT NULL,
    conditions jsonb NOT NULL,
    decorator_id uuid NOT NULL,
    default_parameters jsonb DEFAULT '{}'::jsonb,
    parameter_inference jsonb,
    reasoning text NOT NULL,
    policy_reference text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_conditions_is_object CHECK ((jsonb_typeof(conditions) = 'object'::text))
);


--
-- Name: TABLE decorator_inference_rules; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.decorator_inference_rules IS 'Rules for automatically inferring which decorators a symbol needs';


--
-- Name: COLUMN decorator_inference_rules.conditions; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.decorator_inference_rules.conditions IS 'JSON structure for matching symbols:
 {
   "module_contains": "pattern",
   "name_pattern": "regex",
   "has_decorator": "decorator_name",
   "ast_features": ["async", "class_method"],
   "symbol_kind": ["function", "class"]
 }';


--
-- Name: COLUMN decorator_inference_rules.parameter_inference; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.decorator_inference_rules.parameter_inference IS 'JSON rules for computing parameter values from symbol analysis';


--
-- Name: decorator_registry; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.decorator_registry (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    decorator_name text NOT NULL,
    full_syntax text NOT NULL,
    category text NOT NULL,
    framework text,
    purpose text NOT NULL,
    required_for text[],
    parameters jsonb DEFAULT '[]'::jsonb,
    policy_reference text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT decorator_registry_category_check CHECK ((category = ANY (ARRAY['governance_contract'::text, 'framework_binding'::text, 'type_hint'::text])))
);


--
-- Name: TABLE decorator_registry; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.decorator_registry IS 'Registry of all constitutionally-approved decorators and their metadata';


--
-- Name: domains; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.domains (
    key text NOT NULL,
    title text NOT NULL,
    description text,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: export_digests; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.export_digests (
    path text NOT NULL,
    sha256 text NOT NULL,
    manifest_id uuid NOT NULL,
    exported_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: export_manifests; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.export_manifests (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    exported_at timestamp with time zone DEFAULT now() NOT NULL,
    who text,
    environment text,
    notes text
);


--
-- Name: feedback; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.feedback (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_id uuid,
    action_id uuid,
    feedback_type text NOT NULL,
    message text NOT NULL,
    corrective_action text,
    applied boolean DEFAULT false,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT feedback_feedback_type_check CHECK ((feedback_type = ANY (ARRAY['success'::text, 'failure'::text, 'improvement'::text, 'validation_error'::text, 'user_correction'::text])))
);


--
-- Name: symbol_capability_links; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.symbol_capability_links (
    symbol_id uuid NOT NULL,
    capability_id uuid NOT NULL,
    confidence core.probability NOT NULL,
    source text NOT NULL,
    verified boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT symbol_capability_links_confidence_check CHECK ((((confidence)::numeric >= (0)::numeric) AND ((confidence)::numeric <= (1)::numeric))),
    CONSTRAINT symbol_capability_links_source_check CHECK ((source = ANY (ARRAY['auditor-infer'::text, 'manual'::text, 'rule'::text, 'llm-classified'::text])))
);


--
-- Name: symbol_vector_links; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.symbol_vector_links (
    symbol_id uuid NOT NULL,
    vector_id uuid NOT NULL,
    embedding_model text NOT NULL,
    embedding_version integer NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: symbols; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.symbols (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    symbol_path text NOT NULL,
    module text NOT NULL,
    qualname text NOT NULL,
    kind text NOT NULL,
    ast_signature text NOT NULL,
    fingerprint text NOT NULL,
    state text DEFAULT 'discovered'::text NOT NULL,
    health_status text DEFAULT 'unknown'::text,
    is_public boolean DEFAULT true NOT NULL,
    previous_paths text[],
    key text,
    intent text,
    embedding_model text DEFAULT 'text-embedding-3-small'::text,
    last_embedded timestamp with time zone,
    calls jsonb DEFAULT '[]'::jsonb,
    first_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_seen timestamp with time zone DEFAULT now() NOT NULL,
    last_modified timestamp with time zone DEFAULT now() NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    symbol_tier character varying(20),
    last_attempt_at timestamp with time zone,
    file_path text,
    module_path text,
    definition_status text DEFAULT 'pending'::text NOT NULL,
    definition_error text,
    definition_source text,
    defined_at timestamp with time zone,
    attempt_count integer DEFAULT 0 NOT NULL,
    domain text DEFAULT 'unknown'::text,
    CONSTRAINT ck_symbols_file_path CHECK (((file_path IS NULL) OR (file_path ~~ 'src/%.py'::text))),
    CONSTRAINT ck_symbols_key_requires_defined CHECK ((((key IS NULL) AND (definition_status <> 'defined'::text)) OR ((key IS NOT NULL) AND (definition_status = 'defined'::text)))),
    CONSTRAINT symbols_health_status_check CHECK ((health_status = ANY (ARRAY['healthy'::text, 'needs_review'::text, 'deprecated'::text, 'broken'::text, 'unknown'::text]))),
    CONSTRAINT symbols_kind_check CHECK ((kind = ANY (ARRAY['function'::text, 'class'::text, 'method'::text, 'module'::text]))),
    CONSTRAINT symbols_state_check CHECK ((state = ANY (ARRAY['discovered'::text, 'classified'::text, 'bound'::text, 'verified'::text, 'deprecated'::text])))
);


--
-- Name: COLUMN symbols.key; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.symbols.key IS 'Capability label (non-unique). Many symbols may share the same key. This is a transitional convenience field; the SSOT is core.capabilities + core.symbol_capability_links.';


--
-- Name: COLUMN symbols.definition_status; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.symbols.definition_status IS 'pending: symbol discovered but not yet analyzed;
 defined: successfully analyzed with AST parsing;
 error: analysis failed - see definition_error for details';


--
-- Name: knowledge_graph; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.knowledge_graph AS
 SELECT s.id AS uuid,
    s.symbol_path,
    s.module,
    s.qualname AS name,
    s.kind,
    s.domain,
    s.fingerprint,
    s.state,
    s.health_status,
    s.is_public,
    s.key AS capability,
    s.intent,
    COALESCE(( SELECT jsonb_agg(c.name ORDER BY c.name) AS jsonb_agg
           FROM (core.symbol_capability_links scl
             JOIN core.capabilities c ON ((c.id = scl.capability_id)))
          WHERE (scl.symbol_id = s.id)), '[]'::jsonb) AS capabilities_array,
    svl.vector_id
   FROM (core.symbols s
     LEFT JOIN core.symbol_vector_links svl ON ((svl.symbol_id = s.id)));


--
-- Name: llm_resources; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.llm_resources (
    name text NOT NULL,
    env_prefix text NOT NULL,
    provided_capabilities jsonb DEFAULT '[]'::jsonb,
    performance_metadata jsonb,
    is_available boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT llm_resources_provided_capabilities_check CHECK ((jsonb_typeof(provided_capabilities) = 'array'::text))
);


--
-- Name: mv_refresh_log; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.mv_refresh_log (
    view_name text NOT NULL,
    last_refresh_started timestamp with time zone,
    last_refresh_completed timestamp with time zone,
    last_refresh_duration_ms integer,
    rows_affected integer,
    triggered_by text
);


--
-- Name: northstar; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.northstar (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    mission text NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: observability_decisions; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.observability_decisions (
    id bigint NOT NULL,
    decision_id uuid DEFAULT gen_random_uuid() NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    decision_type character varying(100) NOT NULL,
    governing_policies text[] NOT NULL,
    context_used jsonb NOT NULL,
    reasoning_trace text NOT NULL,
    outcome jsonb NOT NULL,
    correlation_id uuid,
    CONSTRAINT decisions_has_policies CHECK ((array_length(governing_policies, 1) > 0)),
    CONSTRAINT decisions_has_reasoning CHECK ((length(reasoning_trace) > 0)),
    CONSTRAINT observability_decisions_decision_type_check CHECK (((decision_type)::text = ANY ((ARRAY['code_generation'::character varying, 'self_healing'::character varying, 'validation'::character varying, 'planning'::character varying, 'refactoring'::character varying])::text[])))
);


--
-- Name: TABLE observability_decisions; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.observability_decisions IS 'Constitutional audit trail for autonomous AI decisions - permanent record';


--
-- Name: COLUMN observability_decisions.decision_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_decisions.decision_id IS 'Unique identifier for this decision';


--
-- Name: COLUMN observability_decisions.governing_policies; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_decisions.governing_policies IS 'Constitutional policies that constrained this decision';


--
-- Name: COLUMN observability_decisions.context_used; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_decisions.context_used IS 'Input context provided to the AI (symbols, patterns, policies)';


--
-- Name: COLUMN observability_decisions.reasoning_trace; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_decisions.reasoning_trace IS 'AI explanation of why it made this decision';


--
-- Name: COLUMN observability_decisions.outcome; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_decisions.outcome IS 'Result of executing the decision (validation_result, audit_result, integration_status)';


--
-- Name: observability_decisions_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.observability_decisions_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: observability_decisions_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.observability_decisions_id_seq OWNED BY core.observability_decisions.id;


--
-- Name: observability_logs; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.observability_logs (
    id bigint NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    action_id character varying(255) NOT NULL,
    correlation_id uuid NOT NULL,
    level character varying(20) NOT NULL,
    outcome character varying(20) NOT NULL,
    duration_ms integer NOT NULL,
    context jsonb DEFAULT '{}'::jsonb NOT NULL,
    message text,
    CONSTRAINT logs_timestamp_check CHECK (("timestamp" <= (now() + '01:00:00'::interval))),
    CONSTRAINT observability_logs_level_check CHECK (((level)::text = ANY ((ARRAY['DEBUG'::character varying, 'INFO'::character varying, 'WARNING'::character varying, 'ERROR'::character varying, 'CRITICAL'::character varying])::text[]))),
    CONSTRAINT observability_logs_outcome_check CHECK (((outcome)::text = ANY ((ARRAY['success'::character varying, 'failure'::character varying, 'partial'::character varying])::text[])))
);


--
-- Name: TABLE observability_logs; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.observability_logs IS 'Structured logs from atomic actions - enables tracing, debugging, and pattern analysis';


--
-- Name: COLUMN observability_logs.action_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_logs.action_id IS 'Atomic action identifier (e.g., fix.ids, manage.vectorize)';


--
-- Name: COLUMN observability_logs.correlation_id; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_logs.correlation_id IS 'Links related operations across the system';


--
-- Name: COLUMN observability_logs.context; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_logs.context IS 'Operation-specific details (e.g., files_modified, tests_generated)';


--
-- Name: observability_logs_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.observability_logs_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: observability_logs_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.observability_logs_id_seq OWNED BY core.observability_logs.id;


--
-- Name: observability_metrics; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.observability_metrics (
    id bigint NOT NULL,
    "timestamp" timestamp with time zone DEFAULT now() NOT NULL,
    metric_name character varying(255) NOT NULL,
    metric_value numeric NOT NULL,
    metric_type character varying(50) NOT NULL,
    tags jsonb DEFAULT '{}'::jsonb NOT NULL,
    CONSTRAINT observability_metrics_metric_type_check CHECK (((metric_type)::text = ANY ((ARRAY['counter'::character varying, 'gauge'::character varying, 'histogram'::character varying, 'percentage'::character varying])::text[])))
);


--
-- Name: TABLE observability_metrics; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.observability_metrics IS 'Time-series metrics for system health, performance, and quality tracking';


--
-- Name: COLUMN observability_metrics.metric_name; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_metrics.metric_name IS 'Metric identifier (e.g., action_success_rate, autonomous_generation_success_rate)';


--
-- Name: COLUMN observability_metrics.metric_type; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_metrics.metric_type IS 'Type of metric for correct aggregation';


--
-- Name: COLUMN observability_metrics.tags; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.observability_metrics.tags IS 'Dimensions for filtering (e.g., {action_id: "fix.ids", environment: "production"})';


--
-- Name: observability_metrics_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.observability_metrics_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: observability_metrics_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.observability_metrics_id_seq OWNED BY core.observability_metrics.id;


--
-- Name: proposal_signatures; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.proposal_signatures (
    proposal_id bigint NOT NULL,
    approver_identity text NOT NULL,
    signature_base64 text NOT NULL,
    signed_at timestamp with time zone DEFAULT now() NOT NULL,
    is_valid boolean DEFAULT true NOT NULL
);


--
-- Name: proposals; Type: TABLE; Schema: core; Owner: -
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


--
-- Name: proposals_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.proposals_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: proposals_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.proposals_id_seq OWNED BY core.proposals.id;


--
-- Name: retrieval_feedback; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.retrieval_feedback (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    task_id uuid NOT NULL,
    query text NOT NULL,
    retrieved_symbols uuid[],
    actually_used_symbols uuid[],
    retrieval_quality integer,
    notes text,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT retrieval_feedback_retrieval_quality_check CHECK (((retrieval_quality >= 1) AND (retrieval_quality <= 5)))
);


--
-- Name: runtime_services; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.runtime_services (
    name text NOT NULL,
    implementation text NOT NULL,
    is_active boolean DEFAULT true
);


--
-- Name: runtime_settings; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.runtime_settings (
    key text NOT NULL,
    value text,
    description text,
    is_secret boolean DEFAULT false NOT NULL,
    last_updated timestamp with time zone DEFAULT now() NOT NULL
);


--
-- Name: TABLE runtime_settings; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.runtime_settings IS 'Single source of truth for runtime configuration, loaded from .env and managed by `core-admin manage dotenv sync`.';


--
-- Name: COLUMN runtime_settings.is_secret; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.runtime_settings.is_secret IS 'If true, the value should be handled with care.';


--
-- Name: semantic_cache; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.semantic_cache (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    query_hash text NOT NULL,
    query_text text NOT NULL,
    vector_id text,
    response_text text NOT NULL,
    cognitive_role text,
    llm_model text NOT NULL,
    tokens_used integer,
    confidence core.probability,
    hit_count integer DEFAULT 0,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT semantic_cache_confidence_check CHECK ((((confidence)::numeric >= (0)::numeric) AND ((confidence)::numeric <= (1)::numeric)))
);


--
-- Name: symbol_decorators; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.symbol_decorators (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    symbol_id uuid NOT NULL,
    decorator_id uuid NOT NULL,
    order_index integer NOT NULL,
    parameters jsonb DEFAULT '{}'::jsonb,
    source text DEFAULT 'inferred'::text,
    reasoning text,
    is_active boolean DEFAULT true,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    updated_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT chk_order_index_positive CHECK ((order_index > 0)),
    CONSTRAINT symbol_decorators_source_check CHECK ((source = ANY (ARRAY['inferred'::text, 'manual'::text, 'constitutional'::text, 'generated'::text])))
);


--
-- Name: TABLE symbol_decorators; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON TABLE core.symbol_decorators IS 'Links symbols to their required decorators with parameters and ordering';


--
-- Name: COLUMN symbol_decorators.order_index; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.symbol_decorators.order_index IS 'Decorator application order: 1 = outermost (applied first), higher = inner';


--
-- Name: symbols_audit; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.symbols_audit (
    audit_id bigint NOT NULL,
    operation character(1) NOT NULL,
    changed_at timestamp with time zone DEFAULT now(),
    changed_by text DEFAULT CURRENT_USER,
    symbol_id uuid NOT NULL,
    old_data jsonb,
    new_data jsonb
);


--
-- Name: symbols_audit_audit_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.symbols_audit_audit_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: symbols_audit_audit_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.symbols_audit_audit_id_seq OWNED BY core.symbols_audit.audit_id;


--
-- Name: tasks; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.tasks (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    intent text NOT NULL,
    assigned_role text,
    parent_task_id uuid,
    status text DEFAULT 'pending'::text NOT NULL,
    plan jsonb,
    context jsonb DEFAULT '{}'::jsonb,
    error_message text,
    failure_reason text,
    relevant_symbols uuid[],
    context_retrieval_query text,
    context_retrieved_at timestamp with time zone,
    context_tokens_used integer,
    requires_approval boolean DEFAULT false,
    proposal_id bigint,
    estimated_complexity integer,
    actual_duration_seconds integer,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    started_at timestamp with time zone,
    completed_at timestamp with time zone,
    CONSTRAINT chk_intent_not_empty CHECK ((TRIM(BOTH FROM intent) <> ''::text)),
    CONSTRAINT tasks_estimated_complexity_check CHECK (((estimated_complexity >= 1) AND (estimated_complexity <= 10))),
    CONSTRAINT tasks_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'planning'::text, 'executing'::text, 'validating'::text, 'completed'::text, 'failed'::text, 'blocked'::text])))
);


--
-- Name: COLUMN tasks.relevant_symbols; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tasks.relevant_symbols IS 'Array of symbol UUIDs retrieved from vector search.
 Validated via trigger to ensure all UUIDs exist in symbols table.';


--
-- Name: v_agent_context; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_agent_context AS
 SELECT id AS task_id,
    intent,
    assigned_role,
    status,
    relevant_symbols,
    array_length(relevant_symbols, 1) AS context_symbol_count,
    ( SELECT json_agg(json_build_object('action', a.action_type, 'success', a.success, 'target', a.target, 'reasoning', a.reasoning) ORDER BY a.created_at DESC) AS json_agg
           FROM core.actions a
          WHERE (a.task_id = t.id)
         LIMIT 10) AS recent_actions,
    ( SELECT json_agg(json_build_object('type', am.memory_type, 'content', am.content, 'score', am.relevance_score) ORDER BY am.relevance_score DESC) AS json_agg
           FROM core.agent_memory am
          WHERE ((am.cognitive_role = t.assigned_role) AND ((am.expires_at IS NULL) OR (am.expires_at > now())))
         LIMIT 5) AS active_memories,
    ( SELECT json_agg(json_build_object('point', ad.decision_point, 'chosen', ad.chosen_option, 'reasoning', ad.reasoning, 'confidence', ad.confidence) ORDER BY ad.decided_at DESC) AS json_agg
           FROM core.agent_decisions ad
          WHERE (ad.task_id = t.id)
         LIMIT 5) AS recent_decisions
   FROM core.tasks t
  WHERE (status = ANY (ARRAY['pending'::text, 'executing'::text, 'planning'::text]))
  ORDER BY created_at;


--
-- Name: v_agent_workload; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_agent_workload AS
 SELECT cr.role,
    cr.is_active,
    count(t.id) FILTER (WHERE (t.status = 'executing'::text)) AS active_tasks,
    count(t.id) FILTER (WHERE (t.status = 'pending'::text)) AS queued_tasks,
    count(t.id) FILTER (WHERE (t.status = 'blocked'::text)) AS blocked_tasks,
    cr.max_concurrent_tasks,
    (cr.max_concurrent_tasks - count(t.id) FILTER (WHERE (t.status = 'executing'::text))) AS available_slots,
    cr.assigned_resource
   FROM (core.cognitive_roles cr
     LEFT JOIN core.tasks t ON (((t.assigned_role = cr.role) AND (t.status = ANY (ARRAY['pending'::text, 'executing'::text, 'blocked'::text])))))
  GROUP BY cr.role, cr.is_active, cr.max_concurrent_tasks, cr.assigned_resource
  ORDER BY cr.role;


--
-- Name: v_observability_action_health; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_observability_action_health AS
 SELECT action_id,
    count(*) AS total_executions,
    count(*) FILTER (WHERE ((outcome)::text = 'success'::text)) AS successful,
    count(*) FILTER (WHERE ((outcome)::text = 'failure'::text)) AS failed,
    round(((100.0 * (count(*) FILTER (WHERE ((outcome)::text = 'success'::text)))::numeric) / (count(*))::numeric), 2) AS success_rate,
    round(avg(duration_ms), 0) AS avg_duration_ms,
    percentile_cont((0.5)::double precision) WITHIN GROUP (ORDER BY ((duration_ms)::double precision)) AS p50_duration_ms,
    percentile_cont((0.95)::double precision) WITHIN GROUP (ORDER BY ((duration_ms)::double precision)) AS p95_duration_ms,
    max("timestamp") AS last_execution
   FROM core.observability_logs
  WHERE ("timestamp" > (now() - '24:00:00'::interval))
  GROUP BY action_id
  ORDER BY (count(*)) DESC;


--
-- Name: VIEW v_observability_action_health; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON VIEW core.v_observability_action_health IS 'Health metrics for each atomic action (last 24 hours)';


--
-- Name: v_observability_recent_failures; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_observability_recent_failures AS
 SELECT "timestamp",
    action_id,
    correlation_id,
    level,
    message,
    context
   FROM core.observability_logs
  WHERE (((outcome)::text = 'failure'::text) AND ("timestamp" > (now() - '24:00:00'::interval)))
  ORDER BY "timestamp" DESC;


--
-- Name: VIEW v_observability_recent_failures; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON VIEW core.v_observability_recent_failures IS 'Last 24 hours of failures for quick debugging';


--
-- Name: v_orphan_symbols; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_orphan_symbols AS
 SELECT s.id,
    s.symbol_path,
    s.module,
    s.qualname,
    s.kind,
    s.state,
    s.health_status
   FROM (core.symbols s
     LEFT JOIN core.symbol_capability_links l ON ((l.symbol_id = s.id)))
  WHERE ((l.symbol_id IS NULL) AND (s.state <> 'deprecated'::text) AND (s.health_status <> 'deprecated'::text))
  ORDER BY s.last_modified DESC;


--
-- Name: v_schema_health; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_schema_health AS
 SELECT 'Missing FK'::text AS issue_type,
    'core.symbols.domain'::text AS object_name,
    count(*) AS issue_count
   FROM (core.symbols s
     LEFT JOIN core.domains d ON ((s.domain = d.key)))
  WHERE ((d.key IS NULL) AND (s.domain <> 'unknown'::text))
UNION ALL
 SELECT 'Invalid UUID in array'::text AS issue_type,
    'core.tasks.relevant_symbols'::text AS object_name,
    count(*) AS issue_count
   FROM ((core.tasks t
     CROSS JOIN LATERAL unnest(t.relevant_symbols) sym_id(sym_id))
     LEFT JOIN core.symbols s ON ((s.id = sym_id.sym_id)))
  WHERE (s.id IS NULL)
UNION ALL
 SELECT 'Orphaned capability links'::text AS issue_type,
    'core.symbol_capability_links'::text AS object_name,
    count(*) AS issue_count
   FROM (core.symbol_capability_links scl
     LEFT JOIN core.symbols s ON ((s.id = scl.symbol_id)))
  WHERE (s.id IS NULL);


--
-- Name: v_stale_materialized_views; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_stale_materialized_views AS
 SELECT view_name,
    last_refresh_completed,
    (now() - last_refresh_completed) AS age,
    last_refresh_duration_ms,
    rows_affected,
    ((last_refresh_completed IS NULL) OR (last_refresh_completed < (now() - '00:10:00'::interval))) AS is_stale
   FROM core.mv_refresh_log
  WHERE ((last_refresh_completed IS NULL) OR (last_refresh_completed < (now() - '00:10:00'::interval)))
  ORDER BY last_refresh_completed NULLS FIRST;


--
-- Name: v_symbol_decorator_stack; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_symbol_decorator_stack AS
 SELECT s.id AS symbol_id,
    s.symbol_path,
    s.module,
    s.qualname,
    json_agg(json_build_object('decorator', dr.decorator_name, 'syntax', dr.full_syntax, 'parameters', sd.parameters, 'order', sd.order_index, 'category', dr.category, 'reasoning', sd.reasoning) ORDER BY sd.order_index) AS decorator_stack
   FROM ((core.symbols s
     LEFT JOIN core.symbol_decorators sd ON (((sd.symbol_id = s.id) AND (sd.is_active = true))))
     LEFT JOIN core.decorator_registry dr ON (((dr.id = sd.decorator_id) AND (dr.is_active = true))))
  GROUP BY s.id, s.symbol_path, s.module, s.qualname;


--
-- Name: VIEW v_symbol_decorator_stack; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON VIEW core.v_symbol_decorator_stack IS 'Complete decorator stack for each symbol in application order';


--
-- Name: v_symbols_missing_decorators; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_symbols_missing_decorators AS
 SELECT s.id AS symbol_id,
    s.symbol_path,
    s.module,
    s.kind,
    dir.rule_name,
    dr.decorator_name AS missing_decorator,
    dir.reasoning
   FROM ((core.symbols s
     CROSS JOIN core.decorator_inference_rules dir)
     JOIN core.decorator_registry dr ON ((dr.id = dir.decorator_id)))
  WHERE ((dir.is_active = true) AND (dr.is_active = true) AND (s.state <> 'deprecated'::text) AND (((dir.conditions ->> 'module_contains'::text) IS NULL) OR (s.module ~~ (('%'::text || (dir.conditions ->> 'module_contains'::text)) || '%'::text))) AND (NOT (EXISTS ( SELECT 1
           FROM core.symbol_decorators sd
          WHERE ((sd.symbol_id = s.id) AND (sd.decorator_id = dir.decorator_id) AND (sd.is_active = true))))))
  ORDER BY s.module, s.symbol_path;


--
-- Name: VIEW v_symbols_missing_decorators; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON VIEW core.v_symbols_missing_decorators IS 'Symbols that should have decorators based on inference rules but do not';


--
-- Name: v_symbols_needing_embedding; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_symbols_needing_embedding AS
 SELECT id,
    module,
    qualname,
    symbol_path,
    ast_signature,
    fingerprint
   FROM core.symbols s
  WHERE ((last_embedded IS NULL) OR (last_modified > last_embedded))
  ORDER BY last_modified DESC;


--
-- Name: v_verified_coverage; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.v_verified_coverage AS
 SELECT c.id AS capability_id,
    c.name,
    c.domain,
    count(l.symbol_id) AS verified_symbols,
    c.test_coverage,
    c.status
   FROM (core.capabilities c
     LEFT JOIN core.symbol_capability_links l ON (((l.capability_id = c.id) AND (l.verified = true))))
  GROUP BY c.id, c.name, c.domain, c.test_coverage, c.status
  ORDER BY c.domain, c.name;


--
-- Name: vector_sync_log; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.vector_sync_log (
    id bigint NOT NULL,
    operation text NOT NULL,
    symbol_ids uuid[],
    qdrant_collection text NOT NULL,
    success boolean NOT NULL,
    error_message text,
    batch_size integer,
    duration_ms integer,
    synced_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT vector_sync_log_operation_check CHECK ((operation = ANY (ARRAY['upsert'::text, 'delete'::text, 'bulk_update'::text, 'reindex'::text])))
);


--
-- Name: vector_sync_log_id_seq; Type: SEQUENCE; Schema: core; Owner: -
--

CREATE SEQUENCE core.vector_sync_log_id_seq
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vector_sync_log_id_seq; Type: SEQUENCE OWNED BY; Schema: core; Owner: -
--

ALTER SEQUENCE core.vector_sync_log_id_seq OWNED BY core.vector_sync_log.id;


--
-- Name: core_symbols_staging; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.core_symbols_staging (
    uuid text,
    symbol_path text,
    file_path text,
    structural_hash text,
    is_public boolean DEFAULT true
);


--
-- Name: symbols_backup; Type: TABLE; Schema: core; Owner: -
--

CREATE TABLE core.symbols_backup (
    id uuid,
    symbol_path text,
    module text,
    qualname text,
    kind text,
    ast_signature text,
    fingerprint text,
    state text,
    health_status text,
    is_public boolean,
    previous_paths text[],
    key text,
    intent text,
    embedding_model text,
    last_embedded timestamp with time zone,
    first_seen timestamp with time zone,
    last_seen timestamp with time zone,
    last_modified timestamp with time zone,
    created_at timestamp with time zone,
    updated_at timestamp with time zone
);


--
-- Name: vector_links_backup; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE core.vector_links_backup (
    symbol_id uuid,
    vector_id uuid,
    embedding_model text,
    embedding_version integer,
    created_at timestamp with time zone
);


--
-- Name: audit_runs id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.audit_runs ALTER COLUMN id SET DEFAULT nextval('core.audit_runs_id_seq'::regclass);


--
-- Name: observability_decisions id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.observability_decisions ALTER COLUMN id SET DEFAULT nextval('core.observability_decisions_id_seq'::regclass);


--
-- Name: observability_logs id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.observability_logs ALTER COLUMN id SET DEFAULT nextval('core.observability_logs_id_seq'::regclass);


--
-- Name: observability_metrics id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.observability_metrics ALTER COLUMN id SET DEFAULT nextval('core.observability_metrics_id_seq'::regclass);


--
-- Name: proposals id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.proposals ALTER COLUMN id SET DEFAULT nextval('core.proposals_id_seq'::regclass);


--
-- Name: symbols_audit audit_id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbols_audit ALTER COLUMN audit_id SET DEFAULT nextval('core.symbols_audit_audit_id_seq'::regclass);


--
-- Name: vector_sync_log id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.vector_sync_log ALTER COLUMN id SET DEFAULT nextval('core.vector_sync_log_id_seq'::regclass);


--
-- Name: _migrations _migrations_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core._migrations
    ADD CONSTRAINT _migrations_pkey PRIMARY KEY (id);


--
-- Name: action_results action_results_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.action_results
    ADD CONSTRAINT action_results_pkey PRIMARY KEY (id);


--
-- Name: actions actions_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.actions
    ADD CONSTRAINT actions_pkey PRIMARY KEY (id);


--
-- Name: agent_decisions agent_decisions_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.agent_decisions
    ADD CONSTRAINT agent_decisions_pkey PRIMARY KEY (id);


--
-- Name: agent_memory agent_memory_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.agent_memory
    ADD CONSTRAINT agent_memory_pkey PRIMARY KEY (id);


--
-- Name: audit_runs audit_runs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.audit_runs
    ADD CONSTRAINT audit_runs_pkey PRIMARY KEY (id);


--
-- Name: capabilities capabilities_domain_name_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.capabilities
    ADD CONSTRAINT capabilities_domain_name_key UNIQUE (domain, name);


--
-- Name: capabilities capabilities_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.capabilities
    ADD CONSTRAINT capabilities_pkey PRIMARY KEY (id);


--
-- Name: capability_cli_links capability_cli_links_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.capability_cli_links
    ADD CONSTRAINT capability_cli_links_pkey PRIMARY KEY (capability_id, cli_command_name);


--
-- Name: cli_commands cli_commands_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cli_commands
    ADD CONSTRAINT cli_commands_pkey PRIMARY KEY (name);


--
-- Name: cognitive_roles cognitive_roles_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cognitive_roles
    ADD CONSTRAINT cognitive_roles_pkey PRIMARY KEY (role);


--
-- Name: constitutional_violations constitutional_violations_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.constitutional_violations
    ADD CONSTRAINT constitutional_violations_pkey PRIMARY KEY (id);


--
-- Name: context_packets context_packets_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.context_packets
    ADD CONSTRAINT context_packets_pkey PRIMARY KEY (packet_id);


--
-- Name: decorator_inference_rules decorator_inference_rules_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.decorator_inference_rules
    ADD CONSTRAINT decorator_inference_rules_pkey PRIMARY KEY (id);


--
-- Name: decorator_inference_rules decorator_inference_rules_rule_name_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.decorator_inference_rules
    ADD CONSTRAINT decorator_inference_rules_rule_name_key UNIQUE (rule_name);


--
-- Name: decorator_registry decorator_registry_decorator_name_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.decorator_registry
    ADD CONSTRAINT decorator_registry_decorator_name_key UNIQUE (decorator_name);


--
-- Name: decorator_registry decorator_registry_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.decorator_registry
    ADD CONSTRAINT decorator_registry_pkey PRIMARY KEY (id);


--
-- Name: domains domains_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.domains
    ADD CONSTRAINT domains_pkey PRIMARY KEY (key);


--
-- Name: tasks exclude_overlapping_tasks; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tasks
    ADD CONSTRAINT exclude_overlapping_tasks EXCLUDE USING gist (assigned_role WITH =, tstzrange(started_at, completed_at) WITH &&) WHERE ((status = 'executing'::text));


--
-- Name: export_digests export_digests_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.export_digests
    ADD CONSTRAINT export_digests_pkey PRIMARY KEY (path);


--
-- Name: export_manifests export_manifests_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.export_manifests
    ADD CONSTRAINT export_manifests_pkey PRIMARY KEY (id);


--
-- Name: feedback feedback_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.feedback
    ADD CONSTRAINT feedback_pkey PRIMARY KEY (id);


--
-- Name: llm_resources llm_resources_env_prefix_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.llm_resources
    ADD CONSTRAINT llm_resources_env_prefix_key UNIQUE (env_prefix);


--
-- Name: llm_resources llm_resources_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.llm_resources
    ADD CONSTRAINT llm_resources_pkey PRIMARY KEY (name);


--
-- Name: observability_metrics metrics_unique_point; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.observability_metrics
    ADD CONSTRAINT metrics_unique_point UNIQUE ("timestamp", metric_name, tags);


--
-- Name: mv_refresh_log mv_refresh_log_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.mv_refresh_log
    ADD CONSTRAINT mv_refresh_log_pkey PRIMARY KEY (view_name);


--
-- Name: northstar northstar_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.northstar
    ADD CONSTRAINT northstar_pkey PRIMARY KEY (id);


--
-- Name: observability_decisions observability_decisions_decision_id_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.observability_decisions
    ADD CONSTRAINT observability_decisions_decision_id_key UNIQUE (decision_id);


--
-- Name: observability_decisions observability_decisions_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.observability_decisions
    ADD CONSTRAINT observability_decisions_pkey PRIMARY KEY (id);


--
-- Name: observability_logs observability_logs_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.observability_logs
    ADD CONSTRAINT observability_logs_pkey PRIMARY KEY (id);


--
-- Name: observability_metrics observability_metrics_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.observability_metrics
    ADD CONSTRAINT observability_metrics_pkey PRIMARY KEY (id);


--
-- Name: proposal_signatures proposal_signatures_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.proposal_signatures
    ADD CONSTRAINT proposal_signatures_pkey PRIMARY KEY (proposal_id, approver_identity);


--
-- Name: proposals proposals_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.proposals
    ADD CONSTRAINT proposals_pkey PRIMARY KEY (id);


--
-- Name: retrieval_feedback retrieval_feedback_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.retrieval_feedback
    ADD CONSTRAINT retrieval_feedback_pkey PRIMARY KEY (id);


--
-- Name: runtime_services runtime_services_implementation_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.runtime_services
    ADD CONSTRAINT runtime_services_implementation_key UNIQUE (implementation);


--
-- Name: runtime_services runtime_services_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.runtime_services
    ADD CONSTRAINT runtime_services_pkey PRIMARY KEY (name);


--
-- Name: runtime_settings runtime_settings_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.runtime_settings
    ADD CONSTRAINT runtime_settings_pkey PRIMARY KEY (key);


--
-- Name: semantic_cache semantic_cache_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.semantic_cache
    ADD CONSTRAINT semantic_cache_pkey PRIMARY KEY (id);


--
-- Name: semantic_cache semantic_cache_query_hash_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.semantic_cache
    ADD CONSTRAINT semantic_cache_query_hash_key UNIQUE (query_hash);


--
-- Name: symbol_capability_links symbol_capability_links_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_capability_links
    ADD CONSTRAINT symbol_capability_links_pkey PRIMARY KEY (symbol_id, capability_id, source);


--
-- Name: symbol_decorators symbol_decorators_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_decorators
    ADD CONSTRAINT symbol_decorators_pkey PRIMARY KEY (id);


--
-- Name: symbol_decorators symbol_decorators_symbol_id_decorator_id_order_index_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_decorators
    ADD CONSTRAINT symbol_decorators_symbol_id_decorator_id_order_index_key UNIQUE (symbol_id, decorator_id, order_index);


--
-- Name: symbol_vector_links symbol_vector_links_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_vector_links
    ADD CONSTRAINT symbol_vector_links_pkey PRIMARY KEY (symbol_id);


--
-- Name: symbols_audit symbols_audit_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbols_audit
    ADD CONSTRAINT symbols_audit_pkey PRIMARY KEY (audit_id);


--
-- Name: symbols symbols_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbols
    ADD CONSTRAINT symbols_pkey PRIMARY KEY (id);


--
-- Name: symbols symbols_symbol_path_key; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbols
    ADD CONSTRAINT symbols_symbol_path_key UNIQUE (symbol_path);


--
-- Name: tasks tasks_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tasks
    ADD CONSTRAINT tasks_pkey PRIMARY KEY (id);


--
-- Name: vector_sync_log vector_sync_log_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.vector_sync_log
    ADD CONSTRAINT vector_sync_log_pkey PRIMARY KEY (id);


--
-- Name: idx_action_results_created; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_action_results_created ON core.action_results USING btree (created_at);


--
-- Name: idx_action_results_file; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_action_results_file ON core.action_results USING btree (file_path);


--
-- Name: idx_action_results_ok; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_action_results_ok ON core.action_results USING btree (ok);


--
-- Name: idx_action_results_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_action_results_type ON core.action_results USING btree (action_type);


--
-- Name: idx_actions_cognitive_role; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_cognitive_role ON core.actions USING btree (cognitive_role);


--
-- Name: idx_actions_created; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_created ON core.actions USING btree (created_at DESC);


--
-- Name: idx_actions_payload_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_payload_gin ON core.actions USING gin (payload);


--
-- Name: idx_actions_success; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_success ON core.actions USING btree (success) WHERE (success = false);


--
-- Name: idx_actions_task; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_task ON core.actions USING btree (task_id);


--
-- Name: idx_actions_task_success_created; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_task_success_created ON core.actions USING btree (task_id, success, created_at DESC);


--
-- Name: idx_actions_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_type ON core.actions USING btree (action_type);


--
-- Name: idx_active_tasks; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_active_tasks ON core.tasks USING btree (id) WHERE (status = ANY (ARRAY['pending'::text, 'executing'::text, 'planning'::text]));


--
-- Name: idx_agent_memory_related_task_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_agent_memory_related_task_id ON core.agent_memory USING btree (related_task_id);


--
-- Name: idx_audit_runs_passed; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_audit_runs_passed ON core.audit_runs USING btree (passed, started_at DESC);


--
-- Name: idx_cache_expires; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_cache_expires ON core.semantic_cache USING btree (expires_at) WHERE (expires_at IS NOT NULL);


--
-- Name: idx_cache_hash; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_cache_hash ON core.semantic_cache USING btree (query_hash);


--
-- Name: idx_cache_hits; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_cache_hits ON core.semantic_cache USING btree (hit_count DESC);


--
-- Name: idx_capabilities_dependencies_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_capabilities_dependencies_gin ON core.capabilities USING gin (dependencies);


--
-- Name: idx_capabilities_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_capabilities_domain ON core.capabilities USING btree (domain);


--
-- Name: idx_capabilities_status; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_capabilities_status ON core.capabilities USING btree (status);


--
-- Name: idx_capabilities_tags_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_capabilities_tags_gin ON core.capabilities USING gin (tags);


--
-- Name: idx_capability_cli_links_capability_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_capability_cli_links_capability_id ON core.capability_cli_links USING btree (capability_id);


--
-- Name: idx_capability_cli_links_cli_command_name; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_capability_cli_links_cli_command_name ON core.capability_cli_links USING btree (cli_command_name);


--
-- Name: idx_cognitive_roles_assigned_resource; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_cognitive_roles_assigned_resource ON core.cognitive_roles USING btree (assigned_resource);


--
-- Name: idx_cognitive_roles_specialization_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_cognitive_roles_specialization_gin ON core.cognitive_roles USING gin (specialization);


--
-- Name: idx_context_packets_cache_key; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_context_packets_cache_key ON core.context_packets USING btree (cache_key) WHERE (cache_key IS NOT NULL);


--
-- Name: idx_context_packets_created_at; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_context_packets_created_at ON core.context_packets USING btree (created_at DESC);


--
-- Name: idx_context_packets_metadata; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_context_packets_metadata ON core.context_packets USING gin (metadata);


--
-- Name: idx_context_packets_packet_hash; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_context_packets_packet_hash ON core.context_packets USING btree (packet_hash);


--
-- Name: idx_context_packets_task_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_context_packets_task_id ON core.context_packets USING btree (task_id);


--
-- Name: idx_context_packets_task_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_context_packets_task_type ON core.context_packets USING btree (task_type);


--
-- Name: idx_core_capabilities_domain_key_suffix; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_core_capabilities_domain_key_suffix ON core.capabilities USING btree (domain, key_suffix);


--
-- Name: idx_decisions_confidence; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_decisions_confidence ON core.agent_decisions USING btree (confidence);


--
-- Name: idx_decisions_task; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_decisions_task ON core.agent_decisions USING btree (task_id);


--
-- Name: idx_decorator_inference_rules_conditions_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_decorator_inference_rules_conditions_gin ON core.decorator_inference_rules USING gin (conditions);


--
-- Name: idx_decorator_inference_rules_parameter_inference_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_decorator_inference_rules_parameter_inference_gin ON core.decorator_inference_rules USING gin (parameter_inference);


--
-- Name: idx_decorator_registry_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_decorator_registry_active ON core.decorator_registry USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_decorator_registry_category; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_decorator_registry_category ON core.decorator_registry USING btree (category);


--
-- Name: idx_export_digests_manifest_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_export_digests_manifest_id ON core.export_digests USING btree (manifest_id);


--
-- Name: idx_feedback_action_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_feedback_action_id ON core.feedback USING btree (action_id);


--
-- Name: idx_feedback_applied; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_feedback_applied ON core.feedback USING btree (applied) WHERE (applied = false);


--
-- Name: idx_feedback_task; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_feedback_task ON core.feedback USING btree (task_id);


--
-- Name: idx_inference_rules_decorator; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_inference_rules_decorator ON core.decorator_inference_rules USING btree (decorator_id);


--
-- Name: idx_inference_rules_priority; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_inference_rules_priority ON core.decorator_inference_rules USING btree (priority) WHERE (is_active = true);


--
-- Name: idx_links_capability; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_links_capability ON core.symbol_capability_links USING btree (capability_id);


--
-- Name: idx_links_verified; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_links_verified ON core.symbol_capability_links USING btree (verified);


--
-- Name: idx_memory_expires; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_memory_expires ON core.agent_memory USING btree (expires_at) WHERE (expires_at IS NOT NULL);


--
-- Name: idx_memory_relevance; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_memory_relevance ON core.agent_memory USING btree (relevance_score DESC);


--
-- Name: idx_memory_role_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_memory_role_type ON core.agent_memory USING btree (cognitive_role, memory_type);


--
-- Name: idx_observability_decisions_context_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_decisions_context_gin ON core.observability_decisions USING gin (context_used);


--
-- Name: idx_observability_decisions_correlation_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_decisions_correlation_id ON core.observability_decisions USING btree (correlation_id);


--
-- Name: idx_observability_decisions_decision_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_decisions_decision_id ON core.observability_decisions USING btree (decision_id);


--
-- Name: idx_observability_decisions_outcome_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_decisions_outcome_gin ON core.observability_decisions USING gin (outcome);


--
-- Name: idx_observability_decisions_policies_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_decisions_policies_gin ON core.observability_decisions USING gin (governing_policies);


--
-- Name: idx_observability_decisions_timestamp; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_decisions_timestamp ON core.observability_decisions USING btree ("timestamp" DESC);


--
-- Name: idx_observability_decisions_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_decisions_type ON core.observability_decisions USING btree (decision_type);


--
-- Name: idx_observability_logs_action_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_logs_action_id ON core.observability_logs USING btree (action_id);


--
-- Name: idx_observability_logs_context_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_logs_context_gin ON core.observability_logs USING gin (context);


--
-- Name: idx_observability_logs_correlation_action; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_logs_correlation_action ON core.observability_logs USING btree (correlation_id, action_id, "timestamp" DESC);


--
-- Name: idx_observability_logs_correlation_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_logs_correlation_id ON core.observability_logs USING btree (correlation_id);


--
-- Name: idx_observability_logs_outcome; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_logs_outcome ON core.observability_logs USING btree (outcome) WHERE ((outcome)::text <> 'success'::text);


--
-- Name: idx_observability_logs_recent_failures; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_logs_recent_failures ON core.observability_logs USING btree ("timestamp", action_id, message) WHERE ((outcome)::text = 'failure'::text);


--
-- Name: idx_observability_logs_timestamp; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_logs_timestamp ON core.observability_logs USING btree ("timestamp" DESC);


--
-- Name: idx_observability_metrics_name; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_metrics_name ON core.observability_metrics USING btree (metric_name);


--
-- Name: idx_observability_metrics_name_timestamp; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_metrics_name_timestamp ON core.observability_metrics USING btree (metric_name, "timestamp" DESC);


--
-- Name: idx_observability_metrics_tags_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_metrics_tags_gin ON core.observability_metrics USING gin (tags);


--
-- Name: idx_observability_metrics_timestamp; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_metrics_timestamp ON core.observability_metrics USING btree ("timestamp" DESC);


--
-- Name: idx_proposal_signatures_proposal_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_proposal_signatures_proposal_id ON core.proposal_signatures USING btree (proposal_id);


--
-- Name: idx_retrieval_quality; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_retrieval_quality ON core.retrieval_feedback USING btree (retrieval_quality);


--
-- Name: idx_retrieval_symbols; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_retrieval_symbols ON core.retrieval_feedback USING gin (retrieved_symbols);


--
-- Name: idx_retrieval_task; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_retrieval_task ON core.retrieval_feedback USING btree (task_id);


--
-- Name: idx_retrieval_used; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_retrieval_used ON core.retrieval_feedback USING gin (actually_used_symbols);


--
-- Name: idx_symbol_capability_links_symbol_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbol_capability_links_symbol_id ON core.symbol_capability_links USING btree (symbol_id);


--
-- Name: idx_symbol_decorators_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbol_decorators_active ON core.symbol_decorators USING btree (is_active) WHERE (is_active = true);


--
-- Name: idx_symbol_decorators_decorator; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbol_decorators_decorator ON core.symbol_decorators USING btree (decorator_id);


--
-- Name: idx_symbol_decorators_order; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbol_decorators_order ON core.symbol_decorators USING btree (symbol_id, order_index);


--
-- Name: idx_symbol_decorators_symbol; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbol_decorators_symbol ON core.symbol_decorators USING btree (symbol_id);


--
-- Name: idx_symbol_vector_links_symbol_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbol_vector_links_symbol_id ON core.symbol_vector_links USING btree (symbol_id);


--
-- Name: idx_symbol_vector_links_vector_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbol_vector_links_vector_id ON core.symbol_vector_links USING btree (vector_id);


--
-- Name: idx_symbols_calls_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_calls_gin ON core.symbols USING gin (calls);


--
-- Name: idx_symbols_fingerprint; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_fingerprint ON core.symbols USING btree (fingerprint);


--
-- Name: idx_symbols_health; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_health ON core.symbols USING btree (health_status);


--
-- Name: idx_symbols_health_state_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_health_state_domain ON core.symbols USING btree (health_status, state, domain);


--
-- Name: idx_symbols_kind; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_kind ON core.symbols USING btree (kind);


--
-- Name: idx_symbols_module; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_module ON core.symbols USING btree (module);


--
-- Name: idx_symbols_module_kind_state; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_module_kind_state ON core.symbols USING btree (module, kind) WHERE (state <> 'deprecated'::text);


--
-- Name: idx_symbols_public_active; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_public_active ON core.symbols USING btree (id, symbol_path) WHERE ((is_public = true) AND (state <> 'deprecated'::text));


--
-- Name: idx_symbols_qualname; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_qualname ON core.symbols USING btree (qualname);


--
-- Name: idx_symbols_state; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_state ON core.symbols USING btree (state);


--
-- Name: idx_tasks_context_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_context_gin ON core.tasks USING gin (context);


--
-- Name: idx_tasks_created; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_created ON core.tasks USING btree (created_at DESC);


--
-- Name: idx_tasks_parent; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_parent ON core.tasks USING btree (parent_task_id);


--
-- Name: idx_tasks_plan_gin; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_plan_gin ON core.tasks USING gin (plan);


--
-- Name: idx_tasks_proposal_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_proposal_id ON core.tasks USING btree (proposal_id);


--
-- Name: idx_tasks_relevant_symbols; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_relevant_symbols ON core.tasks USING gin (relevant_symbols);


--
-- Name: idx_tasks_role; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_role ON core.tasks USING btree (assigned_role);


--
-- Name: idx_tasks_status; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_status ON core.tasks USING btree (status) WHERE (status = ANY (ARRAY['pending'::text, 'executing'::text, 'blocked'::text]));


--
-- Name: idx_tasks_status_created_at; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_status_created_at ON core.tasks USING btree (status, created_at DESC);


--
-- Name: idx_vector_sync_collection; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_vector_sync_collection ON core.vector_sync_log USING btree (qdrant_collection);


--
-- Name: idx_vector_sync_failed; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_vector_sync_failed ON core.vector_sync_log USING btree (success, synced_at) WHERE (success = false);


--
-- Name: idx_vector_sync_symbols; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_vector_sync_symbols ON core.vector_sync_log USING gin (symbol_ids);


--
-- Name: idx_violations_symbol; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_violations_symbol ON core.constitutional_violations USING btree (symbol_id);


--
-- Name: idx_violations_task; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_violations_task ON core.constitutional_violations USING btree (task_id);


--
-- Name: idx_violations_unresolved; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_violations_unresolved ON core.constitutional_violations USING btree (severity, detected_at) WHERE (resolved_at IS NULL);


--
-- Name: public_core_symbols_staging_symbol_path_idx; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX public_core_symbols_staging_symbol_path_idx ON core.core_symbols_staging USING btree (symbol_path);


--
-- Name: symbols trg_audit_symbols; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trg_audit_symbols AFTER INSERT OR DELETE OR UPDATE ON core.symbols FOR EACH ROW EXECUTE FUNCTION core.audit_symbols_changes();


--
-- Name: capabilities trg_capabilities_updated_at; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trg_capabilities_updated_at BEFORE UPDATE ON core.capabilities FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


--
-- Name: decorator_inference_rules trg_decorator_inference_rules_updated_at; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trg_decorator_inference_rules_updated_at BEFORE UPDATE ON core.decorator_inference_rules FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


--
-- Name: decorator_registry trg_decorator_registry_updated_at; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trg_decorator_registry_updated_at BEFORE UPDATE ON core.decorator_registry FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


--
-- Name: symbol_decorators trg_symbol_decorators_updated_at; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trg_symbol_decorators_updated_at BEFORE UPDATE ON core.symbol_decorators FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


--
-- Name: symbols trg_symbols_updated_at; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trg_symbols_updated_at BEFORE UPDATE ON core.symbols FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


--
-- Name: tasks trg_validate_tasks_symbols; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trg_validate_tasks_symbols BEFORE INSERT OR UPDATE ON core.tasks FOR EACH ROW EXECUTE FUNCTION core.validate_symbol_array();


--
-- Name: actions actions_task_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.actions
    ADD CONSTRAINT actions_task_id_fkey FOREIGN KEY (task_id) REFERENCES core.tasks(id) ON DELETE CASCADE;


--
-- Name: agent_decisions agent_decisions_task_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.agent_decisions
    ADD CONSTRAINT agent_decisions_task_id_fkey FOREIGN KEY (task_id) REFERENCES core.tasks(id);


--
-- Name: agent_memory agent_memory_related_task_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.agent_memory
    ADD CONSTRAINT agent_memory_related_task_id_fkey FOREIGN KEY (related_task_id) REFERENCES core.tasks(id);


--
-- Name: capabilities capabilities_domain_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.capabilities
    ADD CONSTRAINT capabilities_domain_fkey FOREIGN KEY (domain) REFERENCES core.domains(key) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: capability_cli_links capability_cli_links_capability_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.capability_cli_links
    ADD CONSTRAINT capability_cli_links_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES core.capabilities(id) ON DELETE CASCADE;


--
-- Name: capability_cli_links capability_cli_links_cli_command_name_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.capability_cli_links
    ADD CONSTRAINT capability_cli_links_cli_command_name_fkey FOREIGN KEY (cli_command_name) REFERENCES core.cli_commands(name) ON DELETE CASCADE;


--
-- Name: cognitive_roles cognitive_roles_assigned_resource_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.cognitive_roles
    ADD CONSTRAINT cognitive_roles_assigned_resource_fkey FOREIGN KEY (assigned_resource) REFERENCES core.llm_resources(name);


--
-- Name: constitutional_violations constitutional_violations_symbol_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.constitutional_violations
    ADD CONSTRAINT constitutional_violations_symbol_id_fkey FOREIGN KEY (symbol_id) REFERENCES core.symbols(id);


--
-- Name: constitutional_violations constitutional_violations_task_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.constitutional_violations
    ADD CONSTRAINT constitutional_violations_task_id_fkey FOREIGN KEY (task_id) REFERENCES core.tasks(id);


--
-- Name: decorator_inference_rules decorator_inference_rules_decorator_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.decorator_inference_rules
    ADD CONSTRAINT decorator_inference_rules_decorator_id_fkey FOREIGN KEY (decorator_id) REFERENCES core.decorator_registry(id);


--
-- Name: export_digests export_digests_manifest_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.export_digests
    ADD CONSTRAINT export_digests_manifest_id_fkey FOREIGN KEY (manifest_id) REFERENCES core.export_manifests(id) ON DELETE CASCADE;


--
-- Name: feedback feedback_action_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.feedback
    ADD CONSTRAINT feedback_action_id_fkey FOREIGN KEY (action_id) REFERENCES core.actions(id);


--
-- Name: feedback feedback_task_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.feedback
    ADD CONSTRAINT feedback_task_id_fkey FOREIGN KEY (task_id) REFERENCES core.tasks(id);


--
-- Name: actions fk_actions_cognitive_role; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.actions
    ADD CONSTRAINT fk_actions_cognitive_role FOREIGN KEY (cognitive_role) REFERENCES core.cognitive_roles(role) ON UPDATE CASCADE ON DELETE RESTRICT;


--
-- Name: symbols fk_symbols_domain; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbols
    ADD CONSTRAINT fk_symbols_domain FOREIGN KEY (domain) REFERENCES core.domains(key) ON UPDATE CASCADE ON DELETE SET DEFAULT;


--
-- Name: tasks fk_tasks_proposal; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tasks
    ADD CONSTRAINT fk_tasks_proposal FOREIGN KEY (proposal_id) REFERENCES core.proposals(id);


--
-- Name: proposal_signatures proposal_signatures_proposal_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.proposal_signatures
    ADD CONSTRAINT proposal_signatures_proposal_id_fkey FOREIGN KEY (proposal_id) REFERENCES core.proposals(id) ON DELETE CASCADE;


--
-- Name: retrieval_feedback retrieval_feedback_task_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.retrieval_feedback
    ADD CONSTRAINT retrieval_feedback_task_id_fkey FOREIGN KEY (task_id) REFERENCES core.tasks(id);


--
-- Name: symbol_capability_links symbol_capability_links_capability_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_capability_links
    ADD CONSTRAINT symbol_capability_links_capability_id_fkey FOREIGN KEY (capability_id) REFERENCES core.capabilities(id) ON DELETE CASCADE;


--
-- Name: symbol_capability_links symbol_capability_links_symbol_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_capability_links
    ADD CONSTRAINT symbol_capability_links_symbol_id_fkey FOREIGN KEY (symbol_id) REFERENCES core.symbols(id) ON DELETE CASCADE;


--
-- Name: symbol_decorators symbol_decorators_decorator_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_decorators
    ADD CONSTRAINT symbol_decorators_decorator_id_fkey FOREIGN KEY (decorator_id) REFERENCES core.decorator_registry(id) ON DELETE CASCADE;


--
-- Name: symbol_decorators symbol_decorators_symbol_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_decorators
    ADD CONSTRAINT symbol_decorators_symbol_id_fkey FOREIGN KEY (symbol_id) REFERENCES core.symbols(id) ON DELETE CASCADE;


--
-- Name: symbol_vector_links symbol_vector_links_symbol_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_vector_links
    ADD CONSTRAINT symbol_vector_links_symbol_id_fkey FOREIGN KEY (symbol_id) REFERENCES core.symbols(id) ON DELETE CASCADE;


--
-- Name: tasks tasks_assigned_role_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tasks
    ADD CONSTRAINT tasks_assigned_role_fkey FOREIGN KEY (assigned_role) REFERENCES core.cognitive_roles(role);


--
-- Name: tasks tasks_parent_task_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tasks
    ADD CONSTRAINT tasks_parent_task_id_fkey FOREIGN KEY (parent_task_id) REFERENCES core.tasks(id);


--
-- Name: tasks tasks_proposal_id_fkey; Type: FK CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.tasks
    ADD CONSTRAINT tasks_proposal_id_fkey FOREIGN KEY (proposal_id) REFERENCES core.proposals(id);


--
-- Name: runtime_settings; Type: ROW SECURITY; Schema: core; Owner: -
--

ALTER TABLE core.runtime_settings ENABLE ROW LEVEL SECURITY;

--
-- Name: runtime_settings settings_read_policy; Type: POLICY; Schema: core; Owner: -
--

CREATE POLICY settings_read_policy ON core.runtime_settings FOR SELECT USING (((NOT is_secret) OR (CURRENT_USER = ANY (ARRAY['postgres'::name, 'admin'::name]))));


--
-- Name: runtime_settings settings_write_policy; Type: POLICY; Schema: core; Owner: -
--

CREATE POLICY settings_write_policy ON core.runtime_settings USING ((CURRENT_USER = ANY (ARRAY['postgres'::name, 'admin'::name])));


--
-- PostgreSQL database dump complete
--
