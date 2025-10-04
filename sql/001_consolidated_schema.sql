-- =============================================================================
-- CORE v2.1 — Self-Improving System Schema
-- Designed for A1+ Autonomy with Qdrant Vector Integration
--
-- Design Principles:
-- - UUID type consistency (native uuid everywhere, no text UUIDs)
-- - symbol_path as natural key, id as immutable PK
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

    -- Vector integration (Qdrant stores UUIDs as text: id::text)
    vector_id text,                          -- ID in Qdrant collection (= id::text)
    embedding_model text DEFAULT 'text-embedding-3-small',
    embedding_version integer DEFAULT 1,
    last_embedded timestamptz,

    -- Timestamps
    first_seen timestamptz DEFAULT now() NOT NULL,
    last_seen timestamptz DEFAULT now() NOT NULL,
    last_modified timestamptz DEFAULT now() NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX idx_symbols_module ON core.symbols(module);
CREATE INDEX idx_symbols_kind ON core.symbols(kind);
CREATE INDEX idx_symbols_state ON core.symbols(state);
CREATE INDEX idx_symbols_health ON core.symbols(health_status);
CREATE INDEX idx_symbols_vector ON core.symbols(vector_id) WHERE vector_id IS NOT NULL;
CREATE INDEX idx_symbols_qualname ON core.symbols(qualname);
CREATE INDEX idx_symbols_fingerprint ON core.symbols(fingerprint);

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

    -- Implementation tracking (arrays of UUIDs)
    entry_points uuid[] DEFAULT '{}',        -- Main symbol IDs
    dependencies jsonb DEFAULT '[]'::jsonb,  -- Required capability names
    test_coverage numeric(5,2),              -- 0-100%

    -- Metadata
    tags jsonb DEFAULT '[]'::jsonb NOT NULL CHECK (jsonb_typeof(tags) = 'array'),
    status text DEFAULT 'Active' CHECK (status IN ('Active', 'Draft', 'Deprecated')),

    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL,

    UNIQUE(domain, name)
);

CREATE INDEX idx_capabilities_domain ON core.capabilities(domain);
CREATE INDEX idx_capabilities_status ON core.capabilities(status);
CREATE INDEX idx_capabilities_entry_points ON core.capabilities USING GIN(entry_points);

COMMENT ON COLUMN core.capabilities.entry_points IS
    'Array of symbol UUIDs that serve as primary entry points for this capability';

-- Link symbols to capabilities they implement
CREATE TABLE IF NOT EXISTS core.symbol_capability_links (
    symbol_id uuid NOT NULL REFERENCES core.symbols(id) ON DELETE CASCADE,
    capability_id uuid NOT NULL REFERENCES core.capabilities(id) ON DELETE CASCADE,
    confidence numeric NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    source text NOT NULL CHECK (source IN ('auditor-infer', 'manual', 'rule', 'llm-classified')),
    verified boolean DEFAULT false NOT NULL,
    created_at timestamptz DEFAULT now() NOT NULL,
    PRIMARY KEY (symbol_id, capability_id, source)
);

CREATE INDEX idx_links_capability ON core.symbol_capability_links(capability_id);
CREATE INDEX idx_links_verified ON core.symbol_capability_links(verified);

-- Domains for organizing capabilities
CREATE TABLE IF NOT EXISTS core.domains (
    key text PRIMARY KEY,
    title text NOT NULL,
    description text,
    created_at timestamptz DEFAULT now() NOT NULL
);

-- =============================================================================
-- SECTION 2: OPERATIONAL LAYER (What's happening right now)
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

    -- Vector retrieval context (from Qdrant) - native UUID arrays
    relevant_symbols uuid[],                 -- Symbol UUIDs from vector search
    context_retrieval_query text,            -- What we searched for
    context_retrieved_at timestamptz,
    context_tokens_used integer,

    -- Constitutional compliance
    requires_approval boolean DEFAULT false,
    proposal_id bigint,                      -- Links to governance

    -- Metrics
    estimated_complexity integer CHECK (estimated_complexity BETWEEN 1 AND 10),
    actual_duration_seconds integer,

    -- Timestamps
    created_at timestamptz DEFAULT now() NOT NULL,
    started_at timestamptz,
    completed_at timestamptz
);

CREATE INDEX idx_tasks_status ON core.tasks(status) WHERE status IN ('pending', 'executing', 'blocked');
CREATE INDEX idx_tasks_role ON core.tasks(assigned_role);
CREATE INDEX idx_tasks_parent ON core.tasks(parent_task_id);
CREATE INDEX idx_tasks_created ON core.tasks(created_at DESC);
CREATE INDEX idx_tasks_relevant_symbols ON core.tasks USING GIN(relevant_symbols);

COMMENT ON COLUMN core.tasks.relevant_symbols IS
    'Array of symbol UUIDs retrieved from Qdrant vector search for this task context';

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

CREATE INDEX idx_actions_task ON core.actions(task_id);
CREATE INDEX idx_actions_type ON core.actions(action_type);
CREATE INDEX idx_actions_created ON core.actions(created_at DESC);
CREATE INDEX idx_actions_success ON core.actions(success) WHERE success = false;

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

CREATE INDEX idx_decisions_task ON core.agent_decisions(task_id);
CREATE INDEX idx_decisions_confidence ON core.agent_decisions(confidence);

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

CREATE INDEX idx_memory_role_type ON core.agent_memory(cognitive_role, memory_type);
CREATE INDEX idx_memory_expires ON core.agent_memory(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_memory_relevance ON core.agent_memory(relevance_score DESC);

-- =============================================================================
-- SECTION 3: GOVERNANCE LAYER (Constitutional compliance)
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

CREATE INDEX idx_proposals_status ON core.proposals(status);
CREATE INDEX idx_proposals_created ON core.proposals(created_at DESC);

-- Cryptographic approval signatures
CREATE TABLE IF NOT EXISTS core.proposal_signatures (
    proposal_id bigint NOT NULL REFERENCES core.proposals(id) ON DELETE CASCADE,
    approver_identity text NOT NULL,
    signature_base64 text NOT NULL,
    signed_at timestamptz DEFAULT now() NOT NULL,
    is_valid boolean DEFAULT true NOT NULL,
    PRIMARY KEY (proposal_id, approver_identity)
);

-- Link tasks to proposals they generated
ALTER TABLE core.tasks
    ADD CONSTRAINT fk_tasks_proposal
    FOREIGN KEY (proposal_id) REFERENCES core.proposals(id);

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

CREATE INDEX idx_violations_unresolved ON core.constitutional_violations(severity, detected_at)
    WHERE resolved_at IS NULL;
CREATE INDEX idx_violations_symbol ON core.constitutional_violations(symbol_id);
CREATE INDEX idx_violations_task ON core.constitutional_violations(task_id);

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

CREATE INDEX idx_audit_runs_passed ON core.audit_runs(passed, started_at DESC);

-- =============================================================================
-- SECTION 4: VECTOR INTEGRATION LAYER (Qdrant sync)
-- =============================================================================

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

CREATE INDEX idx_vector_sync_failed ON core.vector_sync_log(success, synced_at) WHERE success = false;
CREATE INDEX idx_vector_sync_collection ON core.vector_sync_log(qdrant_collection);
CREATE INDEX idx_vector_sync_symbols ON core.vector_sync_log USING GIN(symbol_ids);

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

CREATE INDEX idx_retrieval_task ON core.retrieval_feedback(task_id);
CREATE INDEX idx_retrieval_quality ON core.retrieval_feedback(retrieval_quality);
CREATE INDEX idx_retrieval_symbols ON core.retrieval_feedback USING GIN(retrieved_symbols);
CREATE INDEX idx_retrieval_used ON core.retrieval_feedback USING GIN(actually_used_symbols);

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

CREATE INDEX idx_cache_hash ON core.semantic_cache(query_hash);
CREATE INDEX idx_cache_expires ON core.semantic_cache(expires_at) WHERE expires_at IS NOT NULL;
CREATE INDEX idx_cache_hits ON core.semantic_cache(hit_count DESC);

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

CREATE INDEX idx_feedback_task ON core.feedback(task_id);
CREATE INDEX idx_feedback_applied ON core.feedback(applied) WHERE applied = false;

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
    -- Log start
    INSERT INTO core.mv_refresh_log (view_name, last_refresh_started, triggered_by)
    VALUES (view_name, start_time, current_user)
    ON CONFLICT (view_name)
    DO UPDATE SET last_refresh_started = start_time, triggered_by = current_user;

    -- Perform refresh
    EXECUTE format('REFRESH MATERIALIZED VIEW CONCURRENTLY %I', view_name);

    -- Get row count
    EXECUTE format('SELECT COUNT(*) FROM %I', view_name) INTO rows_count;

    -- Calculate duration
    duration := EXTRACT(EPOCH FROM (now() - start_time)) * 1000;

    -- Log completion
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

-- Symbols needing embedding/re-embedding
CREATE OR REPLACE VIEW core.v_symbols_needing_embedding AS
SELECT id, module, qualname, symbol_path, ast_signature, fingerprint
FROM core.symbols
WHERE vector_id IS NULL
   OR last_embedded < last_modified
   OR embedding_version < 1
ORDER BY last_modified DESC;

-- Orphaned symbols (not linked to capabilities)
CREATE OR REPLACE VIEW core.v_orphan_symbols AS
SELECT s.id, s.symbol_path, s.module, s.qualname, s.kind, s.state, s.health_status
FROM core.symbols s
LEFT JOIN core.symbol_capability_links l ON l.symbol_id = s.id
WHERE l.symbol_id IS NULL
  AND s.state != 'deprecated'
  AND s.health_status != 'deprecated'
ORDER BY s.last_modified DESC;

-- Capability coverage
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

-- Agent workload
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

-- Active agent context (what each agent can see)
CREATE OR REPLACE VIEW core.v_agent_context AS
SELECT
    t.id as task_id,
    t.intent,
    t.assigned_role,
    t.status,
    t.relevant_symbols,
    array_length(t.relevant_symbols, 1) as context_symbol_count,

    -- Recent actions for context
    (SELECT json_agg(json_build_object(
        'action', a.action_type,
        'success', a.success,
        'target', a.target,
        'reasoning', a.reasoning
    ) ORDER BY a.created_at DESC)
    FROM core.actions a
    WHERE a.task_id = t.id
    LIMIT 10) as recent_actions,

    -- Active memories
    (SELECT json_agg(json_build_object(
        'type', am.memory_type,
        'content', am.content,
        'score', am.relevance_score
    ) ORDER BY am.relevance_score DESC)
    FROM core.agent_memory am
    WHERE am.cognitive_role = t.assigned_role
      AND (am.expires_at IS NULL OR am.expires_at > now())
    LIMIT 5) as active_memories,

    -- Recent decisions
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

-- Knowledge graph (simplified, real data only)
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
    s.vector_id,
    s.updated_at AS last_updated,

    -- Linked capabilities (real data from joins)
    COALESCE(
        (SELECT json_agg(DISTINCT c.name ORDER BY c.name)
         FROM core.symbol_capability_links l
         JOIN core.capabilities c ON c.id = l.capability_id
         WHERE l.symbol_id = s.id),
        '[]'::json
    ) as capabilities,

    -- Computed flags
    (s.kind = 'class') AS is_class,
    (s.qualname LIKE 'Test%' OR s.qualname LIKE 'test_%') AS is_test,

    -- Usage statistics (if available)
    (SELECT COUNT(*) FROM core.actions a WHERE a.target = s.symbol_path) as action_count

FROM core.symbols s
ORDER BY s.updated_at DESC;

-- Stale materialized views monitoring
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
    -- Auto-update timestamps
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

-- =============================================================================
-- SECTION 10: MATERIALIZED VIEW FOR ANALYTICS
-- =============================================================================

-- Symbol usage patterns (refresh periodically for optimization insights)
CREATE MATERIALIZED VIEW IF NOT EXISTS core.mv_symbol_usage_patterns AS
SELECT
    s.id,
    s.symbol_path,
    s.module,
    s.kind,
    s.state,
    s.health_status,

    -- Action statistics
    COUNT(DISTINCT a.task_id) FILTER (WHERE a.action_type = 'file_write') as times_modified,
    COUNT(DISTINCT a.task_id) FILTER (WHERE a.action_type = 'file_read') as times_read,

    -- Retrieval statistics
    COUNT(DISTINCT rf.task_id) as times_retrieved,
    CASE
        WHEN COUNT(DISTINCT rf.task_id) > 0
        THEN COUNT(DISTINCT a.task_id) FILTER (WHERE a.action_type IN ('file_write', 'file_read'))::numeric
             / COUNT(DISTINCT rf.task_id)
        ELSE 0
    END as retrieval_precision,

    -- Capability associations
    array_agg(DISTINCT c.name) FILTER (WHERE c.name IS NOT NULL) as associated_capabilities,

    -- Timestamps
    MAX(a.created_at) as last_action_at,
    MAX(rf.created_at) as last_retrieved_at

FROM core.symbols s
LEFT JOIN core.actions a ON a.target = s.symbol_path
LEFT JOIN core.retrieval_feedback rf ON s.id = ANY(rf.retrieved_symbols)
LEFT JOIN core.symbol_capability_links l ON l.symbol_id = s.id
LEFT JOIN core.capabilities c ON c.id = l.capability_id
GROUP BY s.id, s.symbol_path, s.module, s.kind, s.state, s.health_status;

CREATE UNIQUE INDEX idx_mv_usage_id ON core.mv_symbol_usage_patterns(id);
CREATE INDEX idx_mv_usage_precision ON core.mv_symbol_usage_patterns(retrieval_precision DESC);
CREATE INDEX idx_mv_usage_modified ON core.mv_symbol_usage_patterns(times_modified DESC);
CREATE INDEX idx_mv_usage_last_action ON core.mv_symbol_usage_patterns(last_action_at DESC NULLS LAST);

COMMENT ON MATERIALIZED VIEW core.mv_symbol_usage_patterns IS
    'Analytics view for symbol usage patterns. Refresh with: SELECT * FROM core.refresh_materialized_view(''core.mv_symbol_usage_patterns'');';

-- Initialize refresh log entry
INSERT INTO core.mv_refresh_log (view_name, triggered_by)
VALUES ('core.mv_symbol_usage_patterns', 'schema_init')
ON CONFLICT (view_name) DO NOTHING;
