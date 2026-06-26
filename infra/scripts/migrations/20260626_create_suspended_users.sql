-- Create core.suspended_users for DB-backed access suspension (ADR-124 D4).
-- Date: 2026-06-26
--
-- Replaces the in-process dict in body.services.auth.deny_list with a
-- DB-backed table so that suspensions survive core-api restarts. The table
-- is loaded into an in-process cache at startup (deny_list.initialize) and
-- kept in sync on suspend/reactivate operations in AuthService.set_active.
--
-- TTL (expires_at) matches the access token lifetime so that entries become
-- inert at the same moment the token would expire naturally. Rows can be
-- pruned periodically but are functionally harmless past expires_at.

BEGIN;

CREATE TABLE core.suspended_users (
    user_id      uuid PRIMARY KEY REFERENCES core.users(id) ON DELETE CASCADE,
    expires_at   timestamp with time zone NOT NULL,
    suspended_at timestamp with time zone NOT NULL DEFAULT now()
);

ALTER TABLE core.suspended_users OWNER TO core_db;

COMMENT ON TABLE core.suspended_users IS
    'Active account suspensions for immediate JWT invalidation (ADR-124 D4). '
    'Rows survive core-api restarts; loaded into the in-process deny-list cache '
    'at startup. expires_at matches the access token TTL — entries past that '
    'timestamp are inert and can be pruned.';

COMMIT;
