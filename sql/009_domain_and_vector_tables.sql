-- Migration to make the database the single source of truth for domains.
-- This aligns with the 'single_source_of_truth' and 'evolvable_structure' principles.

-- Step 1: Create the new 'domains' table.
-- This table will store the canonical list of all architectural domains.
CREATE TABLE IF NOT EXISTS core.domains (
    key          TEXT PRIMARY KEY,
    title        TEXT NOT NULL,
    description  TEXT,
    created_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_domains_key ON core.domains (key);


-- Step 2: Add a 'domain' column to the 'symbols' table.
-- This creates the formal link between a piece of code (a symbol) and its
-- architectural domain. It is nullable to support symbols that are not
-- yet classified.
ALTER TABLE core.symbols
ADD COLUMN domain_key TEXT REFERENCES core.domains(key) ON DELETE SET NULL;
CREATE INDEX IF NOT EXISTS idx_symbols_domain_key ON core.symbols (domain_key);


-- Step 3: Add a 'vector' column to the 'symbols' table.
-- This makes the database the single source of truth for embeddings, directly
-- associating a vector with the symbol it represents. We use JSONB for
-- portability instead of a vendor-specific VECTOR type.
ALTER TABLE core.symbols
ADD COLUMN vector JSONB;
CREATE INDEX IF NOT EXISTS idx_symbols_vector_gin ON core.symbols USING GIN (vector);


-- Step 4: Create a junction table for many-to-many relationships between symbols and capabilities.
-- This is a forward-looking change to support future scenarios where a single
-- function might implement multiple, distinct capabilities.
CREATE TABLE IF NOT EXISTS core.symbol_capabilities (
    symbol_uuid TEXT NOT NULL REFERENCES core.symbols(uuid) ON DELETE CASCADE,
    capability_key TEXT NOT NULL, -- This will be validated by the application layer
    PRIMARY KEY (symbol_uuid, capability_key)
);
CREATE INDEX IF NOT EXISTS idx_symbol_capabilities_capability_key ON core.symbol_capabilities (capability_key);
