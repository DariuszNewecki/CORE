-- FILE: sql/008_operational_tables.sql
--
-- CONSTITUTIONAL AMENDMENT: Make the database the Single Source of Truth for operational knowledge.
--
-- Justification: This migration creates tables to house runtime operational knowledge
-- that was previously stored in difficult-to-manage YAML files. This serves the
-- 'single_source_of_truth' principle by centralizing configuration, making it
-- transactionally safe, and queryable by all system components.

-- Table for LLM Resources, replacing resource_manifest_policy.yaml
CREATE TABLE IF NOT EXISTS core.llm_resources (
    name TEXT PRIMARY KEY,
    provided_capabilities JSONB NOT NULL DEFAULT '[]'::jsonb,
    env_prefix TEXT NOT NULL UNIQUE,
    performance_metadata JSONB
);

-- Table for Cognitive Roles, replacing cognitive_roles_policy.yaml
CREATE TABLE IF NOT EXISTS core.cognitive_roles (
    "role" TEXT PRIMARY KEY,
    description TEXT,
    assigned_resource TEXT REFERENCES core.llm_resources(name),
    required_capabilities JSONB NOT NULL DEFAULT '[]'::jsonb
);

-- Table for Runtime Services, replacing runtime_services.yaml
CREATE TABLE IF NOT EXISTS core.runtime_services (
    name TEXT PRIMARY KEY,
    implementation TEXT NOT NULL UNIQUE
);

-- Table for CLI Commands, replacing cli_registry_policy.yaml
CREATE TABLE IF NOT EXISTS core.cli_commands (
    name TEXT PRIMARY KEY,
    module TEXT NOT NULL,
    entrypoint TEXT NOT NULL,
    summary TEXT,
    category TEXT
);