# CORE Commercial Hardening Roadmap

Version: 1.2
Author: Dariusz Newecki
Scope: Solo-executable commercial hardening plan
Horizon: 8–10 weeks

---

# Maturity Baseline (Aligned to 0–5 Scale)

Commercial Readiness (Current): **3.0 / 5**
Research / Conceptual Maturity: **4.2 / 5**
Governance Integrity: **4.0 / 5**
Operational Determinism: **3.2 / 5**
Autonomy Level: **A2.5 (approaching Controlled A3)**

Target After Roadmap Completion:

Commercial Readiness: **≥4.2 / 5**
Operational Determinism: **≥4.3 / 5**
Autonomy Level: **Controlled A3**

---

# Executive Summary

CORE currently operates as a governance-first research-grade runtime.

Strengths:

* Clear Body–Mind–Will separation
* Runtime governance enforcement
* Strict/advisory execution modes
* Integrity and idempotency foundations
* Increasing CLI normalization

Primary Gaps:

* Partial capability closure
* Determinism not fully contract-bound
* Governance coverage not formally measurable
* Installability not yet industrialized
* Versioning and upgrade safety undefined

This roadmap focuses exclusively on **industrial tightening**.

No feature expansion.
No architectural redesign.
No scaling initiatives.

Objective: Transition from architecturally disciplined system → operationally trustworthy governed runtime.

---

# Phase 1 — Capability Closure

Timeline: Weeks 1–2
Primary Metric Affected: Commercial Readiness

## Goal

Eliminate declared-but-unimplemented surface area.

## Acceptance Criteria

* Every CLI command is:

  * Fully implemented, OR
  * Explicitly marked experimental, OR
  * Removed
* Self-check reports zero critical findings

## Deliverables

### CLI Registry Audit

* Enumerate all commands
* Validate handler existence
* Validate metadata completeness
* Detect duplicate canonical names

### Experimental Flag Mechanism

* Metadata field: experimental: true
* Hidden by default
* --show-experimental override

### Self-Check Command

`core-admin self-check`

Validates:

* Registry integrity
* Missing handlers
* Duplicate command definitions
* Metadata compliance

## Expected Score Movement

Commercial Readiness: 3.0 → 3.4

---

# Phase 2 — Deterministic Mutation Guarantees

Timeline: Weeks 3–4
Primary Metric Affected: Operational Determinism

## Goal

Prove CORE mutations are deterministic and infrastructure-grade.

## Acceptance Criteria

* All mutation engines pass idempotency test
* Duplicate #ID detection hard-blocked
* No unintended file drift in strict mode

## Deliverables

### Idempotency Harness

Execution model:

1. Snapshot
2. Run mutation
3. Snapshot
4. Run mutation again
5. Assert no diff

### Mutation Contract Document

Defines:

* Allowed mutation classes
* Forbidden mutation patterns
* Stability guarantees
* Invariants

### Integrity Verification Command

`core-admin integrity verify`

* Hash before/after
* Drift detection
* Deterministic failure reporting

### Duplicate Symbol ID Hard Gate

* Fail fast on duplicate #ID
* Optional auto-remediation tool
* Mandatory in strict mode

## Expected Score Movement

Operational Determinism: 3.2 → 4.1
Commercial Readiness: 3.4 → 3.9

---

# Phase 3 — Governance Enforcement Binding

Timeline: Weeks 5–6
Primary Metric Affected: Governance Integrity

## Goal

Make governance measurably enforceable.

## Acceptance Criteria

* 100% blocking rules mapped to runtime enforcement
* Governance coverage report ≥95%
* Strict mode deterministically fails on violation

## Deliverables

### Rule → Engine → Code Map

Traceability table linking:

* Rule ID
* Enforcement engine
* Code location
* Test reference

### Governance Coverage Command

`core-admin governance coverage`

Reports:

* Blocking rule binding percentage
* Advisory rule monitoring percentage
* Unbound rules

### Strict Mode Validation Tests

Minimum:

* 5 highest-risk blocking rules
* Deterministic failure cases

## Expected Score Movement

Governance Integrity: 4.0 → 4.5
Commercial Readiness: 3.9 → 4.2

---

# Phase 4 — Installation & Bootstrap Hardening

Timeline: Week 7
Primary Metric Affected: Commercial Readiness

## Goal

Achieve reproducible deployment.

## Acceptance Criteria

* Fresh machine → working CORE in ≤10 minutes
* Doctor command passes on clean setup

## Deliverables

### Doctor Command

`core-admin doctor`

Validates:

* Database connectivity
* Vector DB connectivity
* Required environment variables
* Schema alignment
* Intent integrity

### Environment Schema Definition

.env.schema

* Required variables
* Optional variables
* Fatal failure on missing required keys

### Verified Quickstart Guide

* Single canonical installation path
* No undocumented manual steps

### Optional Reference docker-compose

Reproducible but not mandatory.

## Expected Score Movement

Commercial Readiness: 4.2 → 4.4

---

# Phase 5 — Stability & Versioning Contract

Timeline: Week 8
Primary Metric Affected: Commercial Readiness

## Goal

Define upgrade safety and compatibility contract.

## Acceptance Criteria

* Semantic versioning policy defined
* Intent schema versioned
* Breaking changes detectable pre-upgrade

## Deliverables

### Semantic Versioning Policy

* Major: breaking governance or CLI surface
* Minor: additive non-breaking
* Patch: internal fixes

### Deprecation Lifecycle

* Warning phase
* Removal phase
* Documented timeline

### Intent Schema Versioning

* Version field in .intent
* Compatibility validation

### Upgrade Check Command

`core-admin upgrade-check`

Validates:

* Schema compatibility
* Rule changes
* Breaking interface changes

## Expected Score Movement

Commercial Readiness: 4.4 → ≥4.5

---

# Autonomy Progression

Current Level: **A2.5**

Characteristics:

* Governance enforcement present
* Partial determinism
* Traceability improving
* Strict/advisory toggle operational

Target Level: **Controlled A3**

A3 Requires:

* Deterministic mutation guarantees
* Measurable governance coverage
* Strict-mode enforceability
* Reversible changes
* Upgrade safety contract

This roadmap closes the gap.

---

# Final Projection (0–5 Scale)

Commercial Readiness: 3.0 → ≥4.5
Operational Determinism: 3.2 → ≥4.3
Governance Integrity: 4.0 → ≥4.5
Overall Effective Maturity: ≈4.3 / 5

At ≥4.3 / 5, CORE transitions from research-grade runtime to industrially credible governed system.

---

# Closing Statement

CORE does not lack architecture.
CORE does not lack conceptual rigor.
CORE requires industrial closure.

This roadmap delivers that closure.
