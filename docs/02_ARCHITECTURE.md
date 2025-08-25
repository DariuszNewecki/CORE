# The CORE Architecture

---

## Quick Start for New Users

The **"Mind-Body Problem"** is simple:

* **Rules (Mind)** are separate from **code (Body)** to avoid chaos.
* The **Auditor** checks everything.

👉 Start with the *Worked Example* to see directories in action.

---

## The Mind-Body Problem, Solved

* **Separation**: Mind for *“is/should be”*, Body for *execution*, bridged by **Auditor**.

---

## Anatomy of the Mind (`.intent/`)

Your project's **constitution**:

| Directory       | Purpose    | Key Files                   | Beginner Tip     |
| --------------- | ---------- | --------------------------- | ---------------- |
| `/mission`      | Principles | `principles.yaml`           | High-level goals |
| `/policies`     | Rules      | `safety_policies.yaml`      | Safety checks    |
| `/knowledge`    | Self-map   | `knowledge_graph.json`      | Code inventory   |
| `/constitution` | Processes  | `approvers.yaml`            | Change approvals |
| `/proposals`    | Drafts     | `cr-*.yaml`                 | Proposed updates |
| `/config`       | Env        | `runtime_requirements.yaml` | Setup vars       |
| `/schemas`      | Blueprints | `*.schema.json`             | File formats     |

**For Experts:** `KnowledgeGraphBuilder` uses AST to build graph (parsing → extraction → hashing).

### Visual Flow

```mermaid
graph LR
    A[Read src/ Files] --> B[AST Parse]
    B --> C[Extract Symbols]
    C --> D[Analyze Metadata]
    D --> E[Tag Capabilities]
    E --> F[Hash Structure]
    F --> G[Generate knowledge_graph.json]
    G --> H[Auditor Uses for Enforcement]
```

---

## Anatomy of the Body (`src/`)

Domains for **separation of concerns**:

| Directory | Domain | Responsibility | Allowed Imports |
| --------- | ------ | -------------- | --------------- |
| `/core`   | core   | App loop, API  | shared, agents  |
| `/agents` | agents | AI roles       | core, shared    |
| `/system` | system | Auditor, CLI   | shared          |
| `/shared` | shared | Utils          | None (base)     |

**Troubleshooting:** Illegal import? Auditor flags it → propose fix in `/proposals`.

---

## Takeaways

* **Scalable design**: clear separation of Mind, Body, Auditor.
* **Next**: Governance.
