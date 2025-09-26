CREATE SCHEMA IF NOT EXISTS core;

-- proposals (evidence of constitutional change attempts)
CREATE TABLE IF NOT EXISTS core.proposals (
  id               BIGSERIAL PRIMARY KEY,
  target_path      TEXT NOT NULL,
  content_sha256   CHAR(64) NOT NULL,
  justification    TEXT NOT NULL,
  risk_tier        TEXT CHECK (risk_tier IN ('low','medium','high')) DEFAULT 'low',
  is_critical      BOOLEAN NOT NULL DEFAULT FALSE,
  status           TEXT CHECK (status IN ('open','approved','rejected','superseded')) NOT NULL DEFAULT 'open',
  created_at       TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by       TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS core.proposal_signatures (
  proposal_id       BIGINT NOT NULL REFERENCES core.proposals(id) ON DELETE CASCADE,
  approver_identity TEXT NOT NULL,
  signature_base64  TEXT NOT NULL,
  signed_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_valid          BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (proposal_id, approver_identity)
);

-- audit runs (scores + pass/fail over time)
CREATE TABLE IF NOT EXISTS core.audit_runs (
  id         BIGSERIAL PRIMARY KEY,
  source     TEXT NOT NULL,           -- 'nightly' | 'pr' | 'manual'
  commit_sha CHAR(40),
  score      NUMERIC(4,3),
  passed     BOOLEAN NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);
