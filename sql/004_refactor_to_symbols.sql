-- FILE: sql/004_refactor_to_symbols.sql

-- Step 1: Create a temporary mapping table to hold the old implementation data.
-- This block is wrapped in a DO statement to execute conditionally, making the script safe to re-run.
DO $$
BEGIN
   IF EXISTS (SELECT FROM pg_tables WHERE schemaname = 'core' AND tablename  = 'implementations') THEN
      -- Create the temp table only if the source table exists
      CREATE TABLE core.implementations_temp AS TABLE core.implementations;
   END IF;
END $$;

-- Step 2: Explicitly drop the dependent objects first.
DROP TABLE IF EXISTS core.capability_domains;
DROP VIEW IF EXISTS core.knowledge_graph;
DROP VIEW IF EXISTS core.capabilities_view;

-- Step 3: Now it is safe to drop the old tables.
DROP TABLE IF EXISTS core.implementations;
DROP TABLE IF EXISTS core.capabilities;
DROP TABLE IF EXISTS core.domains;

-- Step 4: Create the new, universal symbols table.
CREATE TABLE core.symbols (
    uuid            TEXT PRIMARY KEY,
    symbol_path     TEXT NOT NULL UNIQUE,
    file_path       TEXT NOT NULL,
    is_public       BOOLEAN NOT NULL DEFAULT FALSE,
    title           TEXT,
    description     TEXT,
    owner           TEXT NOT NULL DEFAULT 'unassigned_agent',
    status          TEXT NOT NULL DEFAULT 'active',
    structural_hash CHAR(64),
    vector_id       TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- Add indexes for performance
CREATE INDEX idx_symbols_filepath ON core.symbols (file_path);
CREATE INDEX idx_symbols_is_public ON core.symbols (is_public);

-- NOTE: Data migration from the temp table will be handled by the new 'knowledge sync' command.