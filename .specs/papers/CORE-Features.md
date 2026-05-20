# CORE: Feature Registry

**Document type:** Strategic reference
**Location:** `.specs/papers/CORE-Features.md`
**Status:** Authoritative
**Author:** Dariusz Newecki
**Audience:** Internal — product, commercial, investor

---

## 1. Purpose

This document is the canonical flat inventory of CORE capabilities. It is the
source-of-truth vocabulary that tier packaging references. Tier definitions
describe which features are included at each level; this document defines what
each feature is.

Features are grouped by domain. Each entry carries a status and a scope
indicating whether it is shipping in the current Solo reference implementation
or on the roadmap, and whether it is an artifact-agnostic primitive or a
source-code instantiation of that primitive.

**Status values:**

| Value | Meaning |
|---|---|
| `shipping` | Implemented and active in CORE Solo (current reference implementation) |
| `roadmap` | Designed; not yet implemented |
| `partial` | Foundational work exists; full capability not yet complete |

**Scope values:**

| Value | Meaning |
|---|---|
| `primitive` | Artifact-agnostic. Operates identically regardless of what kind of artifact is being governed. |
| `source-code instantiation` | Current implementation of the primitive, scoped to source code. Does not limit the primitive's generality. |
| `extension` | Extends a primitive to a new artifact type or deployment context. |

---

## 2. Primitive vs. Instantiation

CORE's positioning claim is:

> *CORE is a constitutionally-governed governance runtime. It enforces declared
> law over any artifact-producing process — not just software, but
> documentation, compliance artifacts, regulated process outputs, or any system
> where decisions must be traceable, defensible, and attributed.*

This claim rests on a structural distinction that the feature registry makes
explicit.

**Governance primitives** are artifact-agnostic. The rule engine, consequence
chain, phase discipline, Blackboard, worker model, proposal engine, and
convergence metric do not know what kind of artifact they are governing. They
operate on declared rules, typed findings, and attributed actions — none of
which are source-code concepts. These primitives could govern a regulatory
document, a clinical trial record, a maintenance procedure, or a software
module with equal structural validity.

**Source-code instantiations** are the first governed artifact type. The
default rule library, the audit sensor, the atomic action registry, and the
vector indexer are currently scoped to source code. They are the reference
implementation of the governance primitives against the first artifact domain.
They are not the definition of CORE's scope.

**Artifact-type extensibility** (F-41 through F-43) is the roadmap work that
makes the distinction operationally real. Until those features exist, governing
a non-code artifact type requires custom implementation against the primitives.
The primitives support it; the product does not yet abstract it.

The primitives that are shipping today:

| Feature | Name |
|---|---|
| F-01 | Constitutional rule engine |
| F-02 | Constitutional authority hierarchy |
| F-03 | Phase discipline |
| F-04 | Constitution authoring (`.intent/` layer) |
| F-06 | PathResolver / canonical path registry |
| F-09 | Audit finding persistence |
| F-13 | Autonomous remediation loop |
| F-14 | Proposal engine |
| F-15 | Governor approval interface |
| F-16 | Confidence floor enforcement |
| F-17 | Full consequence chain |
| F-19 | Convergence metric |
| F-21 | Daemon runtime |
| F-22 | Worker declaration model |
| F-23 | Blackboard coordination ledger |
| F-24 | Worker health monitoring |

---

## 3. Feature Registry

### 3.1 Constitutional Governance

All features in this domain are governance primitives — artifact-agnostic by design.

---

<a id="F-01"></a>
**F-01 — Constitutional rule engine**
Status: `shipping` | Scope: `primitive`

A deterministic rules engine that evaluates any governed artifact against a set
of rules declared in `.intent/rules/`. Rules are YAML or JSON documents. Each
rule declares its authority level (`constitutional` or `policy`), enforcement
strength (`advisory`, `required`, or `blocking`), and the phase in which it
applies. The engine does not interpret rules; it applies them exactly as
declared.

Rules make no assumption about artifact type. A rule may govern a source file,
a document, a process record, or any structured artifact — the engine does not
distinguish. Artifact-type awareness belongs in the sensor (F-42), not the
rule engine.

---

<a id="F-02"></a>
**F-02 — Constitutional authority hierarchy**
Status: `shipping` | Scope: `primitive`

Two-tier authority model: Constitutional (highest) and Policy. Constitutional
rules require dual-key amendment. Policy rules are governed by the current
governor. No AI component can create, modify, or suppress a rule at either
authority level. Rule authority is declared, not inferred.

---

<a id="F-03"></a>
**F-03 — Phase discipline**
Status: `shipping` | Scope: `primitive`

Six strictly ordered governance phases: Interpret → Load → Parse → Audit →
Execute → Verify. Each phase has defined authority, permitted operations, and
entry conditions. No phase may operate on artefacts from a later phase. Phase
boundaries are governance boundaries, not performance optimisations.

---

<a id="F-04"></a>
**F-04 — Constitution authoring (`.intent/` layer)**
Status: `shipping` | Scope: `primitive`

The `.intent/` directory is the constitution of a governed repository. It
contains rules, worker declarations, phase definitions, enforcement mappings,
path registries, and remediation maps. All CORE governance reads from `.intent/`
at runtime. `.intent/` is human-authored and human-governed; CORE never writes
to it autonomously. This separation is architecturally non-negotiable.

---

<a id="F-05"></a>
**F-05 — Default rule library (source code)**
Status: `shipping` | Scope: `source-code instantiation`

A bundled set of governance rule_documents under `.intent/rules/`, organized
across eight categories: `ai`, `architecture`, `cli`, `code`, `data`,
`governance`, `infrastructure`, and `will`. The convergence target — the
specific rule_document set F-05 commits to enforcing for shipping status —
is declared in `.intent/enforcement/config/rule_targets.yaml`. F-05
transitions from `partial` to `shipping` when every listed rule_document
exists with `metadata.status == "active"`. Expanding the declared target is
a deliberate governor decision, not autonomous.

This library is the source-code instantiation of the rule primitive (F-01).
Rule libraries for other artifact types (documents, compliance records) are
a roadmap concern under F-41.

---

<a id="F-06"></a>
**F-06 — PathResolver / canonical path registry**
Status: `shipping` | Scope: `primitive`

A declared registry (`governance_paths.yaml`) mapping canonical logical paths
to filesystem locations. All CORE internals resolve paths through this registry.
Hardcoded paths in source code are a constitutional violation (ADR-031).
PathResolver is the mechanism that enforces that law.

---

### 3.2 Audit

---

<a id="F-07"></a>
**F-07 — Stateless constitutional audit**
Status: `shipping` | Scope: `source-code instantiation`

Point-in-time evaluation of a repository against its constitution. Produces a
structured finding set: rule violated, file, line number, severity, message.
Verdict is `PASS` or `FAIL`. Designed to run without daemon, database, or
workers — a single invocation against a governed artifact set.

Currently instantiated against source code. The stateless audit primitive
itself imposes no artifact-type constraint; that constraint lives in the sensor
and rule library.

---

<a id="F-08"></a>
**F-08 — Continuous audit (sensor-driven)**
Status: `shipping` | Scope: `source-code instantiation`

The `AuditViolationSensor` runs constitutional audit on a continuous daemon
cycle and posts findings to the Blackboard. Unlike the stateless audit, this
mode is persistent and feeds the autonomous remediation loop. Findings are
deduplicated by subject string across cycles.

Currently instantiated against source code. The pluggable sensor model (F-42)
is the roadmap work that makes this extensible to other artifact types.

---

<a id="F-09"></a>
**F-09 — Audit finding persistence**
Status: `shipping` | Scope: `primitive`

Findings are persisted to the Blackboard (PostgreSQL). Each finding carries:
rule ID, artifact identifier, location, severity, message, and status
(`open` → `claimed` → `resolved` / `abandoned`). The finding schema makes no
assumption about artifact type. Finding history is queryable.

---

<a id="F-10"></a>
**F-10 — CI/CD gate**
Status: `roadmap` | Scope: `source-code instantiation`

Stateless audit packaged as a GitHub Action, GitLab CI step, or pre-commit
hook. No daemon, database, or workers required. Findings reported as PR
annotations. Merge blocked on blocking-strength violations. This is the
Audit tier's primary delivery mechanism.

---

### 3.3 Autonomous Remediation

---

<a id="F-11"></a>
**F-11 — Remediation map**
Status: `shipping` | Scope: `source-code instantiation`

A declaration (`auto_remediation.yaml`) mapping rule IDs to Atomic Actions.
One rule maps to exactly one action. The RemediatorWorker reads this map to
route findings to the correct remediation handler. Routing is deterministic;
no LLM is involved.

Currently maps source-code rules to source-code actions. The map schema is
artifact-agnostic; the entries are not.

---

<a id="F-12"></a>
**F-12 — Atomic action registry (source code)**
Status: `shipping` | Scope: `source-code instantiation`

A registry of discrete, bounded remediation operations against source code.
Each action is independently testable, has a declared confidence level, and
declares which rule IDs it remediates. Currently active actions include:
`fix.format`, `fix.imports`, `fix.headers`, `fix.ids`, `fix.docstrings`,
`fix.logging`, `fix.placeholders`, `fix.duplicate_ids`, `fix.modularity`.
Actions at confidence >= 0.80 are auto-dispatched.

This is the source-code instantiation of the action model. The pluggable action
model (F-43) is the roadmap work that extends this to other artifact types.

---

<a id="F-13"></a>
**F-13 — Autonomous remediation loop**
Status: `shipping` | Scope: `primitive`

The closed-loop cycle: Finding detected → Proposal generated → Approval
received → Action executed → Verification audit run → New findings posted.
All six edges are attributed, persisted, and queryable. The loop structure
is artifact-agnostic; it operates on findings and actions regardless of what
artifact type produced them.

---

<a id="F-14"></a>
**F-14 — Proposal engine**
Status: `shipping` | Scope: `primitive`

The RemediatorWorker groups open findings by action and creates one Proposal
per unique action group. Proposals are persisted to the Blackboard. A Proposal
carries: proposed action, target artifacts, rationale, confidence, and status
(`pending` → `approved` / `rejected` → `executed` / `failed`). The proposal
schema is artifact-agnostic.

---

<a id="F-15"></a>
**F-15 — Governor approval interface (CLI)**
Status: `shipping` | Scope: `primitive`

Proposals queue in the Blackboard and are reviewed via `core-admin proposals`.
The governor approves or rejects. Approved proposals are dispatched to the
execution layer. The approval gate is a constitutional requirement; there is no
bypass. Approval operates on proposals, not on artifact type.

---

<a id="F-16"></a>
**F-16 — Confidence floor enforcement**
Status: `shipping` | Scope: `primitive`

A constitutional rule (`autonomy.remediation.min_confidence_floor`) sets the
minimum confidence required for auto-dispatch at 0.80. Entries below this
threshold are not dispatched regardless of any operational configuration.
Changing the threshold requires a rule amendment, not a config change.

---

### 3.4 Consequence Chain

---

<a id="F-17"></a>
**F-17 — Full consequence chain**
Status: `shipping` | Scope: `primitive`

A complete, attributed causal trace linking: Finding → Proposal → Approval →
Execution → Artifact changes → New findings. All six edges are persisted in
PostgreSQL and queryable in both directions. The consequence chain is CORE's
primary traceability artefact.

The chain is artifact-agnostic. Currently the "artifact changes" edge is
realised as git commits (F-18), which is the source-code instantiation. For
other artifact types, the execution edge would produce a different change
record — the chain structure remains identical.

---

<a id="F-18"></a>
**F-18 — Commit-level attribution**
Status: `shipping` | Scope: `source-code instantiation`

Each autonomous execution produces a commit whose message encodes the proposal
ID as a structured prefix (`fix(XXXXXXXX): …`). The `proposal_consequences`
table records the post-execution SHA. Forward and reverse lookups are supported
via both git log and DB query.

This is the source-code instantiation of the execution attribution edge in
F-17. Other artifact types would use a different change-record mechanism; the
`proposal_consequences` table schema is designed to accommodate this.

---

<a id="F-19"></a>
**F-19 — Convergence metric**
Status: `shipping` | Scope: `primitive`

The Blackboard records finding creation and resolution events over time.
Rate of resolution versus rate of creation is queryable. A governed artifact
set converging toward constitutional compliance has a resolution rate that
exceeds its creation rate. This is CORE's primary operational health metric,
and it is fully artifact-agnostic.

---

<a id="F-20"></a>
**F-20 — Convergence graph dashboard**
Status: `roadmap` | Scope: `primitive`

A web UI rendering the convergence metric as a time-series graph. Finding rate
versus resolution rate over time. The anchor feature for Team tier adoption.
Equally applicable to any governed artifact type.

---

### 3.5 Worker System

---

<a id="F-21"></a>
**F-21 — Daemon runtime**
Status: `shipping` | Scope: `primitive`

A persistent background process that runs governance workers on a continuous
cycle. Workers are discovered from `.intent/workers/*.yaml` declarations.
Worker lifecycle is governed: registration, heartbeat, claim, release,
abandon. The daemon is the autonomous governance engine and is fully
artifact-agnostic.

---

<a id="F-22"></a>
**F-22 — Worker declaration model**
Status: `shipping` | Scope: `primitive`

Workers are declared in `.intent/workers/*.yaml`, not instantiated in code.
A worker declaration specifies: name, class, schedule, capabilities required,
and enabled state. CORE discovers workers from declarations at daemon start.
A worker that has no declaration does not run. The declaration model is
artifact-agnostic; any worker operating on any artifact type uses it.

---

<a id="F-23"></a>
**F-23 — Blackboard coordination ledger**
Status: `shipping` | Scope: `primitive`

A PostgreSQL-backed shared state store. All inter-worker communication passes
through the Blackboard via typed entries: `finding`, `proposal`, `claim`,
`report`, `heartbeat`. No worker communicates directly with another. The
Blackboard is the single source of governance truth at runtime and carries
no artifact-type assumption.

---

<a id="F-24"></a>
**F-24 — Worker health monitoring**
Status: `shipping` | Scope: `primitive`

The BlackboardAuditor worker monitors worker registrations for stale claims
(SLA = 3600s) and orphaned heartbeats. Stale entries are flagged as abandoned.
Worker health state is queryable via `core-admin workers blackboard`.

---

<a id="F-25"></a>
**F-25 — Vector artifact indexing**
Status: `shipping` | Scope: `source-code instantiation`

The `repo_crawler` and `repo_embedder` workers crawl the repository on a
continuous cycle (~10 min), chunk source files into logical units, and embed
them into Qdrant vector collections (`core-code`, `core-docs`, etc.). The
vector index is used by AI components for context retrieval during generation
and remediation planning.

Currently instantiated against source code and documentation. Extensible to
other artifact types under F-41.

---

### 3.6 AI Integration

---

<a id="F-26"></a>
**F-26 — LLM integration (API)**
Status: `shipping` | Scope: `primitive`

CORE integrates with LLM providers via HTTP API. AI is used as a generation
component inside governance workers. AI output is never trusted; it is
verified against the constitution before execution. The integration surface
is provider-agnostic; the current Solo reference deployment routes to
Ollama-served local models (see F-27). The integration is artifact-agnostic;
AI can generate or transform any artifact type, subject to governance.

---

<a id="F-27"></a>
**F-27 — Local LLM support**
Status: `partial` | Scope: `primitive`

CORE supports Ollama-served local models. In the current Solo reference
deployment, local models are the default routing target; no external provider
traffic occurs unless explicitly configured. Provider selection is governed
by configuration; switching to an external API is opt-in.

---

<a id="F-28"></a>
**F-28 — Context builder**
Status: `shipping` | Scope: `source-code instantiation`

`shared/infrastructure/context/builder.py` assembles the governance context
packet passed to AI components before any generation task. Context includes:
relevant `.intent/` documents, source files, finding details, and prior
proposals. The context builder is the interface between the constitution and
the AI component. AI never reads `.intent/` directly.

Currently assembles context for source-code generation tasks. Extension to
other artifact types requires context builder support under F-41.

---

### 3.7 CLI Governance Interface

---

<a id="F-29"></a>
**F-29 — CLI governance surface**
Status: `shipping` | Scope: `primitive`

A full command-line interface (`core-admin`) covering 14 command groups:
`code`, `admin`, `database`, `vectors`, `dev`, `symbols`, `context`,
`proposals`, `constitution`, `workers`, `project`, `secrets`, `runtime`.
The CLI is the primary governor interface for Solo and the administrative
interface for all tiers. Proposal review, audit invocation, and worker
management are artifact-agnostic CLI operations.

---

<a id="F-30"></a>
**F-30 — Constitutional maintenance commands**
Status: `shipping` | Scope: `source-code instantiation`

`core-admin dev sync --write` performs constitutional maintenance: header
enforcement, ID assignment, formatting normalisation, DB sync, and vector
sync in a single pass. Currently scoped to source code maintenance operations.

---

### 3.8 Multi-User and Team Capabilities

---

<a id="F-31"></a>
**F-31 — Shared consequence chain (multi-user)**
Status: `roadmap` | Scope: `primitive`

All proposals, findings, and executions visible to every member of a shared
CORE instance. Governance state is team-level, not per-governor. Applies
equally to any governed artifact type.

---

<a id="F-32"></a>
**F-32 — Role-based constitutional authority (RBAC)**
Status: `roadmap` | Scope: `primitive`

Explicit governance over who can approve proposals and who can amend `.intent/`.
Role assignments are themselves governed artefacts. A team member without
amendment authority cannot modify the constitution — the system enforces it,
not convention.

---

<a id="F-33"></a>
**F-33 — Multi-repository support**
Status: `roadmap` | Scope: `primitive`

A single CORE instance governing multiple repositories. Each repository has its
own `.intent/` constitution; shared governance infrastructure (Blackboard,
workers, dashboard) is common.

---

<a id="F-34"></a>
**F-34 — Web dashboard**
Status: `roadmap` | Scope: `primitive`

Browser-based governance interface. Views: convergence graph (F-20), proposal
queue, audit history, worker health. Replaces CLI as the primary interface for
team governors who are not working in a terminal.

---

### 3.9 Enterprise and Regulated-Industry Capabilities

---

<a id="F-35"></a>
**F-35 — Federated constitution**
Status: `roadmap` | Scope: `primitive`

An org-level root constitution that team-level constitutions inherit and cannot
override. Teams can extend the root; they cannot weaken it. The root
constitution is the compliance floor. Applies to any governed artifact type.

---

<a id="F-36"></a>
**F-36 — SSO / SAML / OIDC**
Status: `roadmap` | Scope: `primitive`

Enterprise identity integration. Role assignments (F-32) bind to SSO identities.
Required for regulated-industry deployments where identity auditability is
mandatory.

---

<a id="F-37"></a>
**F-37 — Regulatory export (GxP / EU AI Act)**
Status: `roadmap` | Scope: `primitive`

Structured, signed export of the full consequence chain formatted for
regulatory submission. For GxP customers, the export IS the Change Control
record. For EU AI Act Article 9 audits, it IS the risk management record.
CORE does not replace the regulatory framework; it produces the evidence the
framework requires.

The export covers: finding → proposal → approval (with identity) → execution
→ artifact diff → verification audit verdict. Cryptographically signed.
Timestamped. Artifact-agnostic: the same export structure applies whether the
governed artifact is source code, a document, or a regulated process output.

---

<a id="F-38"></a>
**F-38 — Air-gapped deployment (guaranteed)**
Status: `roadmap` | Scope: `primitive`

Local-only LLM with no outbound network traffic. Governed artifacts never leave
the customer perimeter. Builds on F-27 but guarantees network isolation at the
infrastructure level rather than relying on configuration.

---

<a id="F-39"></a>
**F-39 — SLA support**
Status: `roadmap` | Scope: `primitive`

Contractual support SLA with defined response times. Not a software feature;
a commercial and operational commitment required for regulated-industry
procurement.

---

### 3.10 Platform / OEM

---

<a id="F-40"></a>
**F-40 — OEM API surface**
Status: `roadmap` | Scope: `primitive`

A stable, versioned API exposing the CORE enforcement engine to third-party
platforms (IDE plugins, AI coding platforms, DevSecOps tools, GitHub Apps).
The third-party product embeds CORE's governance layer without CORE being
visible as a separate product to end users.

Requires: FastAPI layer stabilised as a public contract; atomic action registry
as a published API; constitution schema versioned for external authors.

---

### 3.11 Artifact-Type Extensibility

These three features are the roadmap work that makes the primitive/instantiation
distinction operationally real for non-code artifact types. Until they exist,
governing a non-code artifact is possible but requires bespoke implementation
against the primitives. These features abstract that work into a declared,
supported model.

---

<a id="F-41"></a>
**F-41 — Artifact type registry**
Status: `roadmap` | Scope: `extension`

A declared model for registering governed artifact types beyond source code.
An artifact type declaration specifies: artifact schema, identity key format,
supported sensors, supported actions, and change-record mechanism. CORE
discovers registered artifact types at daemon start and routes governance
operations accordingly.

This is the enabling feature for governing documentation, compliance records,
regulated process outputs, or any structured artifact. Without it, non-code
governance requires custom wiring against the primitives directly.

---

<a id="F-42"></a>
**F-42 — Pluggable sensor model**
Status: `roadmap` | Scope: `extension`

An abstract sensor interface that decouples artifact observation from the audit
engine. A sensor implementation declares: the artifact type it observes, the
rule namespace it evaluates, and the finding format it produces. The daemon
discovers sensors from `.intent/workers/*.yaml` declarations and routes their
findings through the standard Blackboard pipeline.

Currently the `AuditViolationSensor` is a concrete, source-code-specific
implementation. This feature makes the sensor layer a declared extension point
— enabling document sensors, process sensors, or any other artifact-type
observer to participate in the governance loop without modifying the engine.

---

<a id="F-43"></a>
**F-43 — Pluggable action model**
Status: `roadmap` | Scope: `extension`

An abstract action interface that decouples remediation execution from artifact
type. An action implementation declares: the artifact type it operates on, the
rules it remediates, its confidence level, and its execution contract. The
atomic action registry (F-12) becomes a registry of typed action handlers
rather than a flat list of source-code fixers.

Currently all atomic actions operate on Python source files. This feature makes
the action layer extensible — enabling document remediation actions, compliance
record correction actions, or any other artifact-type handler to participate in
the autonomous remediation loop.

---

## 4. Feature x Status Summary

| ID | Feature | Status | Scope |
|---|---|---|---|
| F-01 | Constitutional rule engine | shipping | primitive |
| F-02 | Constitutional authority hierarchy | shipping | primitive |
| F-03 | Phase discipline | shipping | primitive |
| F-04 | Constitution authoring (`.intent/` layer) | shipping | primitive |
| F-05 | Default rule library (source code) | shipping | source-code instantiation |
| F-06 | PathResolver / canonical path registry | shipping | primitive |
| F-07 | Stateless constitutional audit | shipping | source-code instantiation |
| F-08 | Continuous audit (sensor-driven) | shipping | source-code instantiation |
| F-09 | Audit finding persistence | shipping | primitive |
| F-10 | CI/CD gate | roadmap | source-code instantiation |
| F-11 | Remediation map | shipping | source-code instantiation |
| F-12 | Atomic action registry (source code) | shipping | source-code instantiation |
| F-13 | Autonomous remediation loop | shipping | primitive |
| F-14 | Proposal engine | shipping | primitive |
| F-15 | Governor approval interface (CLI) | shipping | primitive |
| F-16 | Confidence floor enforcement | shipping | primitive |
| F-17 | Full consequence chain | shipping | primitive |
| F-18 | Commit-level attribution | shipping | source-code instantiation |
| F-19 | Convergence metric | shipping | primitive |
| F-20 | Convergence graph dashboard | roadmap | primitive |
| F-21 | Daemon runtime | shipping | primitive |
| F-22 | Worker declaration model | shipping | primitive |
| F-23 | Blackboard coordination ledger | shipping | primitive |
| F-24 | Worker health monitoring | shipping | primitive |
| F-25 | Vector artifact indexing | shipping | source-code instantiation |
| F-26 | LLM integration (API) | shipping | primitive |
| F-27 | Local LLM support | partial | primitive |
| F-28 | Context builder | shipping | source-code instantiation |
| F-29 | CLI governance surface | shipping | primitive |
| F-30 | Constitutional maintenance commands | shipping | source-code instantiation |
| F-31 | Shared consequence chain (multi-user) | roadmap | primitive |
| F-32 | Role-based constitutional authority (RBAC) | roadmap | primitive |
| F-33 | Multi-repository support | roadmap | primitive |
| F-34 | Web dashboard | roadmap | primitive |
| F-35 | Federated constitution | roadmap | primitive |
| F-36 | SSO / SAML / OIDC | roadmap | primitive |
| F-37 | Regulatory export (GxP / EU AI Act) | roadmap | primitive |
| F-38 | Air-gapped deployment (guaranteed) | roadmap | primitive |
| F-39 | SLA support | roadmap | primitive |
| F-40 | OEM API surface | roadmap | primitive |
| F-41 | Artifact type registry | roadmap | extension |
| F-42 | Pluggable sensor model | roadmap | extension |
| F-43 | Pluggable action model | roadmap | extension |

**Shipping: 23** | **Partial: 1** (F-27) | **Roadmap: 19**

Of the 23 shipping features: 16 are primitives, 7 are source-code instantiations.

---

## 5. Relationship to Tier Packaging

Tier definitions in `CORE-Product-Tiers.md` reference features by ID.
The canonical tier x feature mapping:

| Feature | Audit | Solo | Team | Enterprise | Embedded |
|---|:---:|:---:|:---:|:---:|:---:|
| F-01 Constitutional rule engine | . | . | . | . | . |
| F-02 Authority hierarchy | . | . | . | . | . |
| F-03 Phase discipline | . | . | . | . | . |
| F-04 Constitution authoring | . | . | . | . | . |
| F-05 Default rule library (source code) | . | . | . | . | . |
| F-06 PathResolver | . | . | . | . | . |
| F-07 Stateless audit | . | . | . | . | . |
| F-08 Continuous audit (sensor) | | . | . | . | . |
| F-09 Finding persistence | | . | . | . | . |
| F-10 CI/CD gate | . | | . | . | . |
| F-11 Remediation map | | . | . | . | . |
| F-12 Atomic action registry (source code) | | . | . | . | . |
| F-13 Autonomous remediation loop | | . | . | . | . |
| F-14 Proposal engine | | . | . | . | . |
| F-15 Governor approval CLI | | . | . | . | . |
| F-16 Confidence floor enforcement | | . | . | . | . |
| F-17 Full consequence chain | | . | . | . | . |
| F-18 Commit-level attribution | | . | . | . | . |
| F-19 Convergence metric | | . | . | . | . |
| F-20 Convergence graph dashboard | | | . | . | . |
| F-21 Daemon runtime | | . | . | . | . |
| F-22 Worker declaration model | | . | . | . | . |
| F-23 Blackboard ledger | | . | . | . | . |
| F-24 Worker health monitoring | | . | . | . | . |
| F-25 Vector artifact indexing | | . | . | . | . |
| F-26 LLM integration (API) | | . | . | . | . |
| F-27 Local LLM support | | o | o | . | . |
| F-28 Context builder | | . | . | . | . |
| F-29 CLI governance surface | | . | . | . | . |
| F-30 Constitutional maintenance cmds | | . | . | . | . |
| F-31 Shared consequence chain | | | . | . | . |
| F-32 RBAC | | | . | . | . |
| F-33 Multi-repository support | | | . | . | . |
| F-34 Web dashboard | | | . | . | . |
| F-35 Federated constitution | | | | . | . |
| F-36 SSO / SAML / OIDC | | | | . | . |
| F-37 Regulatory export (GxP / EU AI Act) | | | | . | . |
| F-38 Air-gapped deployment (guaranteed) | | | | . | . |
| F-39 SLA support | | | | . | . |
| F-40 OEM API surface | | | | | . |
| F-41 Artifact type registry | | | | . | . |
| F-42 Pluggable sensor model | | | | . | . |
| F-43 Pluggable action model | | | | . | . |

o = supported with configuration, not default
. = included

---

*This document is derived from `CORE-Product-Tiers.md`, the system constitution,
and the reference implementation state as of May 2026. Update feature status
when implementation milestone changes. Tier packaging decisions live in
`CORE-Product-Tiers.md`; this document is the vocabulary only.*
