# CORE Workflow Catalog — Canonical Workflow Layer

This document defines the **CORE Workflow Catalog**: a finite set of named workflows, each with a clear trigger, inputs, steps, outputs, and governance gates.

This catalog is intended to remain **stable and auditable** over time. Implementations may split, rename, or combine CLI commands; however, those implementations should be mapped back to these canonical workflow IDs.

---

## CORE Workflow Catalog

### A. Governance and Constitution Workflows

#### 1. Bootstrap Governance

* **Purpose:** Start CORE with a single authority root (constitution path) and load governance state.
* **Trigger:** process start / CLI start
* **Inputs:** `ConstitutionPath` from Settings
* **Steps:** load constitution → validate schema → build policy index → publish read-only interface
* **Outputs:** Governance API ready; policy registry; schema registry

#### 2. Validate Constitution

* **Purpose:** Prove the constitution is structurally valid and internally consistent.
* **Trigger:** manual / CI
* **Inputs:** constitution files
* **Steps:** schema validation → required fields → cross-reference checks → rule IDs uniqueness
* **Outputs:** validation report (pass/fail + diagnostics)

#### 3. Generate Governance Coverage Map

* **Purpose:** Compute “declared vs enforced” rules coverage.
* **Trigger:** `governance coverage` / CI
* **Inputs:** constitution policies + enforcement evidence index (checks, code links)
* **Steps:** parse rules → map to enforcing checks → compute enforcement ratio
* **Outputs:** coverage map artifact + summary

#### 4. Run Governance Audit

* **Purpose:** Run all governance checks against codebase/config.
* **Trigger:** `governance audit` / CI gate
* **Inputs:** codebase + constitution + coverage map (optional)
* **Steps:** enumerate checks → execute → aggregate → severity thresholds
* **Outputs:** audit report; exit code for CI

#### 5. Enforce Domain Boundary

* **Purpose:** Prevent work outside authorized scope (IntentGuard style).
* **Trigger:** before workflow execution / before agent execution
* **Inputs:** workflow request + intent boundary rules
* **Steps:** resolve scope → verify allowed domains → block or allow
* **Outputs:** allow/deny + rationale

---

### B. Intent and Contract Workflows

#### 6. Load Intent Bundle

* **Purpose:** Load `.intent/` as governed facts (read-only).
* **Trigger:** bootstrap; CLI; refresh
* **Inputs:** constitution root → intent paths
* **Steps:** locate documents → parse → normalize → cache
* **Outputs:** in-memory intent model / index

#### 7. Validate Intent Bundle

* **Purpose:** Enforce schemas for intent artifacts (policies, tags, roles, bundles).
* **Trigger:** CI; dev sync; governance audit step
* **Inputs:** intent bundle + schemas
* **Steps:** schema validation → referential integrity → required metadata checks
* **Outputs:** structured validation results

#### 8. Refresh Intent Cache

* **Purpose:** Detect changes and refresh derived indexes safely.
* **Trigger:** manual; file watcher; scheduled
* **Inputs:** intent folder state
* **Steps:** diff → reload → re-validate → publish new snapshot
* **Outputs:** new “intent snapshot id” + changelog

---

### C. Development Synchronization Workflows

#### 9. Dev Sync (Read)

* **Purpose:** Pull derived governance/dev artifacts into a local workspace (without mutation).
* **Trigger:** `core-admin dev sync`
* **Inputs:** repo state; governance state; tooling outputs
* **Steps:** compute deltas → generate artifacts → stage results
* **Outputs:** updated local artifacts; summary

#### 10. Dev Sync (Write)

* **Purpose:** Update tracked artifacts deterministically (explicit write mode).
* **Trigger:** `core-admin dev sync --write`
* **Inputs:** same as above + explicit permission
* **Steps:** generate → validate → write → re-audit (recommended)
* **Outputs:** committed-ready changes

---

### D. Code Quality and Introspection Workflows

#### 11. Static Code Analysis

* **Purpose:** AST-level understanding of codebase for governance and refactoring.
* **Trigger:** `core-admin analyze` / CI
* **Inputs:** source tree
* **Steps:** AST parse → symbol extraction → metrics → smells
* **Outputs:** analysis_results.json (or equivalent)

#### 12. Naming Convention Check

* **Purpose:** Enforce naming rules and structural conventions.
* **Trigger:** `check-naming`
* **Inputs:** source tree + naming rules
* **Steps:** scan → detect violations → produce fixes suggestions
* **Outputs:** violations report

#### 13. Duplicate Detection

* **Purpose:** Detect duplicate functions/blocks for dedup pipeline.
* **Trigger:** `detect-duplicates`
* **Inputs:** source tree
* **Steps:** AST canonicalization → similarity grouping → emit groups
* **Outputs:** duplicate groups artifact

#### 14. Generate Documentation

* **Purpose:** Produce structured docs from code and intent.
* **Trigger:** `generate-docs`
* **Inputs:** intent + manifest + codegraph
* **Steps:** extract → assemble → validate against templates
* **Outputs:** docs artifacts

---

### E. Proposal Governance Workflows (Work/Proposals)

#### 15. Proposal Create

* **Purpose:** Create a governed proposal artifact for change.
* **Trigger:** CLI “proposal create”
* **Inputs:** problem statement + scope + owner metadata
* **Steps:** template instantiation → schema validate → register
* **Outputs:** proposal file in proposals area

#### 16. Proposal Review

* **Purpose:** Run policy checks + quality gates on a proposal.
* **Trigger:** “proposal review”
* **Inputs:** proposal + constitution policies
* **Steps:** validate → policy gate evaluation → required sections check
* **Outputs:** approve/reject + findings

#### 17. Proposal Apply

* **Purpose:** Apply an approved proposal into code/config.
* **Trigger:** “proposal apply”
* **Inputs:** approved proposal + repository state
* **Steps:** execute atomic actions → validate → run audit
* **Outputs:** applied change set + trace

---

### F. Agent and Execution Workflows (Will → Body via SRC)

#### 18. Plan Task

* **Purpose:** Turn intent + context into a bounded plan.
* **Trigger:** user request / autonomous trigger
* **Inputs:** goal + intent + context package
* **Steps:** scope check → capability mapping → plan graph
* **Outputs:** execution plan artifact

#### 19. Execute Task (Atomic Actions)

* **Purpose:** Execute a plan via atomic actions.
* **Trigger:** plan approved
* **Inputs:** plan + tool registry + policy gates
* **Steps:** pre-checks → run action → validate result → record trace
* **Outputs:** result + trace + persisted state

#### 20. Self-Healing / Fix Loop

* **Purpose:** Detect issues (audit failures, validation errors) and propose/apply safe fixes.
* **Trigger:** failed audit/validation; scheduled health check
* **Inputs:** failure report + code context + policies
* **Steps:** classify → propose fix → validate → apply → re-run audit
* **Outputs:** fix PR/patch + updated health status

---

### G. Knowledge and Memory Workflows (DB + Vector)

#### 21. Index Artifacts to Vector

* **Purpose:** Embed and store governed documents/code snippets for retrieval.
* **Trigger:** on intent refresh; on doc updates
* **Inputs:** canonical text items + embedding capability
* **Steps:** chunk → embed → upsert vectors → store lineage in DB
* **Outputs:** vector index updated + provenance links

#### 22. Retrieve Context

* **Purpose:** Build retrieval-augmented context packages.
* **Trigger:** before reasoning/generation
* **Inputs:** query + scope + vector index
* **Steps:** search → filter by scope → assemble context bundle
* **Outputs:** bounded context package

---

## Making This Catalog Authoritative

To turn this catalog into the definitive list of “workflows CORE knows/uses”, CORE needs a single canonical source of truth.

Two viable approaches exist:

1. **Workflows are defined in Constitution** (YAML) and loaded via `ConstitutionInterface`.
2. **Workflows are defined in the CLI registry / code manifest** and audited against the Constitution.

---

## Workflow Definition Template (Minimal)

When instantiating workflows as first-class governed objects, each workflow should define at least:

* `id`
* `name`
* `purpose`
* `trigger`
* `inputs`
* `preconditions` (policy gates)
* `steps` (high-level, not implementation)
* `outputs`
* `artifacts` (files/records produced)
* `telemetry` (trace evidence)
* `failure_modes`

---

## Notes

* This catalog is a **canonical semantic layer**.
* CLI commands and internal implementations should be mapped to these IDs.
* The catalog is expected to evolve only through governed change control (proposal → review → approval → activation).
