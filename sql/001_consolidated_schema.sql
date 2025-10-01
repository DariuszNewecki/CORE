-- FILE: sql/001_consolidated_schema.sql
--
-- This is the single, canonical source of truth for the CORE operational database schema.
-- It is a consolidation of all previous migration files (001-009).
--
-- This script is designed to be IDEMPOTENT. It can be run safely on a new or existing
-- database, as all object creation statements use `IF NOT EXISTS` or `OR REPLACE`.
--

-- =============================================================================
-- SECTION 1: CORE SCHEMA
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS core;


-- =============================================================================
-- SECTION 2: KNOWLEDGE & SYMBOL CATALOG (The Mind's Database)
-- =============================================================================

-- Domains for architectural classification
CREATE TABLE IF NOT EXISTS core.domains (
    key          TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- The central table for all discovered code symbols (functions, classes, etc.)
CREATE TABLE IF NOT EXISTS core.symbols (
    uuid            TEXT PRIMARY KEY,
    symbol_path     TEXT NOT NULL UNIQUE,
    file_path       TEXT NOT NULL,
    is_public       BOOLEAN NOT NULL DEFAULT FALSE,
    title           TEXT,
    description     TEXT,
    owner           TEXT NOT NULL DEFAULT 'unassigned_agent',
    status          TEXT NOT NULL DEFAULT 'active',
    structural_hash CHAR(64),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- Merged from later migrations
    key             TEXT,
    domain_key      TEXT REFERENCES core.domains(key) ON DELETE SET NULL,
    vector          JSONB,
    vector_id       TEXT -- Storing the Qdrant point ID for cross-reference
);

-- A new capabilities table, distinct from the old one, for high-level tracking.
CREATE TABLE IF NOT EXISTS core.capabilities (
  id TEXT PRIMARY KEY,          -- The canonical key, e.g., 'introspection.vectorize'
  title TEXT NOT NULL,
  owner TEXT NOT NULL,
  implementing_files JSONB,     -- A JSON array of file paths like ["src/features/introspection/service.py"]
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Junction table for many-to-many relationship between symbols and capabilities
CREATE TABLE IF NOT EXISTS core.symbol_capabilities (
    symbol_uuid TEXT NOT NULL REFERENCES core.symbols(uuid) ON DELETE CASCADE,
    capability_key TEXT NOT NULL, -- This will be validated by the application layer
    PRIMARY KEY (symbol_uuid, capability_key)
);


-- =============================================================================
-- SECTION 3: OPERATIONAL KNOWLEDGE (Runtime Configuration)
-- =============================================================================

-- Table for LLM Resources, replacing resource_manifest.yaml
CREATE TABLE IF NOT EXISTS core.llm_resources (
    name TEXT PRIMARY KEY,
    provided_capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    env_prefix TEXT NOT NULL UNIQUE,
    performance_metadata JSONB
);

-- Table for Cognitive Roles, replacing cognitive_roles.yaml
CREATE TABLE IF NOT EXISTS core.cognitive_roles (
    "role" TEXT PRIMARY KEY,
    description TEXT,
    assigned_resource TEXT REFERENCES core.llm_resources(name),
    required_capabilities JSONB NOT NULL DEFAULT '[]'::jsonb
);

-- Table for Runtime Services, replacing runtime_services.yaml
CREATE TABLE IF NOT EXISTS core.runtime_services (
    name TEXT PRIMARY KEY,
    implementation TEXT NOT NULL UNIQUE
);

-- Table for CLI Commands, replacing cli_registry.yaml
CREATE TABLE IF NOT EXISTS core.cli_commands (
    name TEXT PRIMARY KEY,
    module TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    summary TEXT,
    category TEXT
);


-- =============================================================================
-- SECTION 4: GOVERNANCE & AUDIT TRAIL
-- =============================================================================

-- Evidence of constitutional change attempts
CREATE TABLE IF NOT EXISTS core.proposals (
  id               BIGSERIAL PRIMARY KEY,
  target_path      TEXT NOT NULL,
  content_sha256   CHAR(64) NOT NULL,
  justification    TEXT NOT NULL,
  risk_tier        TEXT CHECK (risk_tier IN ('low','medium','high')) DEFAULT 'low',
  is_critical      BOOLEAN NOT NULL DEFAULT FALSE,
  status           TEXT CHECK (status IN ('open','approved','rejected','superseded')) NOT NULL DEFAULT 'open',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS core.proposal_signatures (
  proposal_id       BIGINT NOT NULL REFERENCES core.proposals(id) ON DELETE CASCADE,
  approver_identity TEXT NOT NULL,
  signature_base64  TEXT NOT NULL,
  signed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_valid          BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (proposal_id, approver_identity)
);

-- Scores and pass/fail history over time
CREATE TABLE IF NOT EXISTS core.audit_runs (
  id         BIGSERIAL PRIMARY KEY,
  source     TEXT NOT NULL,           -- 'nightly' | 'pr' | 'manual'
  commit_sha CHAR(40),
  score      NUMERIC(4,3),
  passed     BOOLEAN NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);


-- =============================================================================
-- SECTION 5: VIEWS
-- =============================================================================

-- A stable, queryable interface to the system's knowledge graph.
CREATE OR REPLACE VIEW core.knowledge_graph AS
SELECT
    s.uuid,
    s.key AS capability, -- Alias 'key' to 'capability' for backward compatibility
    s.symbol_path,
    s.file_path AS file,
    s.title,
    s.description AS intent,
    s.owner,
    s.status,
    s.is_public,
    s.structural_hash,
    s.vector_id,
    s.updated_at AS last_updated,
    -- Placeholders to match the old schema for now.
    '[]'::jsonb AS tags,
    '[]'::jsonb AS calls,
    '[]'::jsonb AS parameters,
    '[]'::jsonb AS base_classes,
    (s.symbol_path LIKE '%__init__') AS is_class,
    (s.symbol_path LIKE '%Test%') AS is_test,
    0 AS line_number,
    0 AS end_line_number,
    NULL AS source_code,
    NULL AS docstring,
    NULL AS entry_point_type,
    NULL AS entry_point_justification,
    NULL AS parent_class_key,
    FALSE AS is_async
FROM
    core.symbols s;


-- =============================================================================
-- SECTION 6: INDEXES
-- =============================================================================

CREATE UNIQUE INDEX IF NOT EXISTS uq_symbols_key ON core.symbols (key) WHERE key IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_symbols_filepath ON core.symbols (file_path);
CREATE INDEX IF NOT EXISTS idx_symbols_is_public ON core.symbols (is_public);
CREATE INDEX IF NOT EXISTS idx_domains_key ON core.domains (key);
CREATE INDEX IF NOT EXISTS idx_symbols_domain_key ON core.symbols (domain_key);
CREATE INDEX IF NOT EXISTS idx_symbols_vector_gin ON core.symbols USING GIN (vector);
CREATE INDEX IF NOT EXISTS idx_symbol_capabilities_capability_key ON core.symbol_capabilities (capability_key);


-- =============================================================================
-- END OF CONSOLIDATED SCHEMA
-- =============================================================================