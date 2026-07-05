---
kind: adr
id: ADR-090
title: "ADR-090 — Cognitive Roles DB Structural Enforcement"
status: accepted
depends_on: ["ADR-068", "ADR-052"]
---

<!-- path: .specs/decisions/ADR-090-cognitive-roles-db-structural-enforcement.md -->

# ADR-090 — Cognitive Roles DB Structural Enforcement

**Date:** 2026-07-05
**Status:** Accepted (governor decision 2026-07-05)
**Author:** Darek (Dariusz Newecki)
**Closes:** #487

**Governing ADRs:**
- ADR-068 — principal_roles backfill + CHECK pattern (mirror target)
- ADR-052 — resource assignment (role_resource_assignments supersedes cognitive_roles columns)

---

## Context

A prior session (commits `e378b253`, `b55955f3`) closed the governance half
of the cognitive-roles drift gap: `.intent/taxonomies/cognitive_roles.yaml`
is the canonical name set, `load_cognitive_roles` is the fail-closed loader,
and `artifact_gate.py` reads the taxonomy instead of `_KNOWN_ROLES`.

Two structural gaps remain:

1. **No value-restricting CHECK on `core.cognitive_roles.role`** — an
   INSERT with an undeclared role is accepted by the DB and honoured by 8
   inbound FKs, silently recreating the drift just closed at the governance
   layer.

2. **Columns that outran their definition** — `operating_mode` and
   `max_concurrent_tasks` live in `cognitive_roles` but are not declared in
   the paper or the taxonomy YAML. Per constitutional principle: ungoverned
   state in a governed table is structural debt.

3. **`required_capabilities` is Role-layer, not "elsewhere"** — the YAML
   header wrongly classified it as a resource concern. The paper (§2.2, §3)
   explicitly places capabilities at the Role layer as the matching
   predicate between Role and Resource.

4. **`tasks.assigned_role` FK has no ON UPDATE/DELETE actions** — the other
   7 inbound FKs to `cognitive_roles` all declare `ON UPDATE CASCADE ON
   DELETE RESTRICT`; this one defaults to `NO ACTION`.

---

## Decisions

### D1 — Reconciliation trigger: migration-driven

The CHECK constraint and column drops are applied as a one-shot DDL change-
set (governor-run via `psql`). The taxonomy YAML is authoritative; the DB
is derived. No startup-time or scheduled reconciliation — the constraint
itself enforces alignment from the moment it is applied.

### D2 — CHECK shape: enumerated ARRAY (ADR-068 pattern)

```sql
CHECK (role = ANY(ARRAY[
    'Architect', 'CapabilityTagger', 'CodeReviewer', 'Coder',
    'ConstitutionalCoherenceAnalyst', 'DocstringWriter', 'LocalCoder',
    'LocalReasoner', 'Planner', 'RemoteCoder', 'Vectorizer'
]))
```

Generated from the current taxonomy. Any new role requires both a taxonomy
YAML entry and a DDL revision — two-surface confirmation requirement by
design.

### D3 — Unknown roles: block reconciliation

There are no unknown roles in the live DB (all 11 DB rows match the taxonomy
declaration exactly). The CHECK is applied clean. Going forward: any INSERT
with an undeclared role is rejected at the storage layer.

### D4 — `tasks.assigned_role` FK: tighten to match peers

```sql
-- Drop + re-add with explicit actions
ALTER TABLE ONLY core.tasks
    DROP CONSTRAINT tasks_assigned_role_fkey;
ALTER TABLE ONLY core.tasks
    ADD CONSTRAINT tasks_assigned_role_fkey
    FOREIGN KEY (assigned_role) REFERENCES core.cognitive_roles(role)
    ON UPDATE CASCADE ON DELETE RESTRICT;
```

Matches the other 7 inbound FKs. Rename-safe via CASCADE; protects against
orphan tasks via RESTRICT.

### D5 — Column scope: required_capabilities in YAML; drop operating_mode + max_concurrent_tasks; specialization stays

**`required_capabilities`** — Role-layer per the paper. Added to the
taxonomy YAML for all 11 roles (DocstringWriter corrected from empty to
`code_understanding + documentation`). The YAML header that wrongly excluded
it is corrected.

**`operating_mode`** — Resource-layer (routing policy, paper §4). The
per-role override in `cognitive_roles.operating_mode` is removed; all roles
use the system-level `operating_mode` from `system_config`. Consequence:
`ConstitutionalCoherenceAnalyst`'s `hybrid` override disappears; it adopts
the system default. `ResourceSelector._filter_by_locality` simplifies to
`effective_mode = system_operating_mode`.

**`max_concurrent_tasks`** — Not declared in the paper; not consumed in any
logic (ORM-only). Dropped. Concurrency limits at the Resource layer exist on
`llm_resources.max_concurrent`; the Role layer has no business owning this.

**`specialization`** — Resource-layer binding data (`model_preference`,
`latency_tolerance`). Stays in the DB but is explicitly NOT a taxonomy
concern. Future ADR may move it to `role_resource_assignments` or
`llm_resources`. No code change in this ADR.

---

## Deliverables

| ID | Artifact | Change |
|----|---------|--------|
| D1a | `.intent/taxonomies/cognitive_roles.yaml` | Add `required_capabilities` to all 11 roles; correct header |
| D1b | `src/shared/infrastructure/database/models/operations.py` | Remove `operating_mode` and `max_concurrent_tasks` from `CognitiveRole` |
| D1c | `src/will/agents/resource_selector.py` | `effective_mode = system_operating_mode` (2 sites); update docstrings |
| D1d | `tests/will/agents/test_resource_selector_high_reasoning.py` | Remove `r.operating_mode = None` |
| D1e | `infra/sql/db_schema_live.sql` | Remove 2 columns + `operating_mode_check`; add `role_check`; tighten tasks FK |
| D1f | Live DB | Stop daemons → DDL → start daemons |
