-- 20260602_reassign_core_schema_owner_to_core_db.sql
--
-- Closes #536. The `core` schema currently has split ownership:
-- 28 objects (12 views, 10 functions, 3 domains, 3 enums) owned by
-- lira_user; 76 objects (tables, sequences, the schema itself, one
-- view) owned by core_db. The lira_user-owned objects are the type-
-- system foundations and helper functions created during early
-- bootstrap under the host Linux account; they never got transferred
-- to the canonical service role.
--
-- This migration reassigns every lira_user-owned object IN THE core
-- SCHEMA to core_db. The public schema (PostgreSQL extension defaults,
-- ~200 lira_user-owned objects) is intentionally untouched — those
-- aren't part of the install story.
--
-- MUST be run as a superuser (postgres, or lira_user). The core_db
-- service role lacks REASSIGN/ALTER OWNER privilege on lira_user-owned
-- objects.
--
-- Idempotent: re-running after success is a no-op (each loop iterates
-- zero rows). Re-running after partial failure resumes correctly.
--
-- See ADR-086 (Installation Architecture) and #536.

BEGIN;

-- Relations: tables, views, materialized views, sequences.
-- ALTER ... OWNER TO automatically propagates to the relation's
-- implicit row type and any array type derived from it; indexes
-- inherit ownership from their table.
DO $$
DECLARE
    obj record;
BEGIN
    FOR obj IN
        SELECT c.relname, c.relkind
        FROM pg_class c
        JOIN pg_namespace n ON c.relnamespace = n.oid
        WHERE n.nspname = 'core'
          AND c.relowner = 'lira_user'::regrole
          AND c.relkind IN ('r', 'v', 'm', 'S')
        ORDER BY c.relkind, c.relname
    LOOP
        EXECUTE format(
            'ALTER %s core.%I OWNER TO core_db',
            CASE obj.relkind
                WHEN 'r' THEN 'TABLE'
                WHEN 'v' THEN 'VIEW'
                WHEN 'm' THEN 'MATERIALIZED VIEW'
                WHEN 'S' THEN 'SEQUENCE'
            END,
            obj.relname
        );
    END LOOP;
END
$$;

-- Functions: ALTER FUNCTION needs the full signature, hence
-- oid::regprocedure (renders as `core.fn(arg_types)`).
DO $$
DECLARE
    fn record;
BEGIN
    FOR fn IN
        SELECT p.oid::regprocedure::text AS sig
        FROM pg_proc p
        JOIN pg_namespace n ON p.pronamespace = n.oid
        WHERE n.nspname = 'core'
          AND p.proowner = 'lira_user'::regrole
        ORDER BY sig
    LOOP
        EXECUTE format('ALTER FUNCTION %s OWNER TO core_db', fn.sig);
    END LOOP;
END
$$;

-- Domains and enums. Filter to typtype IN ('d','e') so we skip the
-- auto-generated array companion types (typtype='b' with typelem set),
-- which follow their parent's ownership automatically.
DO $$
DECLARE
    rec record;
BEGIN
    FOR rec IN
        SELECT typ.typname, typ.typtype
        FROM pg_type typ
        JOIN pg_namespace n ON typ.typnamespace = n.oid
        WHERE n.nspname = 'core'
          AND typ.typowner = 'lira_user'::regrole
          AND typ.typtype IN ('d', 'e')
        ORDER BY typ.typtype, typ.typname
    LOOP
        IF rec.typtype = 'd' THEN
            EXECUTE format('ALTER DOMAIN core.%I OWNER TO core_db', rec.typname);
        ELSE
            EXECUTE format('ALTER TYPE core.%I OWNER TO core_db', rec.typname);
        END IF;
    END LOOP;
END
$$;

-- Verification: zero core-schema objects remain under lira_user.
-- Fail the transaction loudly if anything was missed.
DO $$
DECLARE
    leftover_relations int;
    leftover_functions int;
    leftover_types int;
    total int;
BEGIN
    SELECT count(*) INTO leftover_relations
    FROM pg_class c
    JOIN pg_namespace n ON c.relnamespace = n.oid
    WHERE n.nspname = 'core'
      AND c.relowner = 'lira_user'::regrole
      AND c.relkind IN ('r', 'v', 'm', 'S');

    SELECT count(*) INTO leftover_functions
    FROM pg_proc p
    JOIN pg_namespace n ON p.pronamespace = n.oid
    WHERE n.nspname = 'core'
      AND p.proowner = 'lira_user'::regrole;

    SELECT count(*) INTO leftover_types
    FROM pg_type t
    JOIN pg_namespace n ON t.typnamespace = n.oid
    WHERE n.nspname = 'core'
      AND t.typowner = 'lira_user'::regrole
      AND t.typtype IN ('d', 'e');

    total := leftover_relations + leftover_functions + leftover_types;

    IF total > 0 THEN
        RAISE EXCEPTION
            'Schema-owner cleanup incomplete in core schema: % relations, % functions, % types still under lira_user',
            leftover_relations, leftover_functions, leftover_types;
    END IF;

    RAISE NOTICE 'core schema ownership: all objects now owned by core_db';
END
$$;

COMMIT;
