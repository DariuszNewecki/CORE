# CORE — Data Contracts

**Status:** Canonical
**Authority:** Constitution (derivative, non-amending)
**Scope:** Runtime data contracts as constitutional artifacts in CORE

---

## 1. Purpose

This paper defines what a data contract is in CORE, how it is declared,
how it is enforced, and where the boundary of automated enforcement ends
and governor authority begins.

It records the reasoning behind ADR-056's design decisions — particularly
the choice of contract-side class declaration and the rejection of
Python-side markers — so that future sessions and future CORE instances
can extend the pattern correctly.

---

## 2. Definition

A data contract is a constitutional declaration of the structure a
governed Python class must have. It lives in
`.intent/enforcement/contracts/` as a JSON Schema file.

A data contract declares:

- which Python classes it governs (`governed_classes`)
- what fields those classes must declare (`properties`)
- which fields are non-optional (`required`)

A data contract does **not**:

- live in `src/`
- annotate or decorate the governed class
- change the runtime behavior of the governed class
- replace type annotations or Pydantic validation

The declaration is the authority. The Python class is the governed
artifact. The audit check is the enforcement mechanism.

---

## 3. The Enum Analogy

Data contracts follow the same pattern as vocabulary enums in
`.intent/META/enums.json`.

| | Enums | Data Contracts |
|---|---|---|
| Declaration lives in | `.intent/META/enums.json` | `.intent/enforcement/contracts/` |
| Governs | Python string literal values | Python class field declarations |
| Enforcement | AST gate, `schema_conformance` check | AST gate, `schema_conformance` check |
| Python carries no marker | ✓ | ✓ |
| Declaration is the authority | ✓ | ✓ |

An enum declares what values are legal. A data contract declares what
structure is required. The enforcement architecture is identical.

This analogy is the design rationale for every implementation choice
in ADR-056 D6.

---

## 4. Why No Python-Side Markers

The first design candidate for class discovery was a decorator:
`@schema_contract("ContractName")` placed on the governed class.

This was rejected for two reasons.

**Reason 1 — Authority inversion.** A decorator places constitutional
registration in `src/`, which is the governed layer. The contract file
is the law. The Python class is the implementation. Law does not derive
its authority from what the implementation says about itself. The contract
file must declare its own scope.

**Reason 2 — Decorator proliferation.** CORE already governs code with
`@atomic_action`, `@command_meta`, and other decorators. Each decorator
is a permanent maintenance surface. A decorator added to mark governed
classes would propagate across every structured object that crosses a
D7 boundary — potentially dozens of classes. The cost is not justified
when the same information can live in the contract file.

The adopted mechanism: the contract file declares `governed_classes` as
a list of Python class names. The `SchemaConformanceChecks` engine reads
this list, locates matching `ClassDef` nodes in the AST of the files
targeted by the governance rule, and validates their field declarations.
No Python file is touched for governance registration purposes.

---

## 5. Building Blocks and Construction-Time Consistency

Data contracts are one layer of a broader consistency architecture.
CORE has two mechanisms for making code predictable:

**Building blocks** — base classes, abstract base classes, and governed
primitives that make incorrect construction structurally impossible. When
a class inherits from a governed base class, Python enforces the contract
at class-definition time via `__init_subclass__`. The wrong structure
cannot be expressed. Examples: `Component`, Worker base classes,
`@atomic_action`.

**Data contracts** — constitutional declarations that govern what building
blocks and their implementations must contain. Where building blocks
enforce structure in Python, data contracts declare that structure in
`.intent/`. The audit check validates conformance.

These two mechanisms are complementary:

- Building blocks enforce at construction time (Python raises immediately)
- Data contracts enforce at audit time (constitutional audit catches drift)

A class that uses a governed building block AND has a governing data
contract is enforced at both layers. A class that uses only a building
block is enforced structurally but not constitutionally. A class with
only a data contract is audited but not construction-time-constrained.

The strongest guarantee requires both. Wave 1 contracts introduce the
constitutional layer. The building blocks layer is a separate and
longer-running architectural investment.

---

## 6. The Consistency Boundary for Autonomous Operation

When CORE operates autonomously and generates new code, the question
arises: how does generated code remain consistent with the existing
codebase?

The answer has two parts depending on what is being generated.

**Known patterns.** If CORE generates a class that belongs to a
governed family — a Worker, an Action, a Finding — the building block
(base class) and the data contract together constrain what CORE can
produce. CORE cannot generate a structurally wrong Worker because the
Worker base class enforces the contract at import time. CORE cannot
generate a Finding with missing required fields without the audit
catching it immediately.

**Unknown patterns.** If CORE discovers an efficiency gain that requires
introducing a genuinely new pattern — one with no existing building
block, no data contract, no governance rule — automated enforcement
cannot apply. There is no law covering the unknown pattern.

In this case the consistency guarantee is the governor, not the
constitution. CORE surfaces the discovery as a proposal. The governor
evaluates it, authors the constitutional artifacts (the ADR, the base
class, the contract), and only then can conforming code be generated.

This boundary is intentional and permanent. **The governor is the
consistency mechanism for unknown patterns. Building blocks and data
contracts are the consistency mechanism for known patterns.**

The constitution governs what it knows. The governor governs what it
does not yet know.

---

## 7. Real-World Precedent

This pattern is not novel. It appears across the most battle-tested
infrastructure systems in production:

**Kubernetes Custom Resource Definitions (CRDs)** — any resource
submitted to the cluster must conform to a declared schema. Non-conforming
resources are rejected at submission time, before execution.

**Protocol Buffers / Avro / Thrift** — schema-first design. The schema
is declared independently of any implementation. Code is either generated
from the schema or validated against it. A malformed message cannot be
constructed.

**Terraform provider schemas** — when Terraform plans infrastructure
changes, every proposed resource must conform to the provider's schema.
The provider schema is the constitution; Terraform cannot propose a
structurally invalid resource.

**Django ORM metaclass** — a Model subclass that violates the ORM
contract raises at class-definition time, before any database interaction.

CORE applies the same principle to code governance: the `.intent/`
contract is the schema, the Python class is the resource, the audit is
the admission controller.

---

## 8. Boundary Criteria

A Python class requires a governing data contract when it crosses one
or more of the boundaries declared in ADR-056 D7:

1. Consequence chain — audit → blackboard → proposal → execution → consequence
2. Worker boundary — any payload written to `core.blackboard_entries`
3. Persistence boundary — any JSONB column in `core.*`
4. AI invocation boundary — any payload sent to or received from `PromptModel.invoke()`
5. Vector store boundary — any payload written to or queried from Qdrant
6. API boundary — any FastAPI request or response body
7. Phase boundary — any object passed between ComponentPhase-declared components
8. Atomic-action boundary — any `@atomic_action` argument or return value
9. Flow boundary — any Flow step input or output

A class that does not cross any of these boundaries may remain ungoverned.

---

## 9. Contract File Structure

A contract file at `.intent/enforcement/contracts/<name>.json` must
contain:

```json
{
  "governed_classes": ["ClassName", "AnotherClassName"],
  "properties": {
    "field_name": { "type": "string", "description": "..." }
  },
  "required": ["field_name"]
}
```

`governed_classes` is the declaration of scope. It names the Python
classes this contract governs. The audit check uses this list to locate
matching `ClassDef` nodes in the AST of files targeted by the governance
rule.

`properties` declares the legal field set. Fields present in a governed
class but absent from `properties` are a violation.

`required` declares the mandatory subset of `properties`. Fields in
`required` but absent from the governed class are a violation.

The contract file is a constitutional artifact. It is authored by the
governor. It is never generated by CORE.

---

## 10. Enforcement Chain

```
.intent/enforcement/contracts/<name>.json   ← declaration (governor-authored)
        ↓
.intent/rules/data/governance.json          ← rule with check_type: schema_conformance,
        ↓                                       schema_ref: <name>, glob targeting files
ASTGateEngine dispatch                      ← resolves contract_path, calls check
        ↓
SchemaConformanceChecks.check_schema_contract_fields()  ← reads governed_classes,
        ↓                                                   validates AST fields
ConstitutionalAuditor                       ← collects findings, issues verdict
```

The enforcement chain is deterministic. No LLM is involved. The same
code produces the same verdict on every run.

---

## 11. Non-Goals

This paper does not define:

- The full Wave 1 contract inventory (see `.specs/planning/data-contracts-inventory.md`)
- Building block base class design (a separate architectural investment)
- Runtime enforcement via `__init_subclass__` (construction-time constraint,
  distinct from audit-time enforcement)
- Contract schema evolution policy (requires a future ADR when the first
  breaking field change occurs)

---

## 12. References

- ADR-056 — runtime data contracts (decision record)
- `.specs/planning/data-contracts-inventory.md` — Wave 1–3 contract inventory
- `CORE-Finding.md` — Finding payload as governed class (Wave 1 candidate)
- `.intent/META/enums.json` — enum vocabulary (pattern precedent)
- `.intent/enforcement/contracts/` — contract file directory
