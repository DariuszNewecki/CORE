-- FILE: sql/003_capability_domains_idx.sql

-- Helpful indexes for common lookups
CREATE INDEX IF NOT EXISTS idx_capability_domains_domain
  ON core.capability_domains(domain_key);

CREATE INDEX IF NOT EXISTS idx_capability_domains_cap_primary
  ON core.capability_domains(capability_key)
  WHERE is_primary = TRUE;
