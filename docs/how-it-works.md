# How CORE Works

CORE is built on a single architectural principle: **governance must be structural, not advisory**.

Rules are not suggestions checked after the fact. They are enforcement gates that determine whether execution proceeds at all.

---

## The Constitutional Loop

Every autonomous operation in CORE follows the same governed loop:

```mermaid
flowchart TD
    A["🟢 GOAL\nHUMAN INTENT"] --> B["📂 CONTEXT\nRepo state • knowledge • history"]
    B --> C["🔒 CONSTRAINTS\nImmutable rules\n265 rules • 17 engines"]
    C --> D["🗺️ PLAN\nStep-by-step reasoning\nRule-aware plan"]
    D --> E["✨ GENERATE\nCode • changes • tool calls"]
    E --> F["✅ VALIDATE\nDeterministic checks\nAST • semantic • intent • style"]
    F -->|Pass| G["▶️ EXECUTE\nApply compliant changes"]
    F -->|Fail| H["🔄 REMEDIATE\nRepair violation\nAutonomy Ladder"]
    H --> E
    G --> I["✓ SUCCESS\nChanges committed"]

    subgraph "SAFETY HALT"
        direction TB
        J["🚨 CONSTITUTIONAL VIOLATION\n→ HARD HALT\n+ FULL AUDIT LOG"]
    end

    E -.->|Any violation| J
    F -.->|Any violation| J

    classDef phase      fill:#f8f9fa,stroke:#495057,stroke-width:2px
    classDef constraint fill:#d1e7ff,stroke:#0d6efd,stroke-width:2.5px
    classDef validate   fill:#fff3cd,stroke:#ffc107,stroke-width:2.5px
    classDef halt       fill:#ffebee,stroke:#dc3545,stroke-width:3px

    class A,B,D,E,G,I phase
    class C constraint
    class F validate
    class J halt
```

---

## Four Repository Layers

CORE separates responsibility across four layers. Three are enforced as constitutional law. One is the human reasoning layer.

### 📐 Specs — Human Intent

**Location:** `.specs/`

The human intent layer. Contains architectural papers, northstar documents, user requirements, architectural decision records, and planning documents. This is where the reasoning behind constitutional decisions lives.

`.specs/` is authored by humans and never written by CORE. It is vectorized into the `core_specs` collection and semantically searchable — context build evidence draws from it alongside constitutional rules.

Start here: [`.specs/northstar/CORE-What-It-Does.md`](https://github.com/DariuszNewecki/CORE/blob/main/.specs/northstar/CORE%20-%20What%20It%20Does.md)

---

### 🧠 Mind — Law

**Location:** `.intent/` + `src/mind/`

Mind defines what is allowed, required, or forbidden. It contains machine-readable constitutional rules, enforcement mappings, phase-aware enforcement models, and the authority hierarchy:

```
Meta → Constitution → Policy → Code
```

In `.intent/` this expands to a chain that ends at the engines which actually read `src/`:

```mermaid
flowchart TD
    META[".intent/META/<br/>schemas + meta-rules<br/><i>how rules are written</i>"]
    CONST[".intent/constitution/<br/>founding rules<br/><i>what CORE will not do</i>"]
    RULES[".intent/rules/<br/>executable rule definitions"]
    MAP[".intent/enforcement/mappings/<br/>rule → engine + file scope"]
    ENG["Engines<br/>ast_gate · regex_gate · glob_gate · cli_gate<br/>artifact_gate · workflow_gate · knowledge_gate · action_gate<br/>passive_gate · taxonomy_gate · contracts_gate · attestation_gate<br/>reference_gate · exclusion_gate · llm_gate · grc_judge · runtime_gate"]
    CODE["src/"]
    BB["blackboard_entries<br/>audit.violation::&lt;rule&gt;"]

    META --> CONST
    CONST --> RULES
    RULES --> MAP
    MAP --> ENG
    ENG --> CODE
    CODE -.->|violates| BB
    BB -.->|cites| RULES

    classDef law       fill:#d1e7ff,stroke:#0d6efd,stroke-width:2px
    classDef binding   fill:#fff3cd,stroke:#ffc107,stroke-width:2px
    classDef engine    fill:#e7f5e7,stroke:#28a745,stroke-width:2px
    classDef observed  fill:#f8f9fa,stroke:#495057,stroke-width:2px

    class META,CONST,RULES law
    class MAP binding
    class ENG engine
    class CODE,BB observed
```

Every rule with an enforcement mapping names exactly one engine; the rules without a mapping are advisory or exempt and are human-reviewed. Engines only read — most read repository files, `runtime_gate` reads runtime telemetry from the blackboard — and never write. Violations land on the blackboard as `audit.violation::<rule>` and cite back at the rule that produced them, which is how the [Proof Index](proof-index.md) audit-state query observes them.

**Mind never executes. Mind never mutates. Mind defines law.**

The `.intent/` directory is the authoritative source for operational governance. It is human-authored and immutable at runtime. CORE cannot write to it. No autonomous operation can amend constitutional law.

---

### ⚖️ Will — Judgment

**Location:** `src/will/`

Will reads constitutional constraints, orchestrates autonomous reasoning, and records every decision with a traceable audit trail. Every operation follows a structured phase pipeline:

```
INTERPRET → PLAN → LOAD CONTEXT → GENERATE → VALIDATE (changes · canary · sandbox · style) → COMMIT
```

**Will never bypasses Body. Will never rewrites Mind.**

---

### 🏗️ Body — Execution

**Location:** `src/body/`

Body contains deterministic, atomic components: analyzers, evaluators, file operations, git services, test runners. (The CLI lives in `src/cli/`, the API in `src/api/`, and cross-cutting infrastructure in `src/shared/`.)

**Body performs mutations. Body does not judge. Body does not govern.**

---

## How an Action Executes

Every autonomous mutation in CORE flows through one path. Workers do not call each other; they communicate through the blackboard. A finding becomes a proposal, the proposal is approved (automatically only inside the safe-auto-approval envelope, otherwise by a human), and `ProposalConsumerWorker` executes approved proposals through `ActionExecutor` — the only caller permitted to invoke an `@atomic_action`. The decorator refuses any other caller: a direct call raises `GovernanceBypassError`. (A governor running a command directly from the CLI is a separate, human-operated path; see the [Proof Index](proof-index.md).)

```mermaid
sequenceDiagram
    autonumber
    participant AVS as AuditViolationSensor
    participant BB as blackboard_entries
    participant VR as ViolationRemediator
    participant P as core.autonomous_proposals
    participant G as Approval (envelope or human)
    participant PC as ProposalConsumerWorker
    participant AE as ActionExecutor
    participant AA as "@atomic_action"
    participant AR as core.action_results

    AVS->>BB: post finding audit.violation::<rule>
    VR->>BB: claim finding
    VR->>P: create proposal (remediation map)
    G->>P: approve
    PC->>P: load approved proposals
    PC->>AE: execute(action_id, params)
    AE->>AE: set governance token
    AE->>AA: invoke decorated function (in a sandbox worktree)
    AA-->>AE: ActionResult(ok, data, impact)
    AE->>AR: INSERT row (best-effort audit record)
    PC->>P: commit, then finalizing → completed once the consequence is recorded
    AVS->>BB: next scan: finding gone → resolved by re-audit
```

Two things this diagram makes structural:

- **No bypass.** The governance token is set inside `ActionExecutor.execute` and read by the `@atomic_action` decorator. A direct call (step 8 without step 7) finds no token and refuses. This is the mechanism behind row 2 of the [Proof Index](proof-index.md).
- **No untracked mutation.** Every successful step 8 produces a step 10 — a row in `core.action_results` with `agent_id = 'ActionExecutor'` (best-effort: if that write fails it is logged as `AUDIT_GAP`, never silently dropped). The audit trail is the record of what ran, not a summary of what was attempted. This is row 4 of the [Proof Index](proof-index.md).

---

## Constitutional Primitives

CORE's governance model is built on four primitives only:

| Primitive | Purpose |
|-----------|---------|
| Document | Persisted, validated artifact |
| Rule | Atomic normative statement |
| Phase | When the rule is evaluated |
| Authority | Who may define or amend it |

Rules carry one of three enforcement strengths: **Blocking** · **Reporting** · **Advisory**

A Blocking rule that fails stops the change before it is applied. Reporting and advisory rules surface findings and let execution continue — which surfaces block depends on the mode (see *Current proof status* in the README).

---

## Enforcement Engines

CORE evaluates rules through seventeen engines:

| Engine | Method |
|--------|--------|
| `ast_gate` | Deterministic structural analysis (AST-based) |
| `regex_gate` | Pattern-based text enforcement |
| `glob_gate` | Path and boundary enforcement |
| `cli_gate` | CLI surface and command-shape enforcement |
| `artifact_gate` | Declared-vs-discovered artifact completeness |
| `workflow_gate` | Phase-sequencing and coverage checks |
| `knowledge_gate` | Responsibility and ownership validation |
| `action_gate` | Atomic-action invariants |
| `passive_gate` | Substrate-enforced rules (DB/runtime marker) |
| `taxonomy_gate` | Capability-id ↔ atomic-action coherence (ADR-079 D9) |
| `contracts_gate` | Cross-cutting data-contract coherence (context-level; ADR-102) |
| `reference_gate` | Concrete `.intent/` references must resolve to something that exists (context-level) |
| `exclusion_gate` | Every `scope.excludes` entry must still exempt something (context-level) |
| `attestation_gate` | Human-attestation surface for requirements no automated engine can honestly decide (context-level; ADR-113) |
| `llm_gate` | LLM-assisted semantic checks |
| `grc_judge` | Semantic compliance assessment of documents against a requirements catalog (GRC gap analysis) |
| `runtime_gate` | Runtime telemetry checks — reads blackboard data, not source files |

Runtime write authorization is a separate mechanism, not an audit engine: `IntentGuard` refuses forbidden writes (for example any write under `.intent/`) at the moment they are attempted.

Deterministic when possible. LLM only when necessary.

---

## System Guarantees

Within CORE:

- Nothing is self-approved outside the safe-auto-approval envelope (five `fix.*` actions and test generation, `.py` files under `src/` and `tests/` only) — every other change waits for a human
- No structural rule can be bypassed silently
- No atomic action can execute outside the governed executor (inline authorization is deferred to the audit→consequence loop)
- Decisions are phase-aware and logged with decision traces (audit persistence is best-effort — surfaced as `AUDIT_GAP`, not silent; see the [Proof Index](proof-index.md))
- No agent can amend constitutional law

If a *blocking* rule fails, execution halts with no partial state. Reporting and advisory rules surface findings and continue — what blocks versus what reports depends on the mode.

---

## Trust Model

| Component | Trusted? |
|-----------|---------|
| `.specs/` human intent | ✅ Yes |
| `.intent/` constitution | ✅ Yes |
| Rules engine | ✅ Yes |
| Audit system | ✅ Yes — recording is best-effort; a failed write is logged as `AUDIT_GAP`, not silent ([Proof Index](proof-index.md) claim 4) |
| Execution system | ✅ Yes |
| AI outputs | ❌ Never |
| Generated code | ❌ Never |
| Plans | ❌ Never |

The process is trustworthy even when the AI is not.
