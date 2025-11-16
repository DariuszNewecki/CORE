-- Context Packets Table
-- Stores metadata for ContextPackage artifacts
-- Migration: 2025-11-11_create_context_packets.sql

-- --- START OF FIX: Explicitly create table and indexes in the 'core' schema ---
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
-- --- END OF FIX ---

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
