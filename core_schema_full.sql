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

ALTER TABLE IF EXISTS ONLY core.tasks DROP CONSTRAINT IF EXISTS tasks_proposal_id_fkey;
ALTER TABLE IF EXISTS ONLY core.tasks DROP CONSTRAINT IF EXISTS tasks_parent_task_id_fkey;
ALTER TABLE IF EXISTS ONLY core.tasks DROP CONSTRAINT IF EXISTS tasks_assigned_role_fkey;
ALTER TABLE IF EXISTS ONLY core.symbol_vector_links DROP CONSTRAINT IF EXISTS symbol_vector_links_symbol_id_fkey;
ALTER TABLE IF EXISTS ONLY core.symbol_capability_links DROP CONSTRAINT IF EXISTS symbol_capability_links_symbol_id_fkey;
ALTER TABLE IF EXISTS ONLY core.symbol_capability_links DROP CONSTRAINT IF EXISTS symbol_capability_links_capability_id_fkey;
ALTER TABLE IF EXISTS ONLY core.retrieval_feedback DROP CONSTRAINT IF EXISTS retrieval_feedback_task_id_fkey;
ALTER TABLE IF EXISTS ONLY core.proposal_signatures DROP CONSTRAINT IF EXISTS proposal_signatures_proposal_id_fkey;
ALTER TABLE IF EXISTS ONLY core.tasks DROP CONSTRAINT IF EXISTS fk_tasks_proposal;
ALTER TABLE IF EXISTS ONLY core.feedback DROP CONSTRAINT IF EXISTS feedback_task_id_fkey;
ALTER TABLE IF EXISTS ONLY core.feedback DROP CONSTRAINT IF EXISTS feedback_action_id_fkey;
ALTER TABLE IF EXISTS ONLY core.export_digests DROP CONSTRAINT IF EXISTS export_digests_manifest_id_fkey;
ALTER TABLE IF EXISTS ONLY core.constitutional_violations DROP CONSTRAINT IF EXISTS constitutional_violations_task_id_fkey;
ALTER TABLE IF EXISTS ONLY core.constitutional_violations DROP CONSTRAINT IF EXISTS constitutional_violations_symbol_id_fkey;
ALTER TABLE IF EXISTS ONLY core.cognitive_roles DROP CONSTRAINT IF EXISTS cognitive_roles_assigned_resource_fkey;
ALTER TABLE IF EXISTS ONLY core.agent_memory DROP CONSTRAINT IF EXISTS agent_memory_related_task_id_fkey;
ALTER TABLE IF EXISTS ONLY core.agent_decisions DROP CONSTRAINT IF EXISTS agent_decisions_task_id_fkey;
ALTER TABLE IF EXISTS ONLY core.actions DROP CONSTRAINT IF EXISTS actions_task_id_fkey;
DROP TRIGGER IF EXISTS trg_symbols_updated_at ON core.symbols;
DROP TRIGGER IF EXISTS trg_capabilities_updated_at ON core.capabilities;
DROP INDEX IF EXISTS core.idx_violations_unresolved;
DROP INDEX IF EXISTS core.idx_violations_task;
DROP INDEX IF EXISTS core.idx_violations_symbol;
DROP INDEX IF EXISTS core.idx_vector_sync_symbols;
DROP INDEX IF EXISTS core.idx_vector_sync_failed;
DROP INDEX IF EXISTS core.idx_vector_sync_collection;
DROP INDEX IF EXISTS core.idx_tasks_status;
DROP INDEX IF EXISTS core.idx_tasks_role;
DROP INDEX IF EXISTS core.idx_tasks_relevant_symbols;
DROP INDEX IF EXISTS core.idx_tasks_parent;
DROP INDEX IF EXISTS core.idx_tasks_created;
DROP INDEX IF EXISTS core.idx_symbols_state;
DROP INDEX IF EXISTS core.idx_symbols_qualname;
DROP INDEX IF EXISTS core.idx_symbols_module;
DROP INDEX IF EXISTS core.idx_symbols_kind;
DROP INDEX IF EXISTS core.idx_symbols_health;
DROP INDEX IF EXISTS core.idx_symbols_fingerprint;
DROP INDEX IF EXISTS core.idx_symbol_vector_links_vector_id;
DROP INDEX IF EXISTS core.idx_retrieval_used;
DROP INDEX IF EXISTS core.idx_retrieval_task;
DROP INDEX IF EXISTS core.idx_retrieval_symbols;
DROP INDEX IF EXISTS core.idx_retrieval_quality;
DROP INDEX IF EXISTS core.idx_observability_metrics_timestamp;
DROP INDEX IF EXISTS core.idx_observability_metrics_tags_gin;
DROP INDEX IF EXISTS core.idx_observability_metrics_name_timestamp;
DROP INDEX IF EXISTS core.idx_observability_metrics_name;
DROP INDEX IF EXISTS core.idx_observability_logs_timestamp;
DROP INDEX IF EXISTS core.idx_observability_logs_outcome;
DROP INDEX IF EXISTS core.idx_observability_logs_correlation_id;
DROP INDEX IF EXISTS core.idx_observability_logs_context_gin;
DROP INDEX IF EXISTS core.idx_observability_logs_action_id;
DROP INDEX IF EXISTS core.idx_observability_decisions_type;
DROP INDEX IF EXISTS core.idx_observability_decisions_timestamp;
DROP INDEX IF EXISTS core.idx_observability_decisions_policies_gin;
DROP INDEX IF EXISTS core.idx_observability_decisions_outcome_gin;
DROP INDEX IF EXISTS core.idx_observability_decisions_decision_id;
DROP INDEX IF EXISTS core.idx_observability_decisions_correlation_id;
DROP INDEX IF EXISTS core.idx_observability_decisions_context_gin;
DROP INDEX IF EXISTS core.idx_memory_role_type;
DROP INDEX IF EXISTS core.idx_memory_relevance;
DROP INDEX IF EXISTS core.idx_memory_expires;
DROP INDEX IF EXISTS core.idx_links_verified;
DROP INDEX IF EXISTS core.idx_links_capability;
DROP INDEX IF EXISTS core.idx_feedback_task;
DROP INDEX IF EXISTS core.idx_feedback_applied;
DROP INDEX IF EXISTS core.idx_decisions_task;
DROP INDEX IF EXISTS core.idx_decisions_confidence;
DROP INDEX IF EXISTS core.idx_context_packets_task_type;
DROP INDEX IF EXISTS core.idx_context_packets_task_id;
DROP INDEX IF EXISTS core.idx_context_packets_packet_hash;
DROP INDEX IF EXISTS core.idx_context_packets_metadata;
DROP INDEX IF EXISTS core.idx_context_packets_created_at;
DROP INDEX IF EXISTS core.idx_context_packets_cache_key;
DROP INDEX IF EXISTS core.idx_capabilities_status;
DROP INDEX IF EXISTS core.idx_capabilities_domain;
DROP INDEX IF EXISTS core.idx_cache_hits;
DROP INDEX IF EXISTS core.idx_cache_hash;
DROP INDEX IF EXISTS core.idx_cache_expires;
DROP INDEX IF EXISTS core.idx_audit_runs_passed;
DROP INDEX IF EXISTS core.idx_actions_type;
DROP INDEX IF EXISTS core.idx_actions_task;
DROP INDEX IF EXISTS core.idx_actions_success;
DROP INDEX IF EXISTS core.idx_actions_created;
ALTER TABLE IF EXISTS ONLY core.vector_sync_log DROP CONSTRAINT IF EXISTS vector_sync_log_pkey;
ALTER TABLE IF EXISTS ONLY core.tasks DROP CONSTRAINT IF EXISTS tasks_pkey;
ALTER TABLE IF EXISTS ONLY core.symbols DROP CONSTRAINT IF EXISTS symbols_symbol_path_key;
ALTER TABLE IF EXISTS ONLY core.symbols DROP CONSTRAINT IF EXISTS symbols_pkey;
ALTER TABLE IF EXISTS ONLY core.symbol_vector_links DROP CONSTRAINT IF EXISTS symbol_vector_links_pkey;
ALTER TABLE IF EXISTS ONLY core.symbol_capability_links DROP CONSTRAINT IF EXISTS symbol_capability_links_pkey;
ALTER TABLE IF EXISTS ONLY core.semantic_cache DROP CONSTRAINT IF EXISTS semantic_cache_query_hash_key;
ALTER TABLE IF EXISTS ONLY core.semantic_cache DROP CONSTRAINT IF EXISTS semantic_cache_pkey;
ALTER TABLE IF EXISTS ONLY core.runtime_settings DROP CONSTRAINT IF EXISTS runtime_settings_pkey;
ALTER TABLE IF EXISTS ONLY core.runtime_services DROP CONSTRAINT IF EXISTS runtime_services_pkey;
ALTER TABLE IF EXISTS ONLY core.runtime_services DROP CONSTRAINT IF EXISTS runtime_services_implementation_key;
ALTER TABLE IF EXISTS ONLY core.retrieval_feedback DROP CONSTRAINT IF EXISTS retrieval_feedback_pkey;
ALTER TABLE IF EXISTS ONLY core.proposals DROP CONSTRAINT IF EXISTS proposals_pkey;
ALTER TABLE IF EXISTS ONLY core.proposal_signatures DROP CONSTRAINT IF EXISTS proposal_signatures_pkey;
ALTER TABLE IF EXISTS ONLY core.observability_metrics DROP CONSTRAINT IF EXISTS observability_metrics_pkey;
ALTER TABLE IF EXISTS ONLY core.observability_logs DROP CONSTRAINT IF EXISTS observability_logs_pkey;
ALTER TABLE IF EXISTS ONLY core.observability_decisions DROP CONSTRAINT IF EXISTS observability_decisions_pkey;
ALTER TABLE IF EXISTS ONLY core.observability_decisions DROP CONSTRAINT IF EXISTS observability_decisions_decision_id_key;
ALTER TABLE IF EXISTS ONLY core.northstar DROP CONSTRAINT IF EXISTS northstar_pkey;
ALTER TABLE IF EXISTS ONLY core.mv_refresh_log DROP CONSTRAINT IF EXISTS mv_refresh_log_pkey;
ALTER TABLE IF EXISTS ONLY core.observability_metrics DROP CONSTRAINT IF EXISTS metrics_unique_point;
ALTER TABLE IF EXISTS ONLY core.llm_resources DROP CONSTRAINT IF EXISTS llm_resources_pkey;
ALTER TABLE IF EXISTS ONLY core.llm_resources DROP CONSTRAINT IF EXISTS llm_resources_env_prefix_key;
ALTER TABLE IF EXISTS ONLY core.feedback DROP CONSTRAINT IF EXISTS feedback_pkey;
ALTER TABLE IF EXISTS ONLY core.export_manifests DROP CONSTRAINT IF EXISTS export_manifests_pkey;
ALTER TABLE IF EXISTS ONLY core.export_digests DROP CONSTRAINT IF EXISTS export_digests_pkey;
ALTER TABLE IF EXISTS ONLY core.domains DROP CONSTRAINT IF EXISTS domains_pkey;
ALTER TABLE IF EXISTS ONLY core.context_packets DROP CONSTRAINT IF EXISTS context_packets_pkey;
ALTER TABLE IF EXISTS ONLY core.constitutional_violations DROP CONSTRAINT IF EXISTS constitutional_violations_pkey;
ALTER TABLE IF EXISTS ONLY core.cognitive_roles DROP CONSTRAINT IF EXISTS cognitive_roles_pkey;
ALTER TABLE IF EXISTS ONLY core.cli_commands DROP CONSTRAINT IF EXISTS cli_commands_pkey;
ALTER TABLE IF EXISTS ONLY core.capabilities DROP CONSTRAINT IF EXISTS capabilities_pkey;
ALTER TABLE IF EXISTS ONLY core.capabilities DROP CONSTRAINT IF EXISTS capabilities_domain_name_key;
ALTER TABLE IF EXISTS ONLY core.audit_runs DROP CONSTRAINT IF EXISTS audit_runs_pkey;
ALTER TABLE IF EXISTS ONLY core.agent_memory DROP CONSTRAINT IF EXISTS agent_memory_pkey;
ALTER TABLE IF EXISTS ONLY core.agent_decisions DROP CONSTRAINT IF EXISTS agent_decisions_pkey;
ALTER TABLE IF EXISTS ONLY core.actions DROP CONSTRAINT IF EXISTS actions_pkey;
ALTER TABLE IF EXISTS ONLY core._migrations DROP CONSTRAINT IF EXISTS _migrations_pkey;
ALTER TABLE IF EXISTS core.vector_sync_log ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS core.proposals ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS core.observability_metrics ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS core.observability_logs ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS core.observability_decisions ALTER COLUMN id DROP DEFAULT;
ALTER TABLE IF EXISTS core.audit_runs ALTER COLUMN id DROP DEFAULT;
DROP SEQUENCE IF EXISTS core.vector_sync_log_id_seq;
DROP TABLE IF EXISTS core.vector_sync_log;
DROP VIEW IF EXISTS core.v_verified_coverage;
DROP VIEW IF EXISTS core.v_symbols_needing_embedding;
DROP VIEW IF EXISTS core.v_stale_materialized_views;
DROP VIEW IF EXISTS core.v_orphan_symbols;
DROP VIEW IF EXISTS core.v_observability_recent_failures;
DROP VIEW IF EXISTS core.v_observability_action_health;
DROP VIEW IF EXISTS core.v_agent_workload;
DROP VIEW IF EXISTS core.v_agent_context;
DROP TABLE IF EXISTS core.tasks;
DROP TABLE IF EXISTS core.semantic_cache;
DROP TABLE IF EXISTS core.runtime_settings;
DROP TABLE IF EXISTS core.runtime_services;
DROP TABLE IF EXISTS core.retrieval_feedback;
DROP SEQUENCE IF EXISTS core.proposals_id_seq;
DROP TABLE IF EXISTS core.proposals;
DROP TABLE IF EXISTS core.proposal_signatures;
DROP SEQUENCE IF EXISTS core.observability_metrics_id_seq;
DROP TABLE IF EXISTS core.observability_metrics;
DROP SEQUENCE IF EXISTS core.observability_logs_id_seq;
DROP TABLE IF EXISTS core.observability_logs;
DROP SEQUENCE IF EXISTS core.observability_decisions_id_seq;
DROP TABLE IF EXISTS core.observability_decisions;
DROP TABLE IF EXISTS core.northstar;
DROP TABLE IF EXISTS core.mv_refresh_log;
DROP TABLE IF EXISTS core.llm_resources;
DROP VIEW IF EXISTS core.knowledge_graph;
DROP TABLE IF EXISTS core.symbols;
DROP TABLE IF EXISTS core.symbol_vector_links;
DROP TABLE IF EXISTS core.symbol_capability_links;
DROP TABLE IF EXISTS core.feedback;
DROP TABLE IF EXISTS core.export_manifests;
DROP TABLE IF EXISTS core.export_digests;
DROP TABLE IF EXISTS core.domains;
DROP TABLE IF EXISTS core.context_packets;
DROP TABLE IF EXISTS core.constitutional_violations;
DROP TABLE IF EXISTS core.cognitive_roles;
DROP TABLE IF EXISTS core.cli_commands;
DROP TABLE IF EXISTS core.capabilities;
DROP SEQUENCE IF EXISTS core.audit_runs_id_seq;
DROP TABLE IF EXISTS core.audit_runs;
DROP TABLE IF EXISTS core.agent_memory;
DROP TABLE IF EXISTS core.agent_decisions;
DROP TABLE IF EXISTS core.actions;
DROP TABLE IF EXISTS core._migrations;
DROP FUNCTION IF EXISTS core.set_updated_at();
DROP FUNCTION IF EXISTS core.refresh_materialized_view(view_name text);
DROP FUNCTION IF EXISTS core.get_symbol_id(path text);
DROP FUNCTION IF EXISTS core.cleanup_observability_metrics();
DROP FUNCTION IF EXISTS core.cleanup_observability_logs();
DROP SCHEMA IF EXISTS core;
--
-- Name: core; Type: SCHEMA; Schema: -; Owner: -
--

CREATE SCHEMA core;


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
    confidence numeric(3,2) NOT NULL,
    was_correct boolean,
    decided_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT agent_decisions_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))
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
    relevance_score numeric(3,2) DEFAULT 1.0,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT agent_memory_memory_type_check CHECK ((memory_type = ANY (ARRAY['fact'::text, 'observation'::text, 'decision'::text, 'pattern'::text, 'error'::text]))),
    CONSTRAINT agent_memory_relevance_score_check CHECK (((relevance_score >= (0)::numeric) AND (relevance_score <= (1)::numeric)))
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
    CONSTRAINT capabilities_status_check CHECK ((status = ANY (ARRAY['Active'::text, 'Draft'::text, 'Deprecated'::text]))),
    CONSTRAINT capabilities_tags_check CHECK ((jsonb_typeof(tags) = 'array'::text))
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
    confidence numeric NOT NULL,
    source text NOT NULL,
    verified boolean DEFAULT false NOT NULL,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT symbol_capability_links_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric))),
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
    CONSTRAINT symbols_health_status_check CHECK ((health_status = ANY (ARRAY['healthy'::text, 'needs_review'::text, 'deprecated'::text, 'broken'::text, 'unknown'::text]))),
    CONSTRAINT symbols_kind_check CHECK ((kind = ANY (ARRAY['function'::text, 'class'::text, 'method'::text, 'module'::text]))),
    CONSTRAINT symbols_state_check CHECK ((state = ANY (ARRAY['discovered'::text, 'classified'::text, 'bound'::text, 'verified'::text, 'deprecated'::text])))
);


--
-- Name: knowledge_graph; Type: VIEW; Schema: core; Owner: -
--

CREATE VIEW core.knowledge_graph AS
 SELECT s.id AS uuid,
    s.symbol_path,
    s.module AS file_path,
    s.qualname AS name,
    s.kind AS type,
    s.state AS status,
    s.health_status,
    s.is_public,
    s.fingerprint AS structural_hash,
    s.updated_at AS last_updated,
    s.key AS capability,
    s.intent,
    s.calls,
    vl.vector_id,
    COALESCE(( SELECT json_agg(DISTINCT c.name ORDER BY c.name) AS json_agg
           FROM (core.symbol_capability_links l
             JOIN core.capabilities c ON ((c.id = l.capability_id)))
          WHERE (l.symbol_id = s.id)), '[]'::json) AS capabilities_array,
    (s.kind = 'class'::text) AS is_class,
    ((s.qualname ~~ 'Test%'::text) OR (s.qualname ~~ 'test_%'::text)) AS is_test,
    ( SELECT count(*) AS count
           FROM core.actions a
          WHERE (a.target = s.symbol_path)) AS action_count
   FROM (core.symbols s
     LEFT JOIN core.symbol_vector_links vl ON ((s.id = vl.symbol_id)))
  ORDER BY s.updated_at DESC;


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
    confidence numeric(3,2),
    hit_count integer DEFAULT 0,
    expires_at timestamp with time zone,
    created_at timestamp with time zone DEFAULT now() NOT NULL,
    CONSTRAINT semantic_cache_confidence_check CHECK (((confidence >= (0)::numeric) AND (confidence <= (1)::numeric)))
);


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
    CONSTRAINT tasks_estimated_complexity_check CHECK (((estimated_complexity >= 1) AND (estimated_complexity <= 10))),
    CONSTRAINT tasks_status_check CHECK ((status = ANY (ARRAY['pending'::text, 'planning'::text, 'executing'::text, 'validating'::text, 'completed'::text, 'failed'::text, 'blocked'::text])))
);


--
-- Name: COLUMN tasks.relevant_symbols; Type: COMMENT; Schema: core; Owner: -
--

COMMENT ON COLUMN core.tasks.relevant_symbols IS 'Array of symbol UUIDs retrieved from Qdrant vector search for this task context';


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
-- Name: vector_sync_log id; Type: DEFAULT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.vector_sync_log ALTER COLUMN id SET DEFAULT nextval('core.vector_sync_log_id_seq'::regclass);


--
-- Name: _migrations _migrations_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core._migrations
    ADD CONSTRAINT _migrations_pkey PRIMARY KEY (id);


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
-- Name: domains domains_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.domains
    ADD CONSTRAINT domains_pkey PRIMARY KEY (key);


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
-- Name: symbol_vector_links symbol_vector_links_pkey; Type: CONSTRAINT; Schema: core; Owner: -
--

ALTER TABLE ONLY core.symbol_vector_links
    ADD CONSTRAINT symbol_vector_links_pkey PRIMARY KEY (symbol_id);


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
-- Name: idx_actions_created; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_created ON core.actions USING btree (created_at DESC);


--
-- Name: idx_actions_success; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_success ON core.actions USING btree (success) WHERE (success = false);


--
-- Name: idx_actions_task; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_task ON core.actions USING btree (task_id);


--
-- Name: idx_actions_type; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_actions_type ON core.actions USING btree (action_type);


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
-- Name: idx_capabilities_domain; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_capabilities_domain ON core.capabilities USING btree (domain);


--
-- Name: idx_capabilities_status; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_capabilities_status ON core.capabilities USING btree (status);


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
-- Name: idx_decisions_confidence; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_decisions_confidence ON core.agent_decisions USING btree (confidence);


--
-- Name: idx_decisions_task; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_decisions_task ON core.agent_decisions USING btree (task_id);


--
-- Name: idx_feedback_applied; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_feedback_applied ON core.feedback USING btree (applied) WHERE (applied = false);


--
-- Name: idx_feedback_task; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_feedback_task ON core.feedback USING btree (task_id);


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
-- Name: idx_observability_logs_correlation_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_logs_correlation_id ON core.observability_logs USING btree (correlation_id);


--
-- Name: idx_observability_logs_outcome; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_observability_logs_outcome ON core.observability_logs USING btree (outcome) WHERE ((outcome)::text <> 'success'::text);


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
-- Name: idx_symbol_vector_links_vector_id; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbol_vector_links_vector_id ON core.symbol_vector_links USING btree (vector_id);


--
-- Name: idx_symbols_fingerprint; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_fingerprint ON core.symbols USING btree (fingerprint);


--
-- Name: idx_symbols_health; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_health ON core.symbols USING btree (health_status);


--
-- Name: idx_symbols_kind; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_kind ON core.symbols USING btree (kind);


--
-- Name: idx_symbols_module; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_module ON core.symbols USING btree (module);


--
-- Name: idx_symbols_qualname; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_qualname ON core.symbols USING btree (qualname);


--
-- Name: idx_symbols_state; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_symbols_state ON core.symbols USING btree (state);


--
-- Name: idx_tasks_created; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_created ON core.tasks USING btree (created_at DESC);


--
-- Name: idx_tasks_parent; Type: INDEX; Schema: core; Owner: -
--

CREATE INDEX idx_tasks_parent ON core.tasks USING btree (parent_task_id);


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
-- Name: capabilities trg_capabilities_updated_at; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trg_capabilities_updated_at BEFORE UPDATE ON core.capabilities FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


--
-- Name: symbols trg_symbols_updated_at; Type: TRIGGER; Schema: core; Owner: -
--

CREATE TRIGGER trg_symbols_updated_at BEFORE UPDATE ON core.symbols FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();


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
-- Name: TABLE actions; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.actions TO core;
GRANT ALL ON TABLE core.actions TO core_db;


--
-- Name: TABLE agent_decisions; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.agent_decisions TO core;
GRANT ALL ON TABLE core.agent_decisions TO core_db;


--
-- Name: TABLE agent_memory; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.agent_memory TO core;
GRANT ALL ON TABLE core.agent_memory TO core_db;


--
-- Name: TABLE audit_runs; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.audit_runs TO core;
GRANT ALL ON TABLE core.audit_runs TO core_db;


--
-- Name: SEQUENCE audit_runs_id_seq; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON SEQUENCE core.audit_runs_id_seq TO core;
GRANT ALL ON SEQUENCE core.audit_runs_id_seq TO core_db;


--
-- Name: TABLE capabilities; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.capabilities TO core;
GRANT ALL ON TABLE core.capabilities TO core_db;


--
-- Name: TABLE cli_commands; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.cli_commands TO core;
GRANT ALL ON TABLE core.cli_commands TO core_db;


--
-- Name: TABLE cognitive_roles; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.cognitive_roles TO core;
GRANT ALL ON TABLE core.cognitive_roles TO core_db;


--
-- Name: TABLE constitutional_violations; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.constitutional_violations TO core;
GRANT ALL ON TABLE core.constitutional_violations TO core_db;


--
-- Name: TABLE context_packets; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.context_packets TO core;
GRANT ALL ON TABLE core.context_packets TO core_db;


--
-- Name: TABLE domains; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.domains TO core;
GRANT ALL ON TABLE core.domains TO core_db;


--
-- Name: TABLE export_digests; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.export_digests TO core;
GRANT ALL ON TABLE core.export_digests TO core_db;


--
-- Name: TABLE export_manifests; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.export_manifests TO core;
GRANT ALL ON TABLE core.export_manifests TO core_db;


--
-- Name: TABLE feedback; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.feedback TO core;
GRANT ALL ON TABLE core.feedback TO core_db;


--
-- Name: TABLE symbol_capability_links; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.symbol_capability_links TO core;
GRANT ALL ON TABLE core.symbol_capability_links TO core_db;


--
-- Name: TABLE symbol_vector_links; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.symbol_vector_links TO core;
GRANT ALL ON TABLE core.symbol_vector_links TO core_db;


--
-- Name: TABLE symbols; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.symbols TO core;
GRANT ALL ON TABLE core.symbols TO core_db;


--
-- Name: TABLE llm_resources; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.llm_resources TO core;
GRANT ALL ON TABLE core.llm_resources TO core_db;


--
-- Name: TABLE mv_refresh_log; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.mv_refresh_log TO core;
GRANT ALL ON TABLE core.mv_refresh_log TO core_db;


--
-- Name: TABLE northstar; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.northstar TO core;
GRANT ALL ON TABLE core.northstar TO core_db;


--
-- Name: TABLE observability_decisions; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.observability_decisions TO core;
GRANT ALL ON TABLE core.observability_decisions TO core_db;


--
-- Name: SEQUENCE observability_decisions_id_seq; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON SEQUENCE core.observability_decisions_id_seq TO core;


--
-- Name: TABLE observability_logs; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.observability_logs TO core;
GRANT ALL ON TABLE core.observability_logs TO core_db;


--
-- Name: SEQUENCE observability_logs_id_seq; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON SEQUENCE core.observability_logs_id_seq TO core;


--
-- Name: TABLE observability_metrics; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.observability_metrics TO core;
GRANT ALL ON TABLE core.observability_metrics TO core_db;


--
-- Name: SEQUENCE observability_metrics_id_seq; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON SEQUENCE core.observability_metrics_id_seq TO core;


--
-- Name: TABLE proposal_signatures; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.proposal_signatures TO core;
GRANT ALL ON TABLE core.proposal_signatures TO core_db;


--
-- Name: TABLE proposals; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.proposals TO core;
GRANT ALL ON TABLE core.proposals TO core_db;


--
-- Name: SEQUENCE proposals_id_seq; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON SEQUENCE core.proposals_id_seq TO core;
GRANT ALL ON SEQUENCE core.proposals_id_seq TO core_db;


--
-- Name: TABLE retrieval_feedback; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.retrieval_feedback TO core;
GRANT ALL ON TABLE core.retrieval_feedback TO core_db;


--
-- Name: TABLE runtime_services; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.runtime_services TO core;
GRANT ALL ON TABLE core.runtime_services TO core_db;


--
-- Name: TABLE runtime_settings; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.runtime_settings TO core;
GRANT ALL ON TABLE core.runtime_settings TO core_db;


--
-- Name: TABLE semantic_cache; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.semantic_cache TO core;
GRANT ALL ON TABLE core.semantic_cache TO core_db;


--
-- Name: TABLE tasks; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.tasks TO core;
GRANT ALL ON TABLE core.tasks TO core_db;


--
-- Name: TABLE v_agent_context; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.v_agent_context TO core;
GRANT ALL ON TABLE core.v_agent_context TO core_db;


--
-- Name: TABLE v_agent_workload; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.v_agent_workload TO core;
GRANT ALL ON TABLE core.v_agent_workload TO core_db;


--
-- Name: TABLE v_observability_action_health; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.v_observability_action_health TO core;
GRANT ALL ON TABLE core.v_observability_action_health TO core_db;


--
-- Name: TABLE v_observability_recent_failures; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.v_observability_recent_failures TO core;
GRANT ALL ON TABLE core.v_observability_recent_failures TO core_db;


--
-- Name: TABLE v_orphan_symbols; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.v_orphan_symbols TO core;
GRANT ALL ON TABLE core.v_orphan_symbols TO core_db;


--
-- Name: TABLE v_stale_materialized_views; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.v_stale_materialized_views TO core;
GRANT ALL ON TABLE core.v_stale_materialized_views TO core_db;


--
-- Name: TABLE v_symbols_needing_embedding; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.v_symbols_needing_embedding TO core;
GRANT ALL ON TABLE core.v_symbols_needing_embedding TO core_db;


--
-- Name: TABLE v_verified_coverage; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.v_verified_coverage TO core;
GRANT ALL ON TABLE core.v_verified_coverage TO core_db;


--
-- Name: TABLE vector_sync_log; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON TABLE core.vector_sync_log TO core;
GRANT ALL ON TABLE core.vector_sync_log TO core_db;


--
-- Name: SEQUENCE vector_sync_log_id_seq; Type: ACL; Schema: core; Owner: -
--

GRANT ALL ON SEQUENCE core.vector_sync_log_id_seq TO core;
GRANT ALL ON SEQUENCE core.vector_sync_log_id_seq TO core_db;


--
-- PostgreSQL database dump complete
--
