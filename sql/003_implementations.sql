--- START OF FILE sql/003_implementations.sql ---
-- FILE: sql/003_implementations.sql

CREATE TABLE IF NOT EXISTS core.implementations (
  capability_key TEXT NOT NULL REFERENCES core.capabilities(key) ON DELETE CASCADE,
  file_path TEXT NOT NULL,
  symbol_path TEXT NOT NULL,
  structural_hash CHAR(64) NOT NULL,
  PRIMARY KEY (capability_key, file_path, symbol_path)
);
--- END OF FILE sql/003_implementations.sql ---