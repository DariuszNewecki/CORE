# CORE Database Governance & Usage Guide
*Living reference for implementing governed database usage in CORE*

---

## 1. Purpose and North Star

CORE uses a database **only** to store evidence, operational telemetry, and indexes.
It **never** stores constitutional authority (policies, approvers, schemas remain in `.intent/` and Git).

Key roles of the DB:
- Evidence & provenance for audits, proposals, and actions.
- Operational telemetry (plans, steps, run logs) to support self-healing and analytics.
- Indexes pointing to external stores (e.g. Qdrant vector IDs).

This supports the constitutional principles:
- **clarity_first** – single source of truth for runtime evidence.
- **safe_by_default** – recoverable, reversible changes.
- **evolvable_structure** – schema can grow under governance.

---

## 2. Mind-Level Governance

### 2.1 Required .intent Additions
Create and maintain:

**`.intent/policies/database_policy.yaml`**
- Declares supported engine (PostgreSQL) and core schema (`core`).
- Defines retention & backup rules.
- Enforces: no secrets, domain validity, vector index consistency.
- References migration directory `sql/`.

**`.intent/schemas/database_policy.schema.json`**
- Validates the policy: engine enum, required sections, retention windows.

Update **critical_paths** in `.intent/constitution/approvers.yaml` if you want DB policy changes to require critical quorum.

### 2.2 Link to Audit System
The existing audit item `audit.database_schema_declared` already references a database policy.  
Completing this policy closes that governance loop.

---

## 3. Minimal v0 Database Schema

Store this as `sql/001_init.sql`.  
It covers proposals & approvals, audits, capabilities, vector indexes, action logs, and agent plans.

```sql
CREATE SCHEMA IF NOT EXISTS core;

-- 1) Constitutional proposals & approvals (evidence only)
CREATE TABLE core.proposals (
  id BIGSERIAL PRIMARY KEY,
  target_path TEXT NOT NULL,
  content_sha256 CHAR(64) NOT NULL,
  justification TEXT NOT NULL,
  risk_tier TEXT CHECK (risk_tier IN ('low','medium','high')) DEFAULT 'low',
  is_critical BOOLEAN NOT NULL DEFAULT FALSE,
  status TEXT CHECK (status IN ('open','approved','rejected','superseded')) NOT NULL DEFAULT 'open',
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  created_by TEXT NOT NULL
);

CREATE TABLE core.proposal_signatures (
  proposal_id BIGINT REFERENCES core.proposals(id) ON DELETE CASCADE,
  approver_identity TEXT NOT NULL,
  signature_base64 TEXT NOT NULL,
  signed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  is_valid BOOLEAN NOT NULL DEFAULT TRUE,
  PRIMARY KEY (proposal_id, approver_identity)
);

-- 2) Audits & violations
CREATE TABLE core.audit_runs (
  id BIGSERIAL PRIMARY KEY,
  source TEXT NOT NULL,
  commit_sha CHAR(40),
  score NUMERIC(4,3),
  risk_tier TEXT,
  passed BOOLEAN NOT NULL,
  started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  finished_at TIMESTAMPTZ
);

CREATE TABLE core.audit_violations (
  id BIGSERIAL PRIMARY KEY,
  audit_id BIGINT REFERENCES core.audit_runs(id) ON DELETE CASCADE,
  check_id TEXT NOT NULL,
  severity TEXT CHECK (severity IN ('info','warn','block')) NOT NULL,
  path TEXT,
  message TEXT NOT NULL,
  evidence JSONB
);

-- 3) Capabilities & implementations mirror
CREATE TABLE core.capabilities (
  key TEXT PRIMARY KEY,
  title TEXT NOT NULL,
  domain TEXT NOT NULL,
  owner TEXT NOT NULL,
  status TEXT CHECK (status IN ('active','deprecated')) NOT NULL DEFAULT 'active',
  last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE core.implementations (
  capability_key TEXT REFERENCES core.capabilities(key) ON DELETE CASCADE,
  file_path TEXT NOT NULL,
  symbol_path TEXT NOT NULL,
  structural_hash CHAR(64) NOT NULL,
  PRIMARY KEY (capability_key, file_path, symbol_path)
);

-- 4) Vector index mapping (Qdrant remains SoT)
CREATE TABLE core.vector_index (
  symbol_path TEXT PRIMARY KEY,
  collection_name TEXT NOT NULL,
  point_id TEXT NOT NULL,
  embed_revision TEXT NOT NULL,
  dim INT NOT NULL,
  updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 5) Action log
CREATE TABLE core.action_log (
  id BIGSERIAL PRIMARY KEY,
  actor TEXT NOT NULL,
  intent TEXT,
  command TEXT,
  result TEXT,
  metadata JSONB,
  occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- 6) Plans & steps (multi-agent transparency)
CREATE TABLE core.plans (
  id BIGSERIAL PRIMARY KEY,
  goal TEXT NOT NULL,
  created_by TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status TEXT CHECK (status IN ('open','executing','completed','aborted')) NOT NULL DEFAULT 'open'
);

CREATE TABLE core.plan_steps (
  id BIGSERIAL PRIMARY KEY,
  plan_id BIGINT REFERENCES core.plans(id) ON DELETE CASCADE,
  order_index INT NOT NULL,
  description TEXT NOT NULL,
  capability_key TEXT,
  status TEXT CHECK (status IN ('pending','running','done','failed')) NOT NULL DEFAULT 'pending',
  evidence JSONB
);
Rules

Never store private keys (keep them in .intent/keys/).

Validate domain against .intent/knowledge/domains.yaml.

Ensure vector_index.embed_revision matches EMBED_MODEL_REVISION and dim matches LOCAL_EMBEDDING_DIM.

4. Migration & Drift Control
Store all migrations as plain SQL in sql/ (001_init.sql, 002_add_x.sql, …).

Reference each migration in .intent/policies/database_policy.yaml.

Add a CI job db-validate to:

Spin up a temporary Postgres instance.

Apply all migrations.

Compare live schema against declared policy.

Fail on drift (warn in dev, block in production).

Rollback requirements:

Every migration must either declare a reverse path or explicitly mark itself irreversible and require critical quorum.

## 5. Runtime Integration
Create a minimal DB layer under src/core/db/:

engine.py – async SQLAlchemy engine + session factory.

models.py – optional Pydantic/data classes.

queries.py – focused query functions.

Example engine.py:

python
Copy code
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
import os

engine = create_async_engine(os.getenv("DATABASE_URL"), pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False)
Keep all business logic in governed capabilities, not inside queries.

6. Emergency Drills (Governance Hardening)
Schedule quarterly drills to prove resilience:

Compromised Key: run a mock revocation proposal and verify quorum recalculation.

Critical Policy Breach: push a test PR violating DB policy and confirm CI blocks it.

Disaster Recovery: rebuild the database schema from Git and confirm all audits pass.

7. Rollout Roadmap
Step	Goal	Owner
Mind First	Commit database_policy.yaml + schema JSON + 001_init.sql	IT/CORE maintainer
CI Second	Add db-validate job with ephemeral Postgres	DevOps
Write Paths	Wire audits, action logs, and vectorizer to DB tables	Core dev team
Vector Index	Sync Qdrant point IDs to core.vector_index	Knowledge/embedding team
Plans & Steps	Persist planner/executor steps	Agents team

8. Benefits at a Glance
Unified, queryable evidence store for every plan, action, and audit.

Strong constitutional guardrails around schema evolution.

Transparent, recoverable history supporting CORE’s self-healing and self-evolving mission.

This document is the canonical reference for all database-related work in CORE.
Keep it updated as the schema, policies, and governance practices evolve.