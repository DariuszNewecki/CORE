# Intent Governance in CORE

## Why `.intent/` matters

The `.intent/` folder is the **brain and constitution** of CORE.
It tells CORE:

* **Why** it exists (mission, principles, NorthStar)
* **What rules** it must follow (policies, schemas)
* **What it knows and can do** (knowledge, capability tags, roles)
* **How to judge risk** (evaluation, score policies, audit checklists)

---

## Two halves of `.intent/`

### 1. Immutable Charter (*human-only*)

* **`constitution/`** → who approves changes, lifecycle of operators
* **`mission/`** → NorthStar, manifesto, principles
* **`policies/`** → behavior, workflow, safety, privacy, incident response
* **`schemas/`** → technical templates that policies and knowledge must follow

🔒 These are the **laws**. CORE can read them, but never change them.
Only humans update them, usually with quorum approval.

---

### 2. Dynamic Working Brain (*system-maintained under guardrails*)

* **`knowledge/`** → capability tags, aliases, agent roles, knowledge graph
* **`evaluation/`** → scoring rules, audit checklist
* **`meta.yaml` / `project_manifest.yaml`** → how the pieces connect, mode settings

🧠 These are CORE’s **maps and memory**.
CORE can update them (for example, when new capabilities are discovered),
but only inside strict boundaries enforced by the guard.

---

## Guardrails & Safety

* **Schemas**: every policy/knowledge file must follow a strict format → prevents mistakes.
* **Aliases**: shortcuts must always point to a real capability → no broken references.
* **Agent roles**: every “power” an agent claims must resolve to a real, allowed capability.
* **Mode gates**: in **production**, CORE cannot rewrite its own intent files.
* **Risk → Evidence**: risky changes require recorded approvers and timestamps.

---

## Audit Trail

Every significant decision creates **breadcrumbs**:

* Who approved
* In which mode (dev/staging/prod)
* Which rules applied
* What evidence was attached

This ensures **traceability, accountability, and compliance**.

---

## Visual Map

```mermaid
flowchart LR
    subgraph Charter [Immutable Charter (Human-only)]
        C1[constitution/]
        C2[mission/]
        C3[policies/]
        C4[schemas/]
    end

    subgraph Brain [Dynamic Working Brain (System-maintained)]
        K[knowledge/]
        E[evaluation/]
        M[meta.yaml & project_manifest.yaml]
    end

    H[Humans] --> Charter
    Charter --> Guards[Intent Guard]
    Brain --> Guards
    Guards --> CORE[CORE Runtime]

    style Charter fill:#0ea5e9,stroke:#0369a1,color:#fff
    style Brain fill:#22c55e,stroke:#166534,color:#053
    style Guards fill:#facc15,stroke:#ca8a04,color:#000
    style CORE fill:#6d28d9,stroke:#4c1d95,color:#fff
    style H fill:#1f2937,stroke:#111,color:#fff
```

---

## In short

* **Humans hold the constitution.**
* **CORE manages knowledge, but only with guardrails.**
* **Every change is checked, logged, and explainable.**

This makes CORE **auditable, safe, and aligned with its NorthStar.**

---

# Primer for Newcomers

**What is `.intent/`?**

* It’s CORE’s brain and constitution.
* Humans set the purpose, laws, and principles.
* CORE maintains the knowledge and working memory.

**How is it structured?**

* **Immutable Charter** (constitution, mission, policies, schemas) → human only.
* **Dynamic Working Brain** (knowledge, evaluation, meta) → CORE may update, but only inside strict guardrails.

**Why is it safe?**

* Strict schemas prevent broken files.
* Aliases and roles are always checked.
* No self-rewrites in production.
* Risky changes require human evidence.

**What does this mean for you?**

* When you edit `.intent/`, you are shaping CORE’s laws and brain.
* If you add policies, they must follow schemas.
* If you approve risky changes, your approval will be recorded.

👉 Think of `.intent/` as **CORE’s Constitution + Operating Manual**. Humans hold the keys, CORE follows the rules.
