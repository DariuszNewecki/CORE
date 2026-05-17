# ADR-056 — Runtime Data Contracts as First-Class Constitutional Artifacts

**Date:** 2026-05-17
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)

---

## Context

CORE governs code structure (AST gate, regex gate), behavioral patterns
(architectural rules, modularity), and operational configuration
(ADR-040). What it does not govern is the shape and semantic invariants
of the data objects that flow through the system at runtime.

A constitutional rule may say "workers must post findings to the
blackboard" — a behavioral claim, enforceable by pattern matching. No
rule can say "a finding without a `rule_id` is constitutionally invalid"
— because the field contract lives only in Python, outside governance
jurisdiction.

### The three-surface problem

Verification against live code (2026-05-17) surfaced a concrete
instance of this gap. The concept of "finding" has three parallel
shapes in `src/`, none governed, none in agreement:

**Surface 1 — `Finding` (Pydantic, `src/body/services/cim/models.py`)**
```
id, severity, rule, evidence, recommendation, links
```
Used by the CIM/policy world as the output of a rule evaluation.

**Surface 2 — `audit_runs.findings` (JSONB dict in DB)**
```
check_id, severity, message, file_path, line_number, context
```
Written by `will.governance.audit_runner`; schemaless; shape derived
from the legacy `core.audit_findings` table.

**Surface 3 — `BlackboardEntry(entry_type='finding')` (SQLAlchemy ORM)**
```
worker_uuid, entry_type, phase, status, subject, payload (freeform JSONB)
```
The blackboard signal that drives the consequence chain.

The constitution references "Finding" 137 times in the governance sense
of the blackboard entity. The Pydantic class claims that name but
represents a different thing — engine output, not a governance signal.
`data_contract` appears zero times in `.intent/`.

### The `entry_type` enum problem

`BlackboardEntry.entry_type` valid values (`finding | claim | proposal |
report | heartbeat`) live in a source code comment. AI-generated code
posting `entry_type='violation'` is constitutionally invisible.

### The `Proposal` invariant problem

`Proposal` (`src/will/autonomy/proposal.py`) mixes fields from three
lifecycle phases in one class:

- Planning: `goal`, `actions`, `scope`, `risk`
- Authorization: `approved_by`, `approved_at`, `approval_authority`,
  `constitutional_constraints`, `approval_required`
- Execution: `execution_started_at`, `execution_completed_at`,
  `execution_results`, `failure_reason`

`ProposalStateManager` enforces valid transitions and
`proposal_lifecycle.yaml` governs the rules — the state machine
machinery is correct. What is missing is a constitutional declaration
of which fields are valid at each `ProposalStatus`. Without it,
state-conditional invariants are implicit in code and invisible to audit.

---

## Decision

### D1 — Establish `.intent/data_contracts/` as a new governed artifact class

A new subdirectory `.intent/data_contracts/` holds JSON Schema documents
defining the canonical shape and semantic invariants of runtime data
objects. These are first-class constitutional artifacts: they require an
ADR to introduce or modify, and they are read-only to `src/` at runtime.

Schema files follow the naming convention `<TypeName>.schema.json`.

The global document meta-schema (`.intent/META/GLOBAL-DOCUMENT-META-SCHEMA.json`)
is extended to include `data_contract` as a valid document kind.

### D2 — Rename `Finding` (Pydantic) to `CheckResult`

The Pydantic class at `src/body/services/cim/models.py` is renamed from
`Finding` to `CheckResult`. It represents engine output — the result of
evaluating one rule — not the constitutional governance entity.

The name `Finding` is reserved for the blackboard entity (Surface 3)
which is what the constitution governs in 137 references.

No field changes. Rename only.

### D3 — Define the canonical `Finding` data contract

`.intent/data_contracts/Finding.schema.json` governs the minimum
required nucleus for any object that claims to be a constitutional
Finding. All three surfaces must satisfy this nucleus.

Required fields:
- `rule_id` — the constitutional rule that was violated
- `severity` — one of the governed severity levels (from enums.json)
- `subject` — the artefact (file, symbol, module) where the violation
  was detected
- `evidence` — human-readable description of what was found
- `worker_uuid` — the worker that detected and posted this finding

Each surface may extend the nucleus with layer-specific fields
(`file_path`, `line_number` for audit records; `payload` for blackboard
entries). No surface may omit a nucleus field.

### D4 — Define the `Proposal` data contract with state-conditional invariants

`.intent/data_contracts/Proposal.schema.json` governs `Proposal` fields
and declares which fields are mandatory, optional, or prohibited at each
`ProposalStatus`.

State-conditional invariants:

| Field group | DRAFT | APPROVED | EXECUTING | COMPLETED / FAILED |
|---|---|---|---|---|
| `goal`, `actions`, `scope` | required | required | required | required |
| `approved_by`, `approval_authority` | must be null | required | required | required |
| `execution_started_at` | must be null | must be null | required | required |
| `execution_completed_at`, `execution_results` | must be null | must be null | must be null | required |
| `failure_reason` | must be null | must be null | must be null | required if FAILED |

`ProposalStateManager` remains the enforcement site. The data contract
makes the invariants constitutionally visible and auditable; it does not
replace `ProposalStateManager`.

`Proposal` is not decomposed into separate types. The state machine
architecture is correct. The gap is declaration, not structure.

### D5 — Govern `BlackboardEntry.entry_type` as a vocabulary enum

The valid values for `BlackboardEntry.entry_type`
(`finding | claim | proposal | report | heartbeat`) are added to
`.intent/META/enums.json` under the key `blackboard_entry_type`.

The existing `vocabulary_canonical_store` rule (ADR-023) is extended
to cover this enum. Any `entry_type` value not present in the governed
enum is a constitutional violation.

### D6 — Extend the AST gate with a `SchemaConformanceChecks` class

Schema conformance is implemented as a new check class
`SchemaConformanceChecks` inside the existing AST gate
(`src/mind/logic/engines/ast_gate/checks/`), not as a new engine.

Rationale: the AST gate already parses Python class definitions and
extracts field structure. Schema conformance requires exactly that
prerequisite work — inspect a class, compare against a reference. A
new engine would add registration, configuration, and test infrastructure
for no architectural gain. The precedent of `PurityChecks`,
`NamingChecks`, and `ImportChecks` as distinct classes within the AST
gate applies here directly.

Rules using this check carry `check_type: schema_conformance` and a
`schema_ref` parameter pointing to the governing
`.intent/data_contracts/` file. The AST gate extracts class fields;
`SchemaConformanceChecks` loads the referenced schema and validates
field presence and type compatibility.

Initial coverage: `CheckResult` → `Finding.schema.json` nucleus,
`Proposal` → `Proposal.schema.json`.

This check runs in the static audit pass (not runtime). It verifies
field presence and type compatibility, not runtime values.

---

## Consequences

- AI-generated code that produces a structurally valid but semantically
  wrong Finding is now detectable at audit time.
- Schema evolution requires an ADR. No silent field additions.
- The constitutional vocabulary for "Finding" is unambiguous: it means
  the blackboard governance entity, not engine output.
- `Proposal` state-conditional invariants become auditable, not just
  operationally enforced.
- `BlackboardEntry.entry_type` values are governed; drift is detectable.

---

## Implementation order

1. Add `data_contract` kind to global meta-schema
2. Add `blackboard_entry_type` enum to `enums.json` (D5 — smallest,
   immediate value)
3. Author `Finding.schema.json` (D3)
4. Rename `Finding` → `CheckResult` in `src/` (D2)
5. Author `Proposal.schema.json` (D4)
6. Register `schema_conformance` check type (D6)

D5 is independent and can ship immediately. D2 and D3 are coupled and
ship together. D4 and D6 follow.

---

## References

- ADR-010 — finding-proposal contract
- ADR-015 — consequence chain attribution
- ADR-023 — vocabulary canonical store
- ADR-035 — one finding, one proposal
- ADR-040 — no hardcoded config values (precedent for config
  externalization pattern)
- `src/body/services/cim/models.py:279` — `Finding` (Pydantic)
- `src/will/autonomy/proposal.py:201` — `Proposal` dataclass
- `src/shared/infrastructure/database/models/workers.py:57` — `BlackboardEntry`
- `.intent/enforcement/mappings/will/proposal_lifecycle.yaml`
- `.intent/rules/will/proposal_lifecycle.json`
