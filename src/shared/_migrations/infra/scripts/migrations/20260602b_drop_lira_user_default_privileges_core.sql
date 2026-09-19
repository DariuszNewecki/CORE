-- 20260602b_drop_lira_user_default_privileges_core.sql
--
-- Follow-up to 20260602_reassign_core_schema_owner_to_core_db.sql.
--
-- After the ownership flip, four ALTER DEFAULT PRIVILEGES rules
-- still reference lira_user in pg_default_acl:
--
--   ALTER DEFAULT PRIVILEGES FOR ROLE lira_user IN SCHEMA core
--     GRANT ALL ON SEQUENCES TO core_db
--   ALTER DEFAULT PRIVILEGES FOR ROLE lira_user IN SCHEMA core
--     GRANT ALL ON TYPES TO core_db
--   ALTER DEFAULT PRIVILEGES FOR ROLE lira_user IN SCHEMA core
--     GRANT ALL ON FUNCTIONS TO core_db
--   ALTER DEFAULT PRIVILEGES FOR ROLE lira_user IN SCHEMA core
--     GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO core_db
--
-- These were set up by lira_user during bootstrap: "when I (lira_user)
-- create new objects in core schema, auto-grant them to core_db." With
-- core_db as the canonical owner, lira_user won't be creating new
-- objects in core, so these rules are dormant. But they still appear
-- in pg_dump output and break restore on a fresh host that doesn't
-- have a lira_user role.
--
-- This migration revokes those four grants, leaving pg_default_acl
-- with zero lira_user entries in core schema. After it runs,
-- `grep lira_user infra/sql/db_schema_live.sql` returns nothing.
--
-- MUST be run as a superuser (postgres or lira_user). Only superusers
-- can ALTER DEFAULT PRIVILEGES for another role.
--
-- Idempotent: REVOKE on a non-existent grant is a no-op.
--
-- See ADR-086 (Installation Architecture) and #536.

BEGIN;

ALTER DEFAULT PRIVILEGES FOR ROLE lira_user IN SCHEMA core REVOKE ALL ON SEQUENCES FROM core_db;
ALTER DEFAULT PRIVILEGES FOR ROLE lira_user IN SCHEMA core REVOKE ALL ON TYPES FROM core_db;
ALTER DEFAULT PRIVILEGES FOR ROLE lira_user IN SCHEMA core REVOKE ALL ON FUNCTIONS FROM core_db;
ALTER DEFAULT PRIVILEGES FOR ROLE lira_user IN SCHEMA core REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM core_db;

-- Verification: zero lira_user entries should remain in
-- pg_default_acl for the core schema.
DO $$
DECLARE
    leftover int;
BEGIN
    SELECT count(*) INTO leftover
    FROM pg_default_acl d
    JOIN pg_namespace n ON d.defaclnamespace = n.oid
    WHERE n.nspname = 'core'
      AND d.defaclrole = 'lira_user'::regrole;

    IF leftover > 0 THEN
        RAISE EXCEPTION
            'pg_default_acl still has % lira_user entries for core schema after revoke',
            leftover;
    END IF;

    RAISE NOTICE 'pg_default_acl: zero lira_user entries remain in core schema';
END
$$;

COMMIT;
