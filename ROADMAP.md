# CORE Roadmap

CORE is in active development. Work is organized into milestone **bands** —
strategic groupings with explicit closure criteria. Each band must close before
the next becomes the primary focus.

This document describes what has been built, what is being finished, and where
the project is going. It is honest about current state.

---

## Autonomy Ladder

CORE measures progress on an autonomy ladder from A1 (human does everything)
to A5 (full governed autonomy, human handles only genuine judgment calls).

| Level | Description | Status |
|-------|-------------|--------|
| A1 | Human writes all code, AI assists | Superseded |
| A2 | AI generates code, human reviews every change | Superseded |
| A3 | Governed autonomy loop running — audit, propose, approve, execute | **Current** |
| A4 | Multi-project governance, external-repo validation | In progress |
| A5 | Full governed autonomy, human governs intent not execution | Future |

A3 was reached in May 2026. The consequence chain (Finding → Proposal →
Approval → Execution → File Changes → New Findings) is fully materialized,
attributed, and queryable.

---

## Milestone Bands

### Band A — Foundation ✅ Closed
Constitutional primitives, rules engine, audit system, blackboard, basic
worker infrastructure.

### Band B — Consequence Chain ✅ Closed
The full governance loop materialized end-to-end. Every edge attributed and
persisted. Released as v2.4.0 "Consequence Chain" (2026-05-01).

### Band C — Historical Debt ✅ Closed
NULL backfills, stuck findings, unmapped rules — pre-existing governance debt
resolved before advancing.

### Band D — Engine Integrity 🔄 95% complete
Engine-level correctness: ContextBuilder wiring, path mapping externalization,
action executor guards, daemon composition root, rule campaigns. Six issues
remain open.

### Band E — Outward-Facing 🔄 In progress (48%)
Post-Band-D work: external-repository validation (BYOR), governor interface
improvements, outward-facing documentation, enterprise readiness tracks.

---

## What Band E Delivers

Band E is the transition from internal capability build-out to external
usability. It covers:

- **BYOR (Bring Your Own Repository):** CORE governing an external codebase,
  not just itself
- **Governor interface:** `core-admin ask` — natural language governance
  queries answered from constitutional context
- **Operating models:** Single-governor local, multi-operator server,
  air-gapped / GxP, CI-embedded
- **Documentation automation:** Compliance evidence packages, API reference,
  release notes — generated from CORE's own governed artifacts
- **Access control:** Authentication and RBAC for multi-operator deployments

---

## Commercial Direction

CORE is being positioned for regulated environments where governance evidence
is a compliance requirement — EU AI Act Articles 9 and 17, GxP qualification
(IQ/OQ/PQ), and similar frameworks.

Planned tiers:

| Tier | Description |
|------|-------------|
| CORE Audit | Read-only — run constitutional audits against any repository, get findings and compliance evidence |
| CORE Solo | Single-governor local deployment with full governance loop |
| CORE Team | Multi-operator with RBAC, API access, shared governance state |
| CORE Enterprise | Air-gapped, GxP-ready, compliance evidence package generation |

No timeline commitments are made here. Tiers are sequenced by governance
readiness, not market pressure.

---

## What CORE Is Not Trying To Be

CORE is not a code completion tool. It is not a CI linter. It is not a
developer productivity product.

It is a governance runtime — applicable wherever artifact-producing processes
must be traceable, defensible, and attributed. Software development is the
primary current use case. The architecture is domain-agnostic.
