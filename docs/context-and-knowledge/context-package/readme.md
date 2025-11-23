# ContextPackage Service

Constitutional governance for all LLM context in CORE.

## Overview

The ContextPackage system enforces Mind-layer policies on all input to LLM executions:

- **Schema Validation**: All packets must conform to `.intent/context/schema.yaml`
- **Privacy Enforcement**: Redacts secrets, PII, forbidden paths per `.intent/context/policy.yaml`
- **Token Budgets**: Prevents context overflow via `max_tokens` constraints
- **Audit Trail**: Every packet logged to `context_packets` table with provenance

## Architecture

```
.intent/context/          ← Mind (governance)
  schema.yaml             ← Structure definition
  policy.yaml             ← Privacy/redaction rules

src/services/context/     ← Body (execution)
  builder.py              ← Assembles packets
  validator.py            ← Enforces schema
  redactor.py             ← Applies privacy policies
  serializers.py          ← YAML I/O, hashing
  cache.py                ← Hash-based caching
  providers/
    db.py                 ← Symbol metadata (PostgreSQL)
    vectors.py            ← Semantic search (Qdrant)
    ast.py                ← Signatures/dependencies

work/context_packets/     ← Artifacts
  <task_id>/
    context.yaml          ← Serialized packet
```

## Usage

### CLI

```bash
# Build packet for task
core-admin context build --task TASK_001

# Validate existing packet
core-admin context validate --file work/context_packets/TASK_001/context.yaml

# Show packet metadata
core-admin context show --task TASK_001
```

### Python API

```python
from src.services.context import ContextBuilder, ContextValidator, ContextRedactor

# Initialize with providers
builder = ContextBuilder(db, qdrant, ast_provider, config)

# Build packet
task_spec = {
    "task_id": "TASK_001",
    "task_type": "docstring.fix",
    "summary": "Fix missing docstrings",
    "roots": ["src/"],
    "max_tokens": 10000,
}

packet = await builder.build_for_task(task_spec)

# Validate & redact
validator = ContextValidator()
is_valid, errors = validator.validate(packet)

redactor = ContextRedactor()
packet = redactor.redact(packet)

# Use in LLM call
# router.call_llm(packet)
```

## ContextPackage Structure (v0.2)

```yaml
header:
  packet_id: uuid
  task_id: string
  task_type: enum[docstring.fix, header.fix, test.generate, ...]
  created_at: iso8601
  builder_version: string
  privacy: enum[local_only, remote_allowed]

problem:
  summary: string
  intent_ref: string (optional)
  acceptance: list[string]

scope:
  include: list[glob_pattern]
  exclude: list[glob_pattern]
  roots: list[path]

constraints:
  max_tokens: int
  max_items: int
  forbidden_paths: list[glob_pattern]
  forbidden_calls: list[function_name]

context:
  - name: string
    path: string
    item_type: enum[symbol, snippet, summary, ...]
    signature: string
    span: {start: int, end: int}
    summary: string
    snippet: string
    deps: list[string]
    hash: string
    source: enum[db, qdrant, ast, filesystem]
    tokens_est: int

invariants:
  - "All symbols must have signatures"
  - "No filesystem operations in snippets"
  - ...

policy:
  redactions_applied:
    - item_name: string
      reason: string
      redacted_at: iso8601
  remote_allowed: bool
  notes: string

provenance:
  inputs: {db_query, qdrant_query, ast_files}
  build_stats: {duration_ms, items_collected, ...}
  cache_key: string
  packet_hash: string
```

## Privacy Enforcement

Policy automatically blocks:

- **Forbidden Paths**: `.env`, `*.key`, `.secrets/**`, etc.
- **Secret Patterns**: API keys, passwords, tokens, private keys
- **PII**: Email addresses (configurable)
- **Dangerous Calls**: `os.remove`, `subprocess.run`, network I/O

Redactions are logged in `policy.redactions_applied` for audit.

## Token Management

- Estimates tokens per context item (via `serializers.estimate_tokens`)
- Enforces `constraints.max_tokens` by trimming context array
- Prioritizes high-value items (symbols > snippets > summaries)

## Caching

Hash-based cache avoids rebuilding identical contexts:

```python
cache = ContextCache("work/context_cache")
cache_key = ContextSerializer.compute_cache_key(task_spec)

if cached := cache.get(cache_key):
    return cached

# Build new packet...
cache.put(cache_key, packet)
```

Cache TTL: 24 hours (configurable).

## Database Schema

```sql
context_packets (
  packet_id UUID PRIMARY KEY,
  task_id VARCHAR(255),
  task_type VARCHAR(50),
  privacy VARCHAR(20),
  packet_hash VARCHAR(64),
  tokens_est INT,
  path TEXT,
  metadata JSONB,
  ...
)
```

See `sql/2025-11-11_create_context_packets.sql` for full schema.

## Status

**Phase 0**: ✓ Complete (contracts, stubs, CLI skeleton)
**Phase 1**: In Progress (provider integration, DB writes)
**Phase 2**: Planned (AST enrichment, quality improvements)
**Phase 3**: Planned (canary, metrics, router integration)

## Testing

```bash
# Unit tests
pytest tests/services/context/

# Integration test
core-admin context build --task docstring.fix.001
```

## Constitutional Compliance

This service enforces `.intent/context/policy.yaml` as constitutional law:

- **Privacy by default**: `local_only` unless explicitly set
- **Zero secrets in context**: Forbidden paths/patterns block packet creation
- **Token budgets prevent overflow**: Hard limits enforced
- **All operations audited**: DB + provenance tracking

Violations block packet creation and trigger audit logs.
