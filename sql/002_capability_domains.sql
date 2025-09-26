-- FILE: sql/002_capability_domains.sql

-- 1) Capabilities can be multi-domain via a junction; keep the column
--    but make it nullable for backward-compat/exports.
ALTER TABLE core.capabilities
  ALTER COLUMN domain DROP NOT NULL;

-- 2) Junction table for capability <-> domain
CREATE TABLE IF NOT EXISTS core.capability_domains (
  capability_key TEXT NOT NULL
    REFERENCES core.capabilities(key) ON DELETE CASCADE,
  domain_key TEXT NOT NULL
    REFERENCES core.domains(key) ON DELETE RESTRICT,
  is_primary BOOLEAN NOT NULL DEFAULT FALSE,
  PRIMARY KEY (capability_key, domain_key)
);

-- 3) At most one primary domain per capability (optional but helpful).
CREATE UNIQUE INDEX IF NOT EXISTS uq_capability_primary_domain
  ON core.capability_domains (capability_key)
  WHERE is_primary = TRUE;

-- 4) Seed the junction from the legacy single-column if present.
INSERT INTO core.capability_domains (capability_key, domain_key, is_primary)
SELECT c.key, c.domain, TRUE
FROM core.capabilities c
JOIN core.domains d ON d.key = c.domain
WHERE c.domain IS NOT NULL
ON CONFLICT DO NOTHING;
