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
    A["🟢 GOAL: HUMAN INTENT"] --> B["📂 CONTEXT\nRepo + knowledge + history"]
    B --> C["🔒 CONSTRAINTS\nImmutable Rules (92/7 engines)"]
    C --> D["🗺️ PLAN\nStep-by-step reasoning"]
    D --> E["✨ GENERATE\nCode, actions, changes"]
    E --> F["✅ VALIDATE\nDeterministic checks"]
    F -->|Pass| G["▶️ EXECUTE\nApply changes"]
    F -->|Fail| H["🔄 REMEDIATE\nRepair → loop back"]
    H --> E
    G --> I["Success"]

    subgraph "SAFETY HALT"
        J["🚨 CONSTITUTIONAL VIOLATION\n→ HARD HALT + AUDIT LOG"]
    end

    E -.->|Violation| J
    F -.->|Violation| J

    style J fill:#ffcccc,stroke:#c00,stroke-width:2px,color:#000
    style C fill:#e6f3ff,stroke:#0066cc
    style F fill:#fff3e6,stroke:#cc6600
    linkStyle default stroke:#333,stroke-width:1.5px
