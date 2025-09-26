-- FILE: sql/006_knowledge_graph_view.sql
--
-- CONSTITUTIONAL AMENDMENT: Create a database view to act as a stable,
-- queryable interface to the system's knowledge graph.
--
-- Justification: This view provides a drop-in replacement for the legacy
-- knowledge_graph.json file, serving the 'evolvable_structure' and 'clarity_first'
-- principles by abstracting the underlying table structure from consumers
-- like the ConstitutionalAuditor.

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
    -- NOTE: These fields are placeholders to match the old schema for now.
    '[]'::jsonb AS tags,
    '[]'::jsonb AS calls,
    '[]'::jsonb AS parameters,
    '[]'::jsonb AS base_classes,
    (s.symbol_path LIKE '%__init__') AS is_class,
    (s.symbol_path LIKE '%Test%') AS is_test,
    -- --- THIS IS THE FIX ---
    -- Add the missing columns that downstream tools rely on.
    -- For now, we use placeholders or simple derivations.
    0 AS line_number, -- Placeholder
    0 AS end_line_number, -- Placeholder
    NULL AS source_code, -- Placeholder
    NULL AS docstring, -- Placeholder
    NULL AS entry_point_type, -- Placeholder
    NULL AS entry_point_justification, -- Placeholder
    NULL AS parent_class_key, -- Placeholder
    FALSE AS is_async -- Placeholder
    -- --- END OF FIX ---
FROM
    core.symbols s;