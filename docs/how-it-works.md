# How CORE Works

CORE is built on a single architectural principle: **governance must be structural, not advisory**.

Rules are not suggestions checked after the fact. They are enforcement gates that determine whether execution proceeds at all.

---

## The Constitutional Loop

Every autonomous operation in CORE follows the same governed loop:

```mermaid
flowchart TD
    A["🟢 GOAL\nHUMAN INTENT"] --> B["📂 CONTEXT\nRepo state • knowledge • history"]
    B --> C["🔒 CONSTRAINTS\nImmutable rules\n92 rules • 7 engines"]
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

## Three Constitutional Layers

CORE enforces a strict separation of responsibility across three layers. This separation is law — not convention.

### 🧠 Mind — Law

**Location:** `.intent/` + `src/mind/`

Mind defines what is allowed, required, or forbidden. It contains machine-readable constitutional rules, phase-aware enforcement models, and the authority hierarchy:

```
Meta → Constitution → Policy → Code
```

**Mind never executes. Mind never mutates. Mind defines law.**

The `.intent/` directory is the authoritative source. It is human-authored and immutable at runtime. CORE cannot write to it. No autonomous operation can amend constitutional law.

---

### ⚖️ Will — Judgment

**Location:** `src/will/`

Will reads constitutional constraints, orchestrates autonomous reasoning, and records every decision with a traceable audit trail. Every operation follows a structured phase pipeline:

```
INTERPRET → PLAN → GENERATE → VALIDATE → STYLE CHECK → EXECUTE
```

**Will never bypasses Body. Will never rewrites Mind.**

---

### 🏗️ Body — Execution

**Location:** `src/body/`

Body contains deterministic, atomic components: analyzers, evaluators, file operations, git services, test runners, CLI commands.

**Body performs mutations. Body does not judge. Body does not govern.**

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

A Blocking rule that fails halts execution immediately. No partial states. No exceptions.

---

## Enforcement Engines

CORE evaluates rules through seven engines:

| Engine | Method |
|--------|--------|
| `ast_gate` | Deterministic structural analysis (AST-based) |
| `glob_gate` | Path and boundary enforcement |
| `intent_gate` | Runtime write authorization |
| `knowledge_gate` | Responsibility and ownership validation |
| `workflow_gate` | Phase-sequencing and coverage checks |
| `regex_gate` | Pattern-based text enforcement |
| `llm_gate` | LLM-assisted semantic checks |

Deterministic when possible. LLM only when necessary.

---

## System Guarantees

Within CORE:

- No file outside an autonomy lane can be modified
- No structural rule can be bypassed silently
- No database action occurs without authorization
- All decisions are phase-aware and logged with full decision traces
- No agent can amend constitutional law

If a blocking rule fails, execution halts. No partial states.

---

## Trust Model

| Component | Trusted? |
|-----------|---------|
| `.intent/` constitution | ✅ Yes |
| Rules engine | ✅ Yes |
| Audit system | ✅ Yes |
| Execution system | ✅ Yes |
| AI outputs | ❌ Never |
| Generated code | ❌ Never |
| Plans | ❌ Never |

The process is trustworthy even when the AI is not.
