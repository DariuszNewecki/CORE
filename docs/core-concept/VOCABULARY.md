# CORE Vocabulary

**Version:** v1.0.0  
**Status:** Active  
**Scope:** CORE System (Mind, Body, Will)  
**Authority:** Normative  

---

## 1. Core System Model

### CORE
The self-governing system that enforces architectural, governance, and behavioral rules over its own codebase and AI agents.

### Mind (The Conscience)
The authority and memory layer. It consists of:
- The **Constitution** (immutable files in `.intent/`)
- The **Knowledge Graph** (Postgres database)

The Mind defines what is *true* and what is *allowed*.

### Body (The Execution)
The deterministic execution layer (`src/`). It contains concrete implementations such as:
- CLI commands  
- Services  
- Atomic Actions  

The Body must be **headless** (no UI) and **stateless** (no hidden memory).

### Will (The Agency)
The autonomous reasoning layer (`src/will/`). It consists of Agents that:
- Perceive context  
- Reason about goals  
- Orchestrate Body actions  

The Will may propose intent, but **only the Mind can validate it**.

---

## 2. Intent & Governance

### Intent
A formal declaration of a desired state or rule.

### Constitution
The highest-authority intent set (`.intent/charter/constitution/`).  
It establishes the fundamental laws of the system. Constitutional rules are **non-negotiable** and **immutable** without a formal amendment process.

### Policy
A governance document (`.intent/charter/standards/`) defining specific rules for code, data, or operations.  
Policies are enforced mechanically by Auditors.

### Crate (Intent Crate)
A transactional package of changes proposed by an Agent.  
A crate must pass validation (**Schema**, **Canary**, **Audit**) before being merged into the codebase.

---

## 3. Domain & Scope

### Domain
A strict architectural boundary that groups related Capabilities.

In the Body implementation, a Domain maps **1:1** to a directory:
src/features/<domain_name>/

### Infrastructure
Code providing cross-cutting utility (`src/shared/`, `src/services/`) without business logic.  
Infrastructure is **exempt from Domain assignment**.

### Trust Zone
A security boundary defining where dangerous execution primitives (e.g. `eval`, `exec`) are permitted  
(e.g. `system`, `privileged`, `application`).

---

## 4. Identity & Meaning

### ID (Capability ID)
A unique UUID (e.g. `# ID: 1234...`) tagged in source code.  
Transforms a raw Symbol into a governed Capability.

### Symbol
A raw code entity (Function, Class, Module) discovered by scanning the codebase.  
A Symbol exists in the Body but is not *known* to the Mind until tagged and synced.

### Capability
A Symbol explicitly claimed by a Domain via an ID.  
Capabilities are the units of business logic tracked in the Database SSOT.

### Anchor
A stable reference point (usually a UUID comment) allowing the Knowledge Graph to maintain links to code even if files are renamed or moved.

---

## 5. Structure & Behavior

### Service
A stateless infrastructure component that manages resources (DB, Vector Store, LLM).  
Services must be **headless** and use **Dependency Injection**.

### Atomic Action
A discrete, governed unit of work that returns a structured `ActionResult`.  
Atomic Actions are the **only** way Agents (Will) may modify the System (Body).

### Orchestrator
A component that composes multiple Atomic Actions into a workflow.  
Orchestrators own the **User Interface (UI)** and progress reporting.

---

## 6. Enforcement & Compliance

### SSOT (Single Source of Truth)
The definitive record of state:
- **Logic:** Filesystem (`src/`)
- **Metadata & Relationships:** Database (Postgres)
- **Law:** Constitution (`.intent/`)

### Drift
A discrepancy between the Mind (Database / Constitution) and the Body (Filesystem).

Examples:
- A Domain defined in YAML but missing in `src/features/`
- A Function existing in code but missing its Capability ID in the DB

### Audit
The mechanical process of comparing the Body against the Mind to detect Drift or Violations.

---

## 7. Assignment & Authority Matrix

This table defines the source of authority for system elements.

| Element        | Authority (Who Defines It) | Storage (Where it Lives) |
|---------------|----------------------------|--------------------------|
| Constitution  | Human (Founder)             | `.intent/charter/constitution/*.yaml` |
| Domain        | Human (Architect)           | `.intent/mind/knowledge/domain_definitions.yaml` + `src/features/` |
| Policy        | Human (Governance)          | `.intent/charter/standards/*.yaml` |
| Capability    | Human or Agent (Proposer)   | Code (`# ID:` tag) + Database (`core.capabilities`) |
| Symbol        | Code (Parser)               | Database (`core.symbols`) |
| Vector        | System (Derived)            | Qdrant (`core_capabilities` collection) |
| Action Log    | System (Runtime)            | Database (`observability.logs`) |

---

## Conceptual Summary

- **Domains are Directories**  
  If it is not in `src/features/<name>`, it is not a Domain.

- **Database is the Mind**  
  If a function is not synced to the DB, the System does not know it exists.

- **IDs Create Reality**  
  A Symbol becomes a Capability only when it receives a UUID.

- **Agents Are Constrained**  
  The Will can only act through Atomic Actions defined by the Body.
