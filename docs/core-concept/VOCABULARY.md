# CORE Vocabulary

**Version:** v0.3
**Status:** Draft
**Scope:** CORE system only (including `.intent/`)
**Authority:** Descriptive (non‑normative)

---

## 1. Core System Model

### CORE

The self‑governing system that enforces architectural, governance, and behavioral rules over its own codebase and AI agents.

### Mind

The declarative authority layer of CORE. It defines what is allowed, required, or forbidden and is implemented primarily through the `.intent/` directory.

### Body

The deterministic execution layer of CORE. It contains the concrete implementation (`src/`) that executes logic strictly within constraints defined by the Mind.

### Will

The autonomous reasoning and action layer of CORE. It may propose or initiate actions, but can never bypass the Mind and never execute outside the Body.

---

## 2. Intent & Governance

### Intent

A formal, machine‑readable declaration of rules, standards, policies, or goals that govern CORE behavior.

### Constitution

The highest‑authority intent set in CORE. Constitutional intents are non‑negotiable and override all other intents and implementations.

### Charter

A structured collection of intents grouped by authority and purpose (e.g. constitution, standards, patterns).

### Standard

An intent that defines mandatory structure, format, or behavior within a defined scope.

### Policy

An intent that expresses governance decisions, obligations, or prohibitions, typically higher‑level than standards.

### Pattern

An intent that defines an approved structural or behavioral solution to a recurring problem.

---

## 3. Domain & Scope

### Domain

A bounded semantic and governance area within CORE.

A domain:

* Defines what a set of intents, code, or capabilities is about
* Establishes scope boundaries
* Prevents rule leakage across unrelated areas

Domains are used consistently across `.intent/`, symbols, enforcement logic, and documentation.

---

## 4. Identity & Meaning

### ID

A unique, stable identifier used to reference a specific entity unambiguously.

IDs are:

* Mechanical, not semantic
* Globally unique within their namespace
* Used for traceability, versioning, and enforcement

IDs do not carry meaning.

### Symbol

A stable, named semantic unit used to anchor meaning across intents, code, and documentation.

Symbols:

* Represent meaning, not identity
* May be shared across artifacts
* Are used to express concepts, capabilities, or guarantees

A symbol is not an ID.

### Capability

A named ability or function that CORE provides or enforces. Capabilities describe what CORE can or must do, not how it is implemented.

---

## 5. Structure & Behavior

### Feature

A coherent, user‑ or system‑facing capability implemented by CORE. A feature may span multiple commands and functions and often maps to one or more capabilities.

### Command

A discrete, invokable operation exposed by the CORE CLI. Commands are user‑facing and orchestrate logic without containing core business rules.

### Function

A deterministic unit of executable logic with a single responsibility. Functions are implementation‑level constructs and are not user‑facing.

### Atomic Action

A minimal, deterministic operation with exactly one responsibility and a strict execution contract. Atomic actions produce no uncontrolled side effects and perform no terminal I/O.

---

## 6. Enforcement & Compliance

### Enforcement

The mechanical verification and constraint of behavior based on declared intents.

### Rule

An individual enforceable statement within an intent.

### Violation

A detected breach of a rule during inspection, validation, or execution.

### Coverage

A measurable indication of how completely intents are enforced by concrete checks or guards.

---

## 7. Knowledge & Authority

### SSOT (Single Source of Truth)

The authoritative origin of a fact, rule, or definition within CORE.

SSOTs:

* Are explicitly declared
* Are authoritative and auditable
* Override all derived or inferred knowledge

### Vector

A structured numerical representation of meaning used for semantic comparison, clustering, and retrieval.

Vectors:

* Represent derived meaning, not authority
* Are generated from SSOTs
* Are regenerable and non‑authoritative

Vectors never override SSOTs.

### Knowledge

Structured or derived understanding CORE has about itself, including rules, symbols, domains, and system state.

### Drift

A detectable divergence between declared intent (Mind / SSOT) and actual implementation or behavior (Body / Will).

---

## 8. Assignment & Authority Matrix

The table below clarifies **who assigns or defines each element** in CORE. This avoids ambiguity between human governance, system generation, and derived artifacts.

| Element       | Assigned / Defined By             | Notes                                               |
| ------------- | --------------------------------- | --------------------------------------------------- |
| Domain        | Human (Architecture / Governance) | Declared explicitly; foundational scoping construct |
| ID            | System or Human (at creation)     | Must be unique; mechanical, non-semantic            |
| Symbol        | Human (Intent authors)            | Semantic anchor; may be reused across artifacts     |
| Capability    | Human (Design / Governance)       | Expresses what CORE provides or enforces            |
| Intent        | Human (Governance)                | Authoritative declaration                           |
| Constitution  | Human (System owner)              | Highest authority                                   |
| Charter       | Human (Governance)                | Organizes intents by authority                      |
| Standard      | Human (Governance)                | Mandatory rules within scope                        |
| Policy        | Human (Governance)                | Obligations and prohibitions                        |
| Pattern       | Human (Architecture)              | Approved solution form                              |
| Feature       | Human (Design)                    | Groups related behavior                             |
| Command       | Human (CLI design)                | User-facing invocation                              |
| Function      | Human (Implementation)            | Deterministic logic unit                            |
| Atomic Action | Human (Architecture)              | Minimal execution primitive                         |
| Rule          | Human (Intent authors)            | Enforceable statement                               |
| Enforcement   | System (Body)                     | Mechanical verification                             |
| Violation     | System (Body)                     | Detected breach                                     |
| Coverage      | System (Body)                     | Measured enforcement extent                         |
| SSOT          | Human or System (Declared)        | Authoritative by designation                        |
| Vector        | System (Derived)                  | Generated from SSOTs; non-authoritative             |
| Knowledge     | System (Derived)                  | Aggregated understanding                            |
| Drift         | System (Detected)                 | Mind–Body divergence indicator                      |

---

## Conceptual Summary

* **ID** answers *which exact thing*
* **Symbol** answers *what it means*
* **Domain** answers *where it belongs*
* **SSOT** defines *what is true*
* **Vectors** help navigate meaning, never authority
