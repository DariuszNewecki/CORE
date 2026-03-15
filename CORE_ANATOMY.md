# The Anatomy of a Governed AI Coding Agent

**CORE** – Constitutional Runtime Enforcement

> **Goal: [HUMAN INTENT]**
> CORE enforces **unbreakable constitutional governance** over the entire agent workflow.
> No prompt • no model output • no clever trick can override the rules.

## Core Phases

**🟢 GOAL**

Human objective or request given to the agent.

**📂 CONTEXT**

Repository state, knowledge sources, system inputs, conversation history.

**🔒 CONSTRAINTS**

Immutable constitutional rules & policies
(92 rules across 7 engines — always enforced, never bypassed)

**🗺️ PLAN**

Agent reasons step-by-step → creates structured, rule-aware execution plan.

**✨ GENERATE**

AI produces code • changes • tool calls • actions.

**✅ VALIDATE**

Deterministic engines (AST, semantic, intent, style, etc.) check full compliance.

**🔄 REMEDIATE**

Validation fails? → Agent repairs violation
(loops back to GENERATE/PLAN via Autonomy Ladder)

**▶️ EXECUTE**

Only approved, compliant actions run
(file writes • commits • tools • system changes)

## Safety Guarantee

**If any constitutional rule is violated at any point:**

- Execution **halts immediately**
- Full audit log created (trace + violation details)
- **No changes** are ever committed without passing all checks

**Result:** Safe • auditable • jailbreak-resistant AI coding agents — production-ready in 2026.

## Visual Flow

```mermaid
flowchart TD
    %% Main flow
    A["🟢 GOAL<br>HUMAN INTENT"] --> B["📂 CONTEXT<br>Repo state • knowledge • history"]
    B --> C["🔒 CONSTRAINTS<br>Immutable rules<br>92 rules • 7 engines"]
    C --> D["🗺️ PLAN<br>Step-by-step reasoning<br>Rule-aware plan"]
    D --> E["✨ GENERATE<br>Code • changes • tool calls"]
    E --> F["✅ VALIDATE<br>Deterministic checks<br>AST • semantic • intent • style"]
    F -->|Pass| G["▶️ EXECUTE<br>Apply compliant changes"]
    F -->|Fail| H["🔄 REMEDIATE<br>Repair violation<br>Autonomy Ladder"]
    H --> E
    G --> I["✓ SUCCESS<br>Changes committed"]

    %% Safety override
    subgraph "SAFETY HALT"
        direction TB
        J["🚨 CONSTITUTIONAL VIOLATION<br>→ HARD HALT<br>+ FULL AUDIT LOG"]
    end

    E -.->|Any violation| J
    F -.->|Any violation| J

    %% Clean, GitHub-safe styling with classDef
    classDef phase      fill:#f8f9fa, stroke:#495057, stroke-width:2px
    classDef constraint fill:#d1e7ff, stroke:#0d6efd, stroke-width:2.5px
    classDef validate   fill:#fff3cd, stroke:#ffc107, stroke-width:2.5px
    classDef halt       fill:#ffebee, stroke:#dc3545, stroke-width:3px

    class A,B,D,E,G,I phase
    class C constraint
    class F validate
    class J halt

    %% Link styling
    linkStyle default stroke:#6c757d, stroke-width:1.8px
    linkStyle 7,8 stroke:#dc3545, stroke-width:2.2px, stroke-dasharray: 5 3
