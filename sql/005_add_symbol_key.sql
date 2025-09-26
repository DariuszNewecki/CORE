-- FILE: sql/005_add_symbol_key.sql
--
-- CONSTITUTIONAL AMENDMENT: Add a canonical, human-readable key to the symbols table.
--
-- Justification: This amendment forges the missing link between the human-readable
-- capabilities declared in .intent/mind/project_manifest.yaml and their concrete
-- implementations tracked in the database. It is a critical step to making the
-- ConstitutionalAuditor's 'check_capability_coverage' function correctly and
-- serves the 'clarity_first' principle.

-- Step 1: Add the new 'key' column. It is nullable for now to allow a phased data migration.
ALTER TABLE core.symbols
ADD COLUMN key TEXT;

-- Step 2: Create a unique index to ensure that each human-readable key can only
-- be assigned to one symbol, enforcing the single_source_of_truth principle.
-- The index is created on non-null values only.
CREATE UNIQUE INDEX IF NOT EXISTS uq_symbols_key
ON core.symbols (key)
WHERE key IS NOT NULL;