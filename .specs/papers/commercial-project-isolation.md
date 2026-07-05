# Commercial Project Isolation

**Status:** Draft
**Date:** 2026-06-27
**Scope:** All commercial projects under `.specs/commercial/`

---

## 1. The Problem

CORE is an open-source engine. Its value is the machinery: the audit engines, the blackboard, the constitutional enforcement runtime, the human approval gate. None of that is domain-specific.

Commercial projects bring domain content: regulation-specific rules, LLM prompts calibrated to an industry, connectors to external systems, customer-specific `.intent/` configurations. That content is not CORE — it is IP that belongs to a specific engagement.

The pollution problem occurs when commercial content has no designated home and drifts into CORE's own directories — a GxP catalog entry lands in `var/prompts/`, a regulation-specific rule appears in `enforcement_catalog.yaml`, a Vault connector ships inside `src/`. CORE's open-source boundary becomes undefined. Commercial IP becomes inadvertently public. And the engine starts accumulating assumptions about domains it should know nothing about.

The absence of an explicit isolation contract is the root cause. This paper establishes that contract.

---

## 2. What is a Commercial Project

A commercial project is an engagement where CORE's engine is deployed to govern a domain that is not software development. It has a customer, a regulatory or operational context, and a body of domain content that CORE enforces against.

A commercial project is NOT a fork of CORE. It does not modify the engine. It does not contribute back to CORE's `.intent/`. It is a consumer of CORE — it brings its own constitution, its own rules, its own artifacts, and runs them through machinery it did not build and does not own.

In CORE's terminology: the engine is the factory; the commercial project is the blueprint set the factory runs against.

Each commercial project has two representations:
- **Spec side** — the human-readable record of what the project is, what it requires, what was decided, and why. Lives under `.specs/commercial/projects/<project-id>/`.
- **Runtime side** — the artifacts CORE actually loads and executes against at runtime: the project's `.intent/`, catalogs, prompts, connectors. Lives outside CORE's own directories.

A project is identified by a short ID in the format `PROJ-YY.NNN` (year + zero-padded counter). That ID is the handle that links spec side to runtime side.

---

## 3. Two Surfaces

CORE owns the engine. A commercial project owns the content. These two surfaces must never blur.

**What CORE owns:**
- The runtime machinery — engines, blackboard, workers, audit pipeline, human approval gate
- The schema contract — what a valid `.intent/` looks like, what a valid catalog entry looks like
- The BYOR machinery floor — the onboarding tooling that lets a project bootstrap its runtime side
- `examples/starter-intent/` — the reference implementation of the schema contract

CORE does not own any domain knowledge. It does not know what 21 CFR Part 11 is. It does not know what a SOP is. It knows how to run engines against rules it is handed.

**What a commercial project owns:**
- Its `.intent/` — the constitution for its specific domain
- Its rule catalog — the regulation-specific checks (regex patterns, LLM prompts, attestation flags)
- Its prompt templates — calibrated to its domain and customer context
- Its connectors — adapters to external systems (Veeva Vault, SharePoint, etc.)
- Its outputs — reports, compliance exports, audit trails produced by running the engine
- Its spec — requirements, decisions, papers, demo plans, contact records

None of the project's content may live in CORE's directories. None of CORE's machinery may be modified to accommodate a project's domain.

The test is simple: if removing a commercial project from the runtime leaves CORE's own directories unchanged, the boundary is clean.

---

## 4. Runtime Contract

CORE must be able to load and execute a commercial project's artifacts without those artifacts being embedded in CORE's own directories — and without CORE having any hardcoded knowledge of which projects exist.

The contract has three parts:

**Discovery** — CORE finds a project's runtime home via configuration, not hardcoding. A project registers itself by pointing CORE at its runtime root. CORE does not scan for projects; it is told where to look.

**Schema compliance** — the project's artifacts must conform to CORE's published schema. CORE validates on load. If a catalog entry or `.intent/` file fails schema validation, CORE rejects it — it does not adapt to accommodate it. The schema is the only coupling point between CORE and a project.

**No callbacks** — a project's content may not modify CORE's behavior beyond what the schema permits. A catalog entry cannot introduce new engine types. A project `.intent/` cannot override CORE's own constitution. The engine is inert to everything outside the schema contract.

The practical consequence: deploying a new commercial project means pointing CORE at a new runtime root and providing schema-compliant artifacts. Nothing in CORE changes.

---

## 5. Isolation Rule

One rule, no exceptions:

> If an artifact was introduced because of a commercial project, it lives in that project's home. It does not touch CORE.

Concretely — the following may NEVER happen:

- A regulation-specific rule entry added to `var/prompts/` or any file under `src/`
- A customer's catalog content committed to the CORE repository
- A connector built for a specific customer living under `src/body/` or anywhere in CORE's source tree
- A prompt template written for a specific domain landing in CORE's prompt directories
- A project-specific `.intent/` entry appearing in CORE's own `.intent/`

The contamination test: check out CORE's repository on a machine with no commercial projects configured. If any commercial project's fingerprint is visible — a rule, a prompt, a catalog entry, a connector stub — the boundary has been violated.

The development discipline: before creating any artifact for a commercial project, ask *"would this exist if this project didn't exist?"* If no — it belongs in the project home, not CORE.

CORE's own `enforcement_catalog.yaml`, `var/prompts/`, and `.intent/` are strictly self-referential — they govern CORE's own development and nothing else.

---

## 6a. Commercial META Structure

`.specs/commercial/` is the top-level home for all commercial reasoning. It mirrors the structure CORE uses for its own architectural thinking.

```
.specs/commercial/
  papers/              — cross-project reasoning, patterns, isolation contracts
  decisions/           — ADRs that apply across all commercial projects
  projects/
    PROJ-26.001/       — first commercial project (pharma pilot)
    PROJ-26.002/       — future project
    ...
  CORE-*.md            — market, GTM, positioning documents
  cadence.md
```

**`papers/`** contains reasoning that applies to all commercial projects — including this document. When a question arises that no single project owns (how does isolation work, what is a project, how does CORE find runtime artifacts), the answer is worked out here first, then recorded as a decision.

**`decisions/`** contains ADRs scoped to the commercial layer. Same format as `.specs/decisions/` — problem, options, decision, consequences. These are the durable anchors that prevent the same question from being re-litigated per project.

Neither `papers/` nor `decisions/` contains anything project-specific. They are the commercial constitution — the rules that all projects inherit.

The existing `CORE-*.md` files (business model, GTM, personas, competitive) stay at the top level. They are not project-specific and not decision records — they are reference documents for the commercial layer as a whole.

---

## 6b. Per-Project Directory Structure

Each project has two sides: spec and runtime. Both are organized under the project ID.

**Spec side** — lives in `.specs/commercial/projects/PROJ-YY.NNN/`:

```
PROJ-YY.NNN/
  _overview.md         — status tracker, summary, key contacts
  requirements.md      — what the customer needs
  product-position.md  — how CORE fits in their stack
  gaps-and-build.md    — what exists, what needs building
  demo-plan.md         — demo critical path
  papers/              — project-specific reasoning
  decisions/           — project-specific ADRs
```

**Runtime side** — lives outside CORE, in a dedicated project runtime root:

```
PROJ-YY.NNN/
  .intent/             — project's domain constitution
  catalogs/            — regulation-specific rule catalogs
  prompts/             — domain-calibrated prompt templates
  connectors/          — adapters to external systems (Vault, SharePoint, etc.)
  outputs/             — gap analysis reports, compliance exports, audit trails
```

The runtime side is never committed to the CORE repository. It is the project's own repository — or a gitignored directory — that CORE is pointed at via configuration.

The spec side IS committed to CORE — it is documentation, not domain content. It contains no rules, no prompts, no catalogs. It describes what the runtime side contains and why.

Outputs are ephemeral relative to the source artifacts — they are produced by running the engine, not authored by hand. They may be delivered to the customer (PDF exports, signed reports) but are never committed back to CORE.

---

## 7. Instantiation Pattern

Creating a new commercial project follows a fixed sequence. The sequence is the contract made operational.

**Step 1 — Assign an ID.** Next available `PROJ-YY.NNN`. Increment the counter, use the current year.

**Step 2 — Create the spec side.** Copy the project template from `.specs/commercial/projects/_template/` into `.specs/commercial/projects/PROJ-YY.NNN/`. Fill `_overview.md`, `requirements.md`. Leave `papers/` and `decisions/` empty until reasoning is needed.

**Step 3 — Create the runtime root.** Outside the CORE repository. Initialize with the BYOR machinery floor via `core-admin project onboard`. This produces a skeleton `.intent/`, empty `catalogs/`, `prompts/`, `connectors/`, `outputs/`.

**Step 4 — Register with CORE.** Point CORE at the runtime root via configuration. CORE discovers nothing on its own — it must be told.

**Step 5 — Author domain content.** Populate catalogs, prompts, `.intent/` in the runtime root. Nothing goes into CORE. When reasoning is needed, write a paper under `PROJ-YY.NNN/papers/`. When a decision is made, record it under `PROJ-YY.NNN/decisions/`.

**Step 6 — Verify isolation.** Run the contamination test from Section 5. CORE's own directories must be unchanged from before Step 1.
