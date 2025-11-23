-- =============================================================================
-- CORE v2.2 — Self-Improving System Schema
-- Designed for A1+ Autonomy with Qdrant Vector Integration
--
-- Design Principles:
-- - UUID type consistency (native uuid everywhere, no text UUIDs)
-- - symbol_path as natural key, id as immutable PK
-- - Single Source of Truth (Links Table only, no Arrays for relationships)
-- - Production-ready materialized view management
-- - Full observability and audit trails
-- =============================================================================

CREATE SCHEMA IF NOT EXISTS core;

-- Helper function for auto-updating timestamps
CREATE OR REPLACE FUNCTION core.set_updated_at() RETURNS trigger
    LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at = NOW();
  RETURN NEW;
END;
$$;

-- =============================================================================
-- SECTION 1: KNOWLEDGE LAYER (What exists in the codebase)
-- =============================================================================

-- Core code symbols discovered via AST analysis
CREATE TABLE IF NOT EXISTS core.symbols (
    -- Primary key: Immutable UUID for referential integrity
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Natural key: Human-readable, unique, but may change during refactoring
    symbol_path text NOT NULL UNIQUE,

    -- Location & structure
    module text NOT NULL,                    -- File path
    qualname text NOT NULL,                  -- Qualified name
    kind text NOT NULL CHECK (kind IN ('function', 'class', 'method', 'module')),

    -- Structure & fingerprinting
    ast_signature text NOT NULL,             -- Structural signature
    fingerprint text NOT NULL,               -- Hash (non-unique: same pattern, different contexts)

    -- Lifecycle
    state text DEFAULT 'discovered' NOT NULL CHECK (
        state IN ('discovered', 'classified', 'bound', 'verified', 'deprecated')
    ),
    health_status text DEFAULT 'unknown' CHECK (
        health_status IN ('healthy', 'needs_review', 'deprecated', 'broken', 'unknown')
    ),
    is_public boolean NOT NULL DEFAULT true,

    -- History tracking for autonomous refactoring
    previous_paths text[],                   -- Track symbol renames/moves

    -- Capability key and AI-generated description
    key text,
    intent text,

    -- Vectorization state tracking
    embedding_model text DEFAULT 'text-embedding-3-small',
    last_embedded timestamptz, -- Timestamp of the last successful vectorization

    -- Calls (Dependencies)
    calls jsonb DEFAULT '[]'::jsonb,

    -- Timestamps
    first_seen timestamptz DEFAULT now() NOT NULL,
    last_seen timestamptz DEFAULT now() NOT NULL,
    last_modified timestamptz DEFAULT now() NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_symbols_module ON core.symbols(module);
CREATE INDEX IF NOT EXISTS idx_symbols_kind ON core.symbols(kind);
CREATE INDEX IF NOT EXISTS idx_symbols_state ON core.symbols(state);
CREATE INDEX IF NOT EXISTS idx_symbols_health ON core.symbols(health_status);
CREATE INDEX IF NOT EXISTS idx_symbols_qualname ON core.symbols(qualname);
CREATE INDEX IF NOT EXISTS idx_symbols_fingerprint ON core.symbols(fingerprint);
-- Optimization for path lookups (added in v2.2)
CREATE INDEX IF NOT EXISTS idx_symbols_path_pattern ON core.symbols (symbol_path text_pattern_ops);

-- Lookup helper for natural key usage
CREATE OR REPLACE FUNCTION core.get_symbol_id(path text)
RETURNS uuid AS $$
    SELECT id FROM core.symbols WHERE symbol_path = path;
$$ LANGUAGE sql STABLE;

COMMENT ON FUNCTION core.get_symbol_id IS
    'Helper to look up symbol UUID by its natural key (symbol_path). Usage: get_symbol_id(''my.module:MyClass'')';

-- System capabilities (what CORE can do)
CREATE TABLE IF NOT EXISTS core.capabilities (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name text NOT NULL,
    domain text DEFAULT 'general' NOT NULL,
    title text NOT NULL,
    objective text,
    owner text NOT NULL,

    -- NOTE: 'entry_points' array removed in v2.2 to prevent split-brain.
    -- Use core.symbol_capability_links instead.
    
    dependencies jsonb DEFAULT '[]'::jsonb,  -- Required capability names
    test_coverage numeric(5,2),              -- 0-100%

    -- Metadata
    tags jsonb DEFAULT '[]'::jsonb NOT NULL CHECK (jsonb_typeof(tags) = 'array'),
    status text DEFAULT 'Active' CHECK (status IN ('Active', 'Draft', 'Deprecated')),

    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL,

    UNIQUE(domain, name)
);

CREATE INDEX IF NOT EXISTS idx_capabilities_domain ON core.capabilities(domain);
CREATE INDEX IF NOT EXISTS idx_capabilities_status ON core.capabilities(status);

-- Link symbols to capabilities they implement (The Single Source of Truth)
CREATE TABLE IF NOT EXISTS core.symbol_capability_links (
    symbol_id uuid NOT NULL REFERENCES core.symbols(id) ON DELETE CASCADE,
    capability_id uuid NOT NULL REFERENCES core.capabilities(id) ON DELETE CASCADE,
    confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source text NOT NULL CHECK (source IN ('auditor-infer', 'manual', 'rule', 'llm-classified')),
    verified boolean DEFAULT false NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY (symbol_id, capability_id, source)
);

CREATE INDEX IF NOT EXISTS idx_links_capability ON core.symbol_capability_links(capability_id);
CREATE INDEX IF NOT EXISTS idx_links_verified ON core.symbol_capability_links(verified);

-- Domains for organizing capabilities
CREATE TABLE IF NOT EXISTS core.domains (
    key text PRIMARY KEY,
    title text NOT NULL,
    description text,
    created_at timestamptz DEFAULT now() NOT NULL
);

-- =============================================================================
-- SECTION 2: GOVERNANCE LAYER (Constitutional compliance)
-- =============================================================================

-- Change proposals requiring approval
CREATE TABLE IF NOT EXISTS core.proposals (
    id bigserial PRIMARY KEY,
    target_path text NOT NULL,
    content_sha256 char(64) NOT NULL,
    justification text NOT NULL,
    risk_tier text DEFAULT 'low' CHECK (risk_tier IN ('low', 'medium', 'high')),
    is_critical boolean DEFAULT false NOT NULL,
    status text DEFAULT 'open' NOT NULL CHECK (
        status IN ('open', 'approved', 'rejected', 'superseded')
    ),
    created_at timestamptz DEFAULT now() NOT NULL,
    created_by text NOT NULL
);

-- Cryptographic approval signatures
CREATE TABLE IF NOT EXISTS core.proposal_signatures (
    proposal_id bigint NOT NULL REFERENCES core.proposals(id) ON DELETE CASCADE,
    approver_identity text NOT NULL,
    signature_base64 text NOT NULL,
    signed_at timestamptz DEFAULT now() NOT NULL,
    is_valid boolean DEFAULT true NOT NULL,
    PRIMARY KEY (proposal_id, approver_identity)
);

-- Audit runs tracking
CREATE TABLE IF NOT EXISTS core.audit_runs (
    id bigserial PRIMARY KEY,
    source text NOT NULL,
    commit_sha char(40),
    score numeric(4,3),
    passed boolean NOT NULL,
    violations_found integer DEFAULT 0,
    started_at timestamptz DEFAULT now() NOT NULL,
    finished_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_audit_runs_passed ON core.audit_runs(passed, started_at DESC);

-- =============================================================================
-- SECTION 3: OPERATIONAL LAYER (What's happening right now)
-- =============================================================================

-- LLM resources available to cognitive roles
CREATE TABLE IF NOT EXISTS core.llm_resources (
    name text PRIMARY KEY,
    env_prefix text NOT NULL UNIQUE,
    provided_capabilities jsonb DEFAULT '[]'::jsonb CHECK (jsonb_typeof(provided_capabilities) = 'array'),
    performance_metadata jsonb,
    is_available boolean DEFAULT true,
    created_at timestamptz DEFAULT now() NOT NULL
);

-- AI cognitive roles (specialized agents)
CREATE TABLE IF NOT EXISTS core.cognitive_roles (
    role text PRIMARY KEY,
    description text,
    assigned_resource text REFERENCES core.llm_resources(name),
    required_capabilities jsonb DEFAULT '[]'::jsonb CHECK (jsonb_typeof(required_capabilities) = 'array'),
    max_concurrent_tasks integer DEFAULT 1,
    specialization jsonb,                    -- {"good_at": [...], "avoid": [...]}
    is_active boolean DEFAULT true,
    created_at timestamptz DEFAULT now() NOT NULL
);

-- Task queue: what agents need to do
CREATE TABLE IF NOT EXISTS core.tasks (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    intent text NOT NULL,                    -- User's request
    assigned_role text REFERENCES core.cognitive_roles(role),
    parent_task_id uuid REFERENCES core.tasks(id),  -- For decomposition

    -- Execution state
    status text DEFAULT 'pending' NOT NULL CHECK (
        status IN ('pending', 'planning', 'executing', 'validating', 'completed', 'failed', 'blocked')
    ),
    plan jsonb,                              -- Agent's execution plan
    context jsonb DEFAULT '{}'::jsonb,       -- Working memory for this task
    error_message text,
    failure_reason text,

    -- Vector retrieval context (from Qdrant) - native UUID arrays
    relevant_symbols uuid[],                 -- Symbol UUIDs from vector search
    context_retrieval_query text,            -- What we searched for
    context_retrieved_at timestamptz,
    context_tokens_used integer,

    -- Constitutional compliance
    requires_approval boolean DEFAULT false,
    proposal_id bigint REFERENCES core.proposals(id), -- Links to governance

    -- Metrics
    estimated_complexity integer CHECK (estimated_complexity BETWEEN 1 AND 10),
    actual_duration_seconds integer,

    -- Timestamps
    created_at timestamptz DEFAULT now() NOT NULL,
    started_at timestamptz,
    completed_at timestamptz
);

CREATE INDEX IF NOT EXISTS idx_tasks_status ON core.tasks(status) WHERE status IN ('pending', 'executing', 'blocked');
CREATE INDEX IF NOT EXISTS idx_tasks_role ON core.tasks(assigned_role);
CREATE INDEX IF NOT EXISTS idx_tasks_parent ON core.tasks(parent_task_id);
CREATE INDEX IF NOT EXISTS idx_tasks_created ON core.tasks(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_tasks_relevant_symbols ON core.tasks USING GIN(relevant_symbols);

COMMENT ON COLUMN core.tasks.relevant_symbols IS
    'Array of symbol UUIDs retrieved from Qdrant vector search for this task context';

-- Link tasks to proposals they generated
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 FROM pg_constraint
        WHERE conname = 'fk_tasks_proposal' AND conrelid = 'core.tasks'::regclass
    ) THEN
        ALTER TABLE core.tasks
        ADD CONSTRAINT fk_tasks_proposal
        FOREIGN KEY (proposal_id) REFERENCES core.proposals(id);
    END IF;
END;
$$;

-- Constitutional violations detected by auditor
CREATE TABLE IF NOT EXISTS core.constitutional_violations (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    rule_id text NOT NULL,
    symbol_id uuid REFERENCES core.symbols(id),
    task_id uuid REFERENCES core.tasks(id),
    severity text NOT NULL CHECK (severity IN ('info', 'warning', 'error', 'critical')),
    description text NOT NULL,
    detected_at timestamptz DEFAULT now() NOT NULL,
    resolved_at timestamptz,
    resolution_notes text
);

CREATE INDEX IF NOT EXISTS idx_violations_unresolved ON core.constitutional_violations(severity, detected_at)
    WHERE resolved_at IS NULL;
CREATE INDEX IF NOT EXISTS idx_violations_symbol ON core.constitutional_violations(symbol_id);
CREATE INDEX IF NOT EXISTS idx_violations_task ON core.constitutional_violations(task_id);

-- Action log: everything agents do
CREATE TABLE IF NOT EXISTS core.actions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES core.tasks(id) ON DELETE CASCADE,
    action_type text NOT NULL CHECK (
        action_type IN ('file_read', 'file_write', 'symbol_analysis', 'llm_call',
                       'shell_command', 'validation', 'vector_search', 'test_run')
    ),
    target text,                             -- File path, symbol ID, command, etc.
    payload jsonb,                           -- Input details
    result jsonb,                            -- Output/response
    success boolean NOT NULL,
    cognitive_role text NOT NULL,
    reasoning text,                          -- Why this action?
    duration_ms integer,
    created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_actions_task ON core.actions(task_id);
CREATE INDEX IF NOT EXISTS idx_actions_type ON core.actions(action_type);
CREATE INDEX IF NOT EXISTS idx_actions_created ON core.actions(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_actions_success ON core.actions(success) WHERE success = false;

-- Agent decisions: choice points for debugging
CREATE TABLE IF NOT EXISTS core.agent_decisions (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES core.tasks(id),
    decision_point text NOT NULL,            -- "What to do next?"
    options_considered jsonb NOT NULL,       -- All possible choices
    chosen_option text NOT NULL,
    reasoning text NOT NULL,                 -- WHY this choice?
    confidence numeric(3,2) NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    was_correct boolean,                     -- Post-hoc evaluation
    decided_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decisions_task ON core.agent_decisions(task_id);
CREATE INDEX IF NOT EXISTS idx_decisions_confidence ON core.agent_decisions(confidence);

-- Short-term agent memory (expires)
CREATE TABLE IF NOT EXISTS core.agent_memory (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    cognitive_role text NOT NULL,
    memory_type text NOT NULL CHECK (memory_type IN ('fact', 'observation', 'decision', 'pattern', 'error')),
    content text NOT NULL,
    related_task_id uuid REFERENCES core.tasks(id),
    relevance_score numeric(3,2) DEFAULT 1.0 CHECK (relevance_score BETWEEN 0 AND 1),
    expires_at timestamptz,                  -- NULL = permanent
    created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_memory_role_type ON core.agent_memory(cognitive_role, memory_type);
CREATE INDEX IF NOT EXISTS idx_memory_expires ON core.agent_memory(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_memory_relevance ON core.agent_memory(relevance_score DESC);

-- =============================================================================
-- SECTION 4: VECTOR INTEGRATION LAYER (Qdrant sync)
-- =============================================================================

-- Link table between symbols and their vectors in Qdrant
CREATE TABLE IF NOT EXISTS core.symbol_vector_links (
    symbol_id uuid PRIMARY KEY NOT NULL REFERENCES core.symbols(id) ON DELETE CASCADE,
    vector_id UUID NOT NULL, -- The UUID ID used in Qdrant
    embedding_model text NOT NULL,
    embedding_version integer NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_symbol_vector_links_vector_id ON core.symbol_vector_links(vector_id);


-- Track Qdrant synchronization
CREATE TABLE IF NOT EXISTS core.vector_sync_log (
    id bigserial PRIMARY KEY,
    operation text NOT NULL CHECK (operation IN ('upsert', 'delete', 'bulk_update', 'reindex')),
    symbol_ids uuid[],                       -- Native UUID array
    qdrant_collection text NOT NULL,
    success boolean NOT NULL,
    error_message text,
    batch_size integer,
    duration_ms integer,
    synced_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_vector_sync_failed ON core.vector_sync_log(success, synced_at) WHERE success = false;
CREATE INDEX IF NOT EXISTS idx_vector_sync_collection ON core.vector_sync_log(qdrant_collection);
CREATE INDEX IF NOT EXISTS idx_vector_sync_symbols ON core.vector_sync_log USING GIN(symbol_ids);

-- Track retrieval quality for optimization
CREATE TABLE IF NOT EXISTS core.retrieval_feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid NOT NULL REFERENCES core.tasks(id),
    query text NOT NULL,
    retrieved_symbols uuid[],                -- Native UUID array
    actually_used_symbols uuid[],            -- Which ones were actually modified/read?
    retrieval_quality integer CHECK (retrieval_quality BETWEEN 1 AND 5),
    notes text,
    created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_retrieval_task ON core.retrieval_feedback(task_id);
CREATE INDEX IF NOT EXISTS idx_retrieval_quality ON core.retrieval_feedback(retrieval_quality);
CREATE INDEX IF NOT EXISTS idx_retrieval_symbols ON core.retrieval_feedback USING GIN(retrieved_symbols);
CREATE INDEX IF NOT EXISTS idx_retrieval_used ON core.retrieval_feedback USING GIN(actually_used_symbols);

-- Semantic cache for LLM responses
CREATE TABLE IF NOT EXISTS core.semantic_cache (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    query_hash text NOT NULL UNIQUE,
    query_text text NOT NULL,
    vector_id text,                          -- Also in Qdrant for semantic lookup
    response_text text NOT NULL,
    cognitive_role text,
    llm_model text NOT NULL,
    tokens_used integer,
    confidence numeric(3,2) CHECK (confidence BETWEEN 0 AND 1),
    hit_count integer DEFAULT 0,
    expires_at timestamptz,
    created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_cache_hash ON core.semantic_cache(query_hash);
CREATE INDEX IF NOT EXISTS idx_cache_expires ON core.semantic_cache(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_cache_hits ON core.semantic_cache(hit_count DESC);

-- =============================================================================
-- SECTION 5: LEARNING & FEEDBACK LAYER
-- =============================================================================

-- General feedback loop
CREATE TABLE IF NOT EXISTS core.feedback (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id uuid REFERENCES core.tasks(id),
    action_id uuid REFERENCES core.actions(id),
    feedback_type text NOT NULL CHECK (
        feedback_type IN ('success', 'failure', 'improvement', 'validation_error', 'user_correction')
    ),
    message text NOT NULL,
    corrective_action text,
    applied boolean DEFAULT false,
    created_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_feedback_task ON core.feedback(task_id);
CREATE INDEX IF NOT EXISTS idx_feedback_applied ON core.feedback(applied) WHERE applied = false;

-- =============================================================================
-- SECTION 6: SYSTEM METADATA
-- =============================================================================

-- CLI commands exposed by CORE
CREATE TABLE IF NOT EXISTS core.cli_commands (
    name text PRIMARY KEY,
    module text NOT NULL,
    entrypoint text NOT NULL,
    summary text,
    category text
);

-- Runtime services
CREATE TABLE IF NOT EXISTS core.runtime_services (
    name text PRIMARY KEY,
    implementation text NOT NULL UNIQUE,
    is_active boolean DEFAULT true
);

-- Migration tracking
CREATE TABLE IF NOT EXISTS core._migrations (
    id text PRIMARY KEY,
    applied_at timestamptz DEFAULT now() NOT NULL
);

-- Export manifests
CREATE TABLE IF NOT EXISTS core.export_manifests (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    exported_at timestamptz DEFAULT now() NOT NULL,
    who text,
    environment text,
    notes text
);

CREATE TABLE IF NOT EXISTS core.export_digests (
    path text PRIMARY KEY,
    sha256 text NOT NULL,
    manifest_id uuid NOT NULL REFERENCES core.export_manifests(id) ON DELETE CASCADE,
    exported_at timestamptz DEFAULT now() NOT NULL
);

-- Mission statement (The Northstar)
CREATE TABLE IF NOT EXISTS core.northstar (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    mission text NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL
);

-- Runtime configuration
CREATE TABLE IF NOT EXISTS core.runtime_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT,
    is_secret BOOLEAN NOT NULL DEFAULT FALSE,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE core.runtime_settings IS 'Single source of truth for runtime configuration, loaded from .env and managed by `core-admin manage dotenv sync`.';
COMMENT ON COLUMN core.runtime_settings.is_secret IS 'If true, the value should be handled with care.';

-- =============================================================================
-- SECTION 6A: CONTEXT PACKETS (ContextPackage Artifacts)
-- =============================================================================
-- Context Packets Table
-- Stores metadata for ContextPackage artifacts

CREATE TABLE IF NOT EXISTS core.context_packets (
    -- Identity
    packet_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    task_id VARCHAR(255) NOT NULL,
    task_type VARCHAR(50) NOT NULL,

    -- Timestamps
    created_at TIMESTAMP WITH TIME ZONE NOT NULL DEFAULT NOW(),

    -- Privacy & governance
    privacy VARCHAR(20) NOT NULL CHECK (privacy IN ('local_only', 'remote_allowed')),
    remote_allowed BOOLEAN NOT NULL DEFAULT FALSE,

    -- Hashing & caching
    packet_hash VARCHAR(64) NOT NULL,
    cache_key VARCHAR(64),

    -- Metrics
    tokens_est INTEGER NOT NULL DEFAULT 0,
    size_bytes INTEGER NOT NULL DEFAULT 0,
    build_ms INTEGER NOT NULL DEFAULT 0,
    items_count INTEGER NOT NULL DEFAULT 0,
    redactions_count INTEGER NOT NULL DEFAULT 0,

    -- Storage
    path TEXT NOT NULL,

    -- Extensible metadata
    metadata JSONB NOT NULL DEFAULT '{}'::jsonb,

    -- Audit
    builder_version VARCHAR(20) NOT NULL,

    -- Constraints
    CONSTRAINT valid_task_type CHECK (
        task_type IN ('docstring.fix', 'header.fix', 'test.generate', 'code.generate', 'refactor')
    ),
    CONSTRAINT positive_metrics CHECK (
        tokens_est >= 0 AND
        size_bytes >= 0 AND
        build_ms >= 0 AND
        items_count >= 0 AND
        redactions_count >= 0
    )
);

-- Indexes for common queries
CREATE INDEX IF NOT EXISTS idx_context_packets_task_id ON core.context_packets(task_id);
CREATE INDEX IF NOT EXISTS idx_context_packets_task_type ON core.context_packets(task_type);
CREATE INDEX IF NOT EXISTS idx_context_packets_packet_hash ON core.context_packets(packet_hash);
CREATE INDEX IF NOT EXISTS idx_context_packets_created_at ON core.context_packets(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_context_packets_cache_key ON core.context_packets(cache_key) WHERE cache_key IS NOT NULL;

-- GIN index for metadata JSONB queries
CREATE INDEX IF NOT EXISTS idx_context_packets_metadata ON core.context_packets USING GIN(metadata);

-- Comments
COMMENT ON TABLE core.context_packets IS 'Metadata for ContextPackage artifacts created by ContextService';
COMMENT ON COLUMN core.context_packets.packet_id IS 'Unique identifier for this packet';
COMMENT ON COLUMN core.context_packets.task_id IS 'Associated task identifier';
COMMENT ON COLUMN core.context_packets.task_type IS 'Type of task (docstring.fix, test.generate, etc.)';
COMMENT ON COLUMN core.context_packets.privacy IS 'Privacy level: local_only or remote_allowed';
COMMENT ON COLUMN core.context_packets.remote_allowed IS 'Whether packet can be sent to remote LLMs';
COMMENT ON COLUMN core.context_packets.packet_hash IS 'SHA256 hash of packet content for validation';
COMMENT ON COLUMN core.context_packets.cache_key IS 'Hash of task spec for cache lookup';
COMMENT ON COLUMN core.context_packets.tokens_est IS 'Estimated token count for packet';
COMMENT ON COLUMN core.context_packets.size_bytes IS 'Size of serialized packet in bytes';
COMMENT ON COLUMN core.context_packets.build_ms IS 'Time taken to build packet in milliseconds';
COMMENT ON COLUMN core.context_packets.items_count IS 'Number of items in context array';
COMMENT ON COLUMN core.context_packets.redactions_count IS 'Number of redactions applied';
COMMENT ON COLUMN core.context_packets.path IS 'File path to serialized packet YAML';
COMMENT ON COLUMN core.context_packets.metadata IS 'Extensible metadata (provenance, stats, etc.)';
COMMENT ON COLUMN core.context_packets.builder_version IS 'Version of ContextBuilder that created packet';

-- =============================================================================
-- SECTION 7: MATERIALIZED VIEW MANAGEMENT (Production-Ready)
-- =============================================================================

-- Track materialized view refresh operations
CREATE TABLE IF NOT EXISTS core.mv_refresh_log (
    view_name text PRIMARY KEY,
    last_refresh_started timestamptz,
    last_refresh_completed timestamptz,
    last_refresh_duration_ms integer,
    rows_affected integer,
    triggered_by text
);

-- Refresh function with logging and observability
CREATE OR REPLACE FUNCTION core.refresh_materialized_view(view_name text)
RETURNS TABLE(
    duration_ms integer,
    rows_affected integer
) AS $$
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
$$ LANGUAGE plpgsql;

COMMENT ON FUNCTION core.refresh_materialized_view IS
    'Refresh a materialized view with logging. Usage: SELECT * FROM core.refresh_materialized_view(''core.mv_symbol_usage_patterns'');';

-- =============================================================================
-- SECTION 8: OPERATIONAL VIEWS
-- =============================================================================

CREATE OR REPLACE VIEW core.v_symbols_needing_embedding AS
SELECT s.id, s.module, s.qualname, s.symbol_path, s.ast_signature, s.fingerprint
FROM core.symbols s
WHERE s.last_embedded IS NULL OR s.last_modified > s.last_embedded
ORDER BY s.last_modified DESC;

-- FIXED: Now checks Link Table (not array)
CREATE OR REPLACE VIEW core.v_orphan_symbols AS
SELECT s.id, s.symbol_path, s.module, s.qualname, s.kind, s.state, s.health_status
FROM core.symbols s
LEFT JOIN core.symbol_capability_links l ON l.symbol_id = s.id
WHERE l.symbol_id IS NULL
  AND s.state != 'deprecated'
  AND s.health_status != 'deprecated'
ORDER BY s.last_modified DESC;

CREATE OR REPLACE VIEW core.v_verified_coverage AS
SELECT
    c.id AS capability_id,
    c.name,
    c.domain,
    COUNT(l.symbol_id) AS verified_symbols,
    c.test_coverage,
    c.status
FROM core.capabilities c
LEFT JOIN core.symbol_capability_links l ON l.capability_id = c.id AND l.verified = true
GROUP BY c.id, c.name, c.domain, c.test_coverage, c.status
ORDER BY c.domain, c.name;

CREATE OR REPLACE VIEW core.v_agent_workload AS
SELECT
    cr.role,
    cr.is_active,
    COUNT(t.id) FILTER (WHERE t.status = 'executing') as active_tasks,
    COUNT(t.id) FILTER (WHERE t.status = 'pending') as queued_tasks,
    COUNT(t.id) FILTER (WHERE t.status = 'blocked') as blocked_tasks,
    cr.max_concurrent_tasks,
    (cr.max_concurrent_tasks - COUNT(t.id) FILTER (WHERE t.status = 'executing')) as available_slots,
    cr.assigned_resource
FROM core.cognitive_roles cr
LEFT JOIN core.tasks t ON t.assigned_role = cr.role
    AND t.status IN ('pending', 'executing', 'blocked')
GROUP BY cr.role, cr.is_active, cr.max_concurrent_tasks, cr.assigned_resource
ORDER BY cr.role;

CREATE OR REPLACE VIEW core.v_agent_context AS
SELECT
    t.id as task_id,
    t.intent,
    t.assigned_role,
    t.status,
    t.relevant_symbols,
    array_length(t.relevant_symbols, 1) as context_symbol_count,
    (SELECT json_agg(json_build_object(
        'action', a.action_type,
        'success', a.success,
        'target', a.target,
        'reasoning', a.reasoning
    ) ORDER BY a.created_at DESC)
    FROM core.actions a
    WHERE a.task_id = t.id
    LIMIT 10) as recent_actions,
    (SELECT json_agg(json_build_object(
        'type', am.memory_type,
        'content', am.content,
        'score', am.relevance_score
    ) ORDER BY am.relevance_score DESC)
    FROM core.agent_memory am
    WHERE am.cognitive_role = t.assigned_role
      AND (am.expires_at IS NULL OR am.expires_at > now())
    LIMIT 5) as active_memories,
    (SELECT json_agg(json_build_object(
        'point', ad.decision_point,
        'chosen', ad.chosen_option,
        'reasoning', ad.reasoning,
        'confidence', ad.confidence
    ) ORDER BY ad.decided_at DESC)
    FROM core.agent_decisions ad
    WHERE ad.task_id = t.id
    LIMIT 5) as recent_decisions
FROM core.tasks t
WHERE t.status IN ('pending', 'executing', 'planning')
ORDER BY t.created_at;

-- FIXED: Replaced Materialized View with Standard View (No Refresh Lag)
CREATE OR REPLACE VIEW core.knowledge_graph AS
SELECT
    s.id as uuid,
    s.symbol_path,
    s.module as file_path,
    s.qualname as name,
    s.kind as type,
    s.state as status,
    s.health_status,
    s.is_public,
    s.fingerprint as structural_hash,
    s.updated_at AS last_updated,
    s.key as capability,
    s.intent,
    vl.vector_id,
    COALESCE(
        (SELECT json_agg(DISTINCT c.name ORDER BY c.name)
         FROM core.symbol_capability_links l
         JOIN core.capabilities c ON c.id = l.capability_id
         WHERE l.symbol_id = s.id),
        '[]'::json
    ) as capabilities_array,
    (s.kind = 'class') AS is_class,
    (s.qualname LIKE 'Test%' OR s.qualname LIKE 'test_%') AS is_test,
    (SELECT COUNT(*) FROM core.actions a WHERE a.target = s.symbol_path) as action_count
FROM core.symbols s
LEFT JOIN core.symbol_vector_links vl ON s.id = vl.symbol_id
ORDER BY s.updated_at DESC;

CREATE OR REPLACE VIEW core.v_stale_materialized_views AS
SELECT
    view_name,
    last_refresh_completed,
    now() - last_refresh_completed as age,
    last_refresh_duration_ms,
    rows_affected,
    (
        last_refresh_completed IS NULL
        OR last_refresh_completed < now() - interval '10 minutes'
    ) as is_stale
FROM core.mv_refresh_log
WHERE (last_refresh_completed IS NULL OR last_refresh_completed < now() - interval '10 minutes')
ORDER BY last_refresh_completed NULLS FIRST;

-- =============================================================================
-- SECTION 9: TRIGGERS
-- =============================================================================

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_capabilities_updated_at') THEN
        CREATE TRIGGER trg_capabilities_updated_at
            BEFORE UPDATE ON core.capabilities
            FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();
    END IF;

    IF NOT EXISTS (SELECT 1 FROM pg_trigger WHERE tgname = 'trg_symbols_updated_at') THEN
        CREATE TRIGGER trg_symbols_updated_at
            BEFORE UPDATE ON core.symbols
            FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();
    END IF;
END$$;

-- CLEANUP: Drop Legacy MV if exists (Using standard View now)
DROP MATERIALIZED VIEW IF EXISTS core.mv_symbol_usage_patterns;

-- Permissions
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA core TO core_db;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA core TO core_db;

-- =============================================================================
-- SECTION 10: AUTOMATED MIGRATION LOGIC
-- =============================================================================

DO $$
BEGIN
    -- Check if the legacy 'entry_points' column still exists
    IF EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_schema = 'core' 
          AND table_name = 'capabilities' 
          AND column_name = 'entry_points'
    ) THEN
        RAISE NOTICE 'Legacy entry_points column found. Migrating data...';

        -- 1. Migrate valid links (ignoring Ghost IDs that don't exist in symbols table)
        INSERT INTO core.symbol_capability_links (symbol_id, capability_id, confidence, source, verified)
        SELECT DISTINCT
            raw_links.symbol_uuid,
            raw_links.capability_id,
            1.0,
            'manual', -- Valid enum value
            true
        FROM (
            SELECT unnest(entry_points) AS symbol_uuid, id AS capability_id
            FROM core.capabilities
            WHERE entry_points IS NOT NULL
        ) raw_links
        JOIN core.symbols s ON s.id = raw_links.symbol_uuid -- FILTER GHOSTS (Critical Fix)
        ON CONFLICT (symbol_id, capability_id, source) DO NOTHING;

        -- 2. Drop the column to enforce 3rd Normal Form
        ALTER TABLE core.capabilities DROP COLUMN entry_points;
        
        RAISE NOTICE 'Migration complete. Legacy column dropped.';
    END IF;
END$$;