-- Migration 002: Add table for runtime configuration
CREATE TABLE IF NOT EXISTS core.runtime_settings (
    key TEXT PRIMARY KEY,
    value TEXT,
    description TEXT,
    is_secret BOOLEAN NOT NULL DEFAULT FALSE,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

COMMENT ON TABLE core.runtime_settings IS 'Single source of truth for runtime configuration, loaded from .env and managed by `core-admin manage dotenv sync`.';
COMMENT ON COLUMN core.runtime_settings.is_secret IS 'If true, the value should be handled with care.';
