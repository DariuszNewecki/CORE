-- FILE: sql/007_capabilities_registry.sql
CREATE TABLE IF NOT EXISTS core.capabilities (
  id TEXT PRIMARY KEY,          -- The canonical key, e.g., 'introspection.vectorize'
  title TEXT NOT NULL,
  owner TEXT NOT NULL,
  implementing_files JSONB,     -- A JSON array of file paths like ["src/features/introspection/service.py"]
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);