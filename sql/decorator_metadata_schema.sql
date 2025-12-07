-- =============================================================================
-- DECORATOR METADATA STORAGE
-- Extension to CORE v2.2 Schema
--
-- Purpose: Store decorator requirements in DB to enable autonomous code generation
-- Status: Future enhancement (Phase 3 of migration)
-- =============================================================================

-- =============================================================================
-- DECORATOR REGISTRY
-- Defines all valid decorators and their constitutional purpose
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.decorator_registry (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Identity
    decorator_name text NOT NULL UNIQUE,  -- e.g., "core_command", "atomic_action"
    full_syntax text NOT NULL,            -- e.g., "@core_command(...)"

    -- Classification
    category text NOT NULL CHECK (
        category IN ('governance_contract', 'framework_binding', 'type_hint')
    ),
    framework text,                        -- e.g., "typer", "fastapi", "pytest", NULL for CORE-native

    -- Constitutional purpose
    purpose text NOT NULL,
    required_for text[],                   -- Function types that need this decorator

    -- Parameters schema
    parameters jsonb DEFAULT '[]'::jsonb,  -- JSON schema for decorator parameters

    -- Metadata
    policy_reference text,                 -- Link to .intent/ policy that defines this
    is_active boolean DEFAULT true,

    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_decorator_registry_category ON core.decorator_registry(category);
CREATE INDEX IF NOT EXISTS idx_decorator_registry_active ON core.decorator_registry(is_active) WHERE is_active = true;

COMMENT ON TABLE core.decorator_registry IS
    'Registry of all constitutionally-approved decorators and their metadata';

-- =============================================================================
-- SYMBOL DECORATORS
-- Links symbols to their required decorators with parameters
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.symbol_decorators (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Relationships
    symbol_id uuid NOT NULL REFERENCES core.symbols(id) ON DELETE CASCADE,
    decorator_id uuid NOT NULL REFERENCES core.decorator_registry(id) ON DELETE CASCADE,

    -- Decorator application
    order_index integer NOT NULL,          -- Decorators are ordered (1 = outermost)
    parameters jsonb DEFAULT '{}'::jsonb,  -- Actual parameter values

    -- Metadata
    source text DEFAULT 'inferred' CHECK (
        source IN ('inferred', 'manual', 'constitutional', 'generated')
    ),
    reasoning text,                        -- WHY this decorator is needed

    -- Lifecycle
    is_active boolean DEFAULT true,        -- Allows disabling without deletion
    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL,

    -- Constraints
    UNIQUE(symbol_id, decorator_id, order_index)
);

CREATE INDEX IF NOT EXISTS idx_symbol_decorators_symbol ON core.symbol_decorators(symbol_id);
CREATE INDEX IF NOT EXISTS idx_symbol_decorators_decorator ON core.symbol_decorators(decorator_id);
CREATE INDEX IF NOT EXISTS idx_symbol_decorators_active ON core.symbol_decorators(is_active) WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_symbol_decorators_order ON core.symbol_decorators(symbol_id, order_index);

COMMENT ON TABLE core.symbol_decorators IS
    'Links symbols to their required decorators with parameters and ordering';

COMMENT ON COLUMN core.symbol_decorators.order_index IS
    'Decorator application order: 1 = outermost (applied first), higher = inner';

-- =============================================================================
-- DECORATOR INFERENCE RULES
-- Teach CORE how to automatically determine required decorators
-- =============================================================================

CREATE TABLE IF NOT EXISTS core.decorator_inference_rules (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),

    -- Rule identity
    rule_name text NOT NULL UNIQUE,
    priority integer NOT NULL DEFAULT 100, -- Lower = higher priority

    -- Matching conditions (all must be true)
    conditions jsonb NOT NULL,             -- JSON conditions for when to apply
    -- Example: {"module_contains": "body/cli", "has_decorator": "@app.command"}

    -- Action to take
    decorator_id uuid NOT NULL REFERENCES core.decorator_registry(id),
    default_parameters jsonb DEFAULT '{}'::jsonb,

    -- Parameter computation
    parameter_inference jsonb,             -- Rules for computing parameter values
    -- Example: {"dangerous": {"ast_check": "has_write_operations", "default": false}}

    -- Metadata
    reasoning text NOT NULL,
    policy_reference text,
    is_active boolean DEFAULT true,

    created_at timestamptz DEFAULT now() NOT NULL,
    updated_at timestamptz DEFAULT now() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_inference_rules_priority ON core.decorator_inference_rules(priority)
    WHERE is_active = true;
CREATE INDEX IF NOT EXISTS idx_inference_rules_decorator ON core.decorator_inference_rules(decorator_id);

COMMENT ON TABLE core.decorator_inference_rules IS
    'Rules for automatically inferring which decorators a symbol needs';

COMMENT ON COLUMN core.decorator_inference_rules.conditions IS
    'JSON object with conditions: module_contains, has_decorator, name_pattern, ast_features, etc.';

COMMENT ON COLUMN core.decorator_inference_rules.parameter_inference IS
    'JSON rules for computing parameter values from symbol analysis';

-- =============================================================================
-- VIEWS FOR COMMON QUERIES
-- =============================================================================

-- Get all decorators for a symbol in correct order
CREATE OR REPLACE VIEW core.v_symbol_decorator_stack AS
SELECT
    s.id AS symbol_id,
    s.symbol_path,
    s.module,
    s.qualname,
    json_agg(
        json_build_object(
            'decorator', dr.decorator_name,
            'syntax', dr.full_syntax,
            'parameters', sd.parameters,
            'order', sd.order_index,
            'category', dr.category,
            'reasoning', sd.reasoning
        ) ORDER BY sd.order_index
    ) AS decorator_stack
FROM core.symbols s
LEFT JOIN core.symbol_decorators sd ON sd.symbol_id = s.id AND sd.is_active = true
LEFT JOIN core.decorator_registry dr ON dr.id = sd.decorator_id AND dr.is_active = true
GROUP BY s.id, s.symbol_path, s.module, s.qualname;

COMMENT ON VIEW core.v_symbol_decorator_stack IS
    'Complete decorator stack for each symbol in application order';

-- Symbols missing required decorators
CREATE OR REPLACE VIEW core.v_symbols_missing_decorators AS
SELECT
    s.id AS symbol_id,
    s.symbol_path,
    s.module,
    s.kind,
    dir.rule_name,
    dr.decorator_name AS missing_decorator,
    dir.reasoning
FROM core.symbols s
CROSS JOIN core.decorator_inference_rules dir
JOIN core.decorator_registry dr ON dr.id = dir.decorator_id
WHERE dir.is_active = true
  AND dr.is_active = true
  AND s.state != 'deprecated'
  -- Check if conditions match
  AND (
    -- Example condition checks (would need actual JSONB path queries)
    (dir.conditions->>'module_contains' IS NULL OR s.module LIKE '%' || (dir.conditions->>'module_contains') || '%')
  )
  -- Symbol doesn't have this decorator
  AND NOT EXISTS (
    SELECT 1
    FROM core.symbol_decorators sd
    WHERE sd.symbol_id = s.id
      AND sd.decorator_id = dir.decorator_id
      AND sd.is_active = true
  )
ORDER BY s.module, s.symbol_path;

COMMENT ON VIEW core.v_symbols_missing_decorators IS
    'Symbols that should have decorators based on inference rules but do not';

-- =============================================================================
-- HELPER FUNCTIONS
-- =============================================================================

-- Get decorator stack as Python code
CREATE OR REPLACE FUNCTION core.generate_decorator_code(p_symbol_id uuid)
RETURNS text AS $$
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
$$ LANGUAGE plpgsql STABLE;

COMMENT ON FUNCTION core.generate_decorator_code IS
    'Generate Python decorator code for a symbol. Usage: SELECT core.generate_decorator_code(symbol_id);';

-- =============================================================================
-- SEED DATA
-- =============================================================================

-- Insert core decorators
INSERT INTO core.decorator_registry (decorator_name, full_syntax, category, framework, purpose, required_for, parameters, policy_reference)
VALUES
    (
        'core_command',
        '@core_command(dangerous=bool)',
        'governance_contract',
        NULL,
        'Constitutional wrapper for CLI entry points - enables governance validation before execution',
        ARRAY['cli_command'],
        '[{"name": "dangerous", "type": "bool", "required": true, "description": "Whether command performs destructive operations"}]'::jsonb,
        '.intent/charter/policies/decorator_governance.yaml'
    ),
    (
        'atomic_action',
        '@atomic_action(action_id=str, impact=str, policies=list)',
        'governance_contract',
        NULL,
        'Constitutional wrapper for autonomous operations - defines blast radius and policies',
        ARRAY['service_method', 'action_handler'],
        '[
            {"name": "action_id", "type": "str", "required": true, "pattern": "^[a-z]+\\.[a-z_]+$"},
            {"name": "impact", "type": "str", "required": true, "enum": ["read-only", "write-metadata", "write-code", "write-data"]},
            {"name": "policies", "type": "list", "required": true, "description": "Constitutional policies validated by this action"}
        ]'::jsonb,
        '.intent/charter/patterns/atomic_actions.yaml'
    ),
    (
        'app.command',
        '@app.command(name=str)',
        'framework_binding',
        'typer',
        'Register CLI command with Typer framework',
        ARRAY['cli_command'],
        '[{"name": "name", "type": "str", "required": false}]'::jsonb,
        NULL
    ),
    (
        'dataclass',
        '@dataclass',
        'type_hint',
        'python',
        'Generate dataclass methods (__init__, __repr__, etc.)',
        ARRAY['data_class'],
        '[]'::jsonb,
        NULL
    )
ON CONFLICT (decorator_name) DO NOTHING;

-- Insert inference rule: CLI commands need @core_command
INSERT INTO core.decorator_inference_rules (rule_name, priority, conditions, decorator_id, default_parameters, parameter_inference, reasoning, policy_reference)
SELECT
    'cli_commands_require_core_command',
    10,
    '{"module_contains": "body/cli", "or": [{"has_decorator": "@app.command"}, {"name_pattern": "^(run_|execute_|list_|show_|query_)"}]}'::jsonb,
    id,
    '{"dangerous": false}'::jsonb,
    '{"dangerous": {"ast_check": "has_write_operations", "default": false}}'::jsonb,
    'All CLI command functions require @core_command for constitutional governance',
    '.intent/charter/policies/decorator_governance.yaml'
FROM core.decorator_registry
WHERE decorator_name = 'core_command'
ON CONFLICT (rule_name) DO NOTHING;

-- =============================================================================
-- TRIGGERS
-- =============================================================================

-- Auto-update timestamps
CREATE TRIGGER trg_decorator_registry_updated_at
    BEFORE UPDATE ON core.decorator_registry
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

CREATE TRIGGER trg_symbol_decorators_updated_at
    BEFORE UPDATE ON core.symbol_decorators
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

CREATE TRIGGER trg_decorator_inference_rules_updated_at
    BEFORE UPDATE ON core.decorator_inference_rules
    FOR EACH ROW EXECUTE FUNCTION core.set_updated_at();

-- =============================================================================
-- PERMISSIONS
-- =============================================================================

GRANT ALL PRIVILEGES ON TABLE core.decorator_registry TO core_db;
GRANT ALL PRIVILEGES ON TABLE core.symbol_decorators TO core_db;
GRANT ALL PRIVILEGES ON TABLE core.decorator_inference_rules TO core_db;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA core TO core_db;

-- =============================================================================
-- MIGRATION NOTES
-- =============================================================================

COMMENT ON SCHEMA core IS $COMMENT$
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
- "Last programmer you'll ever need"

USAGE EXAMPLES:

-- Check which symbols need decorators:
SELECT * FROM core.v_symbols_missing_decorators;

-- Get decorator stack for a symbol:
SELECT * FROM core.v_symbol_decorator_stack WHERE symbol_path = 'body.cli.check:audit';

-- Generate decorator code:
SELECT core.generate_decorator_code('symbol-uuid-here');

-- Add decorator manually:
INSERT INTO core.symbol_decorators (symbol_id, decorator_id, order_index, parameters, source, reasoning)
SELECT
    s.id,
    dr.id,
    1,
    '{"dangerous": false}'::jsonb,
    'manual',
    'CLI command requires constitutional governance'
FROM core.symbols s, core.decorator_registry dr
WHERE s.symbol_path = 'body.cli.check:audit'
  AND dr.decorator_name = 'core_command';
$COMMENT$;
