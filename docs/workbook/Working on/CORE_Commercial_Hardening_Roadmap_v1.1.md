# CORE Commercial Hardening Roadmap

Version: 1.0
Author: Dariusz Newecki
Scope: Solo-executable commercial hardening plan
Horizon: 8–10 weeks
Target Outcome: Increase commercial readiness from ~5.8 → ~8.2

---

## Executive Summary

CORE currently demonstrates strong research-grade maturity (~8.6/10) with a well-formed constitutional architecture and governance philosophy.

However, commercial readiness (~5.8/10) is limited by incomplete capability closure, insufficient determinism guarantees, and lack of operational hardening artifacts.

This roadmap focuses exclusively on industrial tightening — not feature expansion.

---

# Phase 1 — Capability Closure

**Timeline:** Weeks 1–2
**Goal:** Eliminate declared-but-unimplemented surface area.

## Objectives

* Ensure every CLI command is either:

  * Fully implemented
  * Explicitly marked experimental
  * Or removed

## Deliverables

### 1. CLI Command Registry Audit

* Enumerate all registered commands.
* Validate execution paths.
* Remove stubs or mark as experimental.

### 2. Experimental Flag Mechanism

* Add metadata flag for commands.
* Hide experimental commands by default.
* Add `--show-experimental` switch.

### 3. Command Self-Check Mode

New command:
`core-admin self-check`

Validates:

* Command registration integrity
* Missing handlers
* Duplicate definitions

## Expected Impact

+0.8 commercial readiness score
Immediate trust increase.

---

# Phase 2 — Deterministic Mutation Guarantees

**Timeline:** Weeks 3–4
**Goal:** Prove CORE behaves deterministically.

## Objectives

* All mutation engines must be:

  * Idempotent
  * Deterministic
  * Traceable
  * Reversible

## Deliverables

### 1. Idempotency Test Harness

Test sequence:

```
run mutation
snapshot
run mutation again
assert no diff
```

### 2. Mutation Contract Document

Define:

* Allowed mutations
* Forbidden mutations
* Stability guarantees
* Invariants

### 3. Checksum Verification Mode

New command:
`core-admin integrity verify`

* Hashes files before and after mutation.
* Flags unexpected changes.

### 4. Duplicate Symbol ID Hard Gate

* Detect duplicate `# ID:` values.
* Fail fast.
* Optional auto-remediation tool.

## Expected Impact

+1.0 commercial readiness score
Converts “LLM-driven experiment” → “controlled infrastructure”.

---

# Phase 3 — Governance Enforcement Binding

**Timeline:** Weeks 5–6
**Goal:** Prove that all blocking rules are enforceable.

## Objectives

* Map every blocking rule to runtime enforcement.

## Deliverables

### 1. Rule → Engine → Code Map

Traceability document linking:

* Rule ID
* Enforcement engine
* Code location
* Test coverage

### 2. Governance Coverage Command

New command:
`core-admin governance coverage`

Reports:

* % blocking rules enforced
* % reporting rules monitored
* Unbound rules

### 3. Strict Mode Toggle

Modes:

* Advisory
* Strict

Strict mode fails on first blocking violation.

### 4. Unit Tests for Critical Blocking Rules

Minimum:

* 5 highest-risk blocking rules
* Deterministic failure tests

## Expected Impact

+0.8 commercial readiness score
Transforms governance from documentation to compliance.

---

# Phase 4 — Installation & Bootstrap Hardening

**Timeline:** Week 7
**Goal:** Make CORE reproducibly installable.

## Objectives

* Single-environment validation
* Minimal onboarding friction

## Deliverables

### 1. Doctor Command

New command:
`core-admin doctor`

Validates:

* Database connectivity
* Vector DB connectivity
* Required environment variables
* Schema version alignment

### 2. Environment Schema Validation

* `.env.schema` file
* Fatal error on missing required values

### 3. 10-Minute Quickstart Guide

* Minimal install instructions
* Verified working path

### 4. Reference docker-compose.yml

* Optional but reproducible setup

## Expected Impact

+0.7 commercial readiness score
Reduces operational friction.

---

# Phase 5 — Stability & Versioning Contract

**Timeline:** Week 8
**Goal:** Establish upgrade safety.

## Objectives

* Define compatibility rules
* Prevent breaking upgrades

## Deliverables

### 1. Semantic Versioning Policy

Define:

* Major
* Minor
* Patch

### 2. Deprecation Mechanism

* Warning phase
* Removal phase
* Enforcement timeline

### 3. Intent Schema Versioning

* Version tag in `.intent`
* Migration validation

### 4. Upgrade Safety Check

`core-admin upgrade-check`

Validates:

* Schema compatibility
* Breaking rule changes

## Expected Impact

+0.5 commercial readiness score
Improves long-term trust.

---

# What This Roadmap Explicitly Avoids

* No new feature expansion
* No architectural redesign
* No performance optimization
* No infrastructure scaling
* No community push

Focus: Hardening, determinism, trust.

---

# Estimated Score Evolution

| Phase     | Score Gain |
| --------- | ---------- |
| Phase 1   | +0.8       |
| Phase 2   | +1.0       |
| Phase 3   | +0.8       |
| Phase 4   | +0.7       |
| Phase 5   | +0.5       |
| **Total** | **+3.8**   |

Projected Commercial Readiness:
**5.8 → ~8.2**

---

# Final Note

CORE does not lack intelligence.
CORE lacks industrial tightening.

This roadmap is about discipline, not expansion.

When complete, CORE transitions from:

> Advanced Research Platform

To:

> Governed AI Runtime System ready for serious evaluation.

---
