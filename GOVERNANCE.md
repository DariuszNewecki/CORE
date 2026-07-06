# CORE Governance Model

CORE is a constitutionally-governed governance runtime. It enforces declared
law over any artifact-producing process — not just software, but documentation,
compliance artifacts, regulated process outputs, or any system where decisions
must be traceable, defensible, and attributed.

Software development is the primary current use case. The architecture is
domain-agnostic.

---

## Constitutional Authority

Governance in CORE is grounded in a written constitution at
`.intent/constitution/CORE-CONSTITUTION.md`.

The constitution defines four irreducible primitives: **Document**, **Rule**,
**Phase**, and **Finding**. Everything else derives from these. Anything not
defined constitutionally does not exist as a governance concept.

The constitution is **immutable at runtime**. No running process — including AI
— may modify it. Changes require a human decision, recorded as an Architecture
Decision Record (ADR) in `.specs/decisions/`.

---

## Where Authority Lives

| Directory | Role | Who writes it |
|-----------|------|---------------|
| `.intent/` | Constitution, rules, enforcement mappings, canonical schemas | Human governor only |
| `.specs/` | ADRs, requirements, papers, planning | Human governor only |
| `src/` | Implementation | Generated or written under governance |

`.intent/` is law. Everything else must comply with it. The audit system
verifies compliance continuously.

---

## Architectural Separation: Mind / Will / Body

CORE's implementation is divided into exactly three layers. This separation is
constitutional, not organizational. Violations are governance failures.

### Mind — Law & Governance (`src/mind/`)

Mind defines what is allowed, required, or forbidden. It contains the rules
engine, audit logic, and enforcement machinery.

Mind never executes. It evaluates. A rule that executes itself becomes
self-legitimizing — that is explicitly forbidden.

### Will — Decision & Orchestration (`src/will/`)

Will decides which actions to take, when, and in what order. It reads from
Mind (law) and directs Body (execution).

Will never implements actions directly. It orchestrates. Strategy without
constraint is arbitrary power — Will is bounded by what Mind permits.

### Body — Pure Execution (`src/body/`)

Body executes operations without making decisions about which operation to
perform. It receives explicit instructions, carries them out, and returns
structured results.

Body never evaluates rules or policies. Execution without bounds is arbitrary
power — Body acts only on what Will directs, within what Mind permits.

---

## The Governance Loop

```
Finding → Proposal → Approval → Execution → New Audit
```

1. The audit system inspects artifacts against constitutional rules
2. Violations become **Findings**, persisted to the governance database
3. Each Finding generates a **Proposal** — a bounded, attributed remediation
4. Proposals require **authorization** before execution
5. Authorized proposals are executed by the Body layer
6. Execution produces changes, which are re-audited
7. Every step is attributed, persisted, and queryable

This is a closed feedback control system. The system is healthy when
resolution rate exceeds creation rate.

---

## Traceability

Every governance event — audit run, finding, proposal, authorization decision,
execution result — is persisted with full attribution. The consequence chain
(Finding → Proposal → Approval → Execution → Changes → New Findings) is
queryable end to end.

This posture directly addresses regulated environments where evidence of
control is a compliance requirement, including EU AI Act Articles 9 (risk
management system) and 17 (quality management system).

---

## Architecture Decision Records

All architectural decisions that affect governance are recorded as ADRs in
`.specs/decisions/`. An ADR defines the problem, the decision, the rationale,
and the consequences. Implementation follows the ADR — the ADR is not written
to document what was implemented.

As of the current release, 144 ADRs are on record.

---

## What CORE Is Not

CORE is not a prompt engineering framework. It is not an agent framework. It
does not make AI trustworthy by making it more capable.

CORE makes AI output **safe to use** by surrounding non-deterministic AI output
with a deterministic governance system that enforces constitutional rules before
anything reaches a governed artifact.

The human role is governor and architect — writing intent, approving proposals,
amending the constitution. AI is a production component, never trusted, always
verified.
