---
kind: adr
id: ADR-056
title: ADR-056 — Runtime Data Contracts as First-Class Constitutional Artifacts
status: accepted
---

# ADR-056 — Runtime Data Contracts as First-Class Constitutional Artifacts

**Date:** 2026-05-17
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)

---

## Context

CORE governs code structure, behavioral patterns, and operational
configuration. What it does not govern is the shape and semantic
invariants of data objects that flow through the system at runtime.

A constitutional rule may say "workers must post findings to the
blackboard" — a behavioral claim, enforceable by pattern matching. No
rule can say "a finding without a rule_id is constitutionally invalid"
— because field contracts live only in Python, outside governance
jurisdiction. `data_contract` appears zero times in `.intent/`.

Verification against live code (2026-05-17) confirmed three concrete
instances of this gap:

**Finding has three parallel shapes in `src/`, none governed.**
The Pydantic class, the audit run record, and the blackboard entry all
represent the concept of "finding" with different field sets and no
shared contract. The constitution references Finding 137 times in the
governance sense of the blackboard entity, but the Pydantic class
claims that name for a different concept — engine output.

**Proposal mixes fields from three lifecycle phases in one class.**
Planning, authorization, and execution fields coexist with no
constitutional declaration of which fields are valid at each lifecycle
state. `ProposalStateManager` enforces transitions correctly; the
invariants it enforces are invisible to audit.

**`BlackboardEntry.entry_type` valid values live in a code comment.**
These are governed vocabulary values sitting outside governance
jurisdiction.

---

## Decision

### D1 — Establish `.intent/enforcement/contracts/` as a new governed artifact class

Runtime data contracts are constitutional artifacts. They define the
canonical shape and semantic invariants of inter-component data objects.
Introducing or modifying a contract requires an ADR.

### D2 — The name `Finding` belongs to the blackboard entity

The Pydantic class represents engine output — the result of evaluating
one rule. It is renamed accordingly. The name `Finding` is reserved for
the constitutional governance entity: the blackboard signal that drives
the consequence chain.

### D3 — Finding is governed by a canonical nucleus contract

A data contract defines the minimum required fields that any object
claiming to be a Finding must satisfy, regardless of which layer it
inhabits. Layer-specific extensions are permitted; nucleus fields are
not optional.

### D4 — Proposal is governed as a state-machine aggregate

A data contract for Proposal declares which fields are mandatory,
optional, or prohibited at each `ProposalStatus`. `ProposalStateManager`
remains the enforcement site. The contract makes its invariants
constitutionally visible and auditable.

Proposal is not decomposed into separate types. The state machine
architecture is correct; the gap is declaration, not structure.

### D5 — `BlackboardEntry.entry_type` values are governed vocabulary

Valid entry type values are declared in `.intent/META/enums.json` under
the key `blackboard_entry_type`. The enforcement pattern for `enums.json`
is `$ref` from JSON Schemas: governance YAML artifacts that consume an
enum reference it via `./enums.json#/definitions/<name>`, and the
artifact-gate engine constrains values during schema validation
(precedent: `phase`, `worker_status`, `artifact_status` enforced via
`workflow_stage.schema.json` and `worker.schema.json`).

Programmatic enforcement of enum values appearing as string literals
in `src/` — e.g. a worker posting `entry_type="violation"` — requires
the schema-conformance check class introduced in D6 plus Wave 1 schemas
that bind specific Python class fields to the enum. Until those land,
the enum is declared but not statically enforced against Python source.

Note: an earlier draft of this decision referred to "the existing
vocabulary canonical store rule" as the enforcement mechanism. That
phrasing was inaccurate — `governance.vocabulary_canonical_store`
governs the term vocabulary at `CORE-Vocabulary.md` ↔ `vocabulary.json`,
not the enum vocabulary at `enums.json`. Corrected 2026-05-18.

### D6 — Schema conformance is enforced via the AST gate

Schema conformance — validating that a Python class field declaration
matches a governing data contract — is implemented as a new check class
`SchemaConformanceChecks` within the existing AST gate
(`src/mind/logic/engines/ast_gate/checks/`), not as a new engine.

The AST gate already extracts class field structure; this is a natural
extension consistent with the precedent of `PurityChecks`,
`NamingChecks`, and `ImportChecks`. Rules using this check carry
`check_type: schema_conformance` and a `schema_ref` parameter pointing
to the governing `.intent/enforcement/contracts/` file.

### D7 — Boundary criteria for required data contracts

A structured object must have a governing `.intent/enforcement/contracts/`
schema when it crosses one or more of these boundaries:

1. **Consequence chain** — audit → blackboard → proposal → execution →
   consequence
2. **Worker boundary** — any payload written to `core.blackboard_entries`
3. **Persistence boundary** — any JSONB column in `core.*`
4. **AI invocation boundary** — any payload sent to or received from
   `PromptModel.invoke()`
5. **Vector store boundary** — any payload written to or queried from
   Qdrant
6. **API boundary** — any FastAPI request or response body
7. **Phase boundary** — any object passed between
   ComponentPhase-declared components
8. **Atomic-action boundary** — any `@atomic_action` argument or
   return value
9. **Flow boundary** — any Flow step input or output

A structured object that does not cross any of these boundaries may
remain ungoverned. Authoring an object that crosses one of these
boundaries without a governing schema is a constitutional violation
under `architecture.data_contracts.boundary_governed`.

Rules for this artifact class are introduced at INFO severity.
Enforcement tightens as coverage matures.

---

## Consequences

- AI-generated code that produces a structurally valid but semantically
  wrong runtime object is detectable at audit time.
- Schema evolution requires an ADR. No silent field additions.
- The constitutional vocabulary for "Finding" is unambiguous.
- Proposal state-conditional invariants become auditable.
- `BlackboardEntry.entry_type` drift is detectable.
- D7 provides a decision rule for all future contract authoring — no
  case-by-case judgment required.

---

## References

- ADR-010 — finding-proposal contract
- ADR-015 — consequence chain attribution
- ADR-023 — vocabulary canonical store
- ADR-035 — one finding, one proposal
- ADR-040 — no hardcoded config values (precedent for externalization)
- `.specs/planning/data-contracts-inventory.md` — full contract
  inventory and wave plan
