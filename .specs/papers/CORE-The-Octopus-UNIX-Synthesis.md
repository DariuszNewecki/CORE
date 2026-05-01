<!-- path: .specs/papers/CORE-The-Octopus-UNIX-Synthesis.md -->

# CORE-PAPER-004: The Octopus-UNIX Synthesis

**Status:** Architectural Vision (Exploratory)
**Subject:** Transition from Centralized Proceduralism to Distributed Autonomy
**Depends on:** `papers/CORE-Constitutional-Foundations.md`, `papers/CORE-As-a-Legal-System.md`
**Authority:** Policy

---

## Constitutional Standing

This paper is **exploratory architectural vision**, not constitutional law.

It introduces concepts — Limb Workspace, Shadow Knowledge Graph, Reflex
loops — that are not yet integrated into the canonical phase model, not
referenced in other governance papers, and not mapped to CORE's
constitutional layer structure. They represent a direction of travel, not
current law.

This paper does not supersede any other paper. Conflict resolution between
this paper and any canonical paper is governed by `CORE-Workflow-Papers-First.md`
section "Conflict Resolution" — a canonical paper at constitution authority
overrides this exploratory paper at policy authority.

**Concepts from this paper that have been realized in the canonical
architecture:**
- The Crate → canonically defined in `CORE-Crate.md`
- The Canary → canonically defined in `CORE-Canary.md`
- Logic Conservation Gate → canonically defined in `CORE-ConservationGate.md`
- Constitutional Finalizer (Paperwork as Execution artifact) → realized in `ActionExecutor`

**Concepts from this paper that remain exploratory (not yet canonical):**
- `LimbWorkspace` — overlay filesystem handler for in-flight changes
- `Shadow Knowledge Graph` — virtual knowledge graph over proposed changes
- `ReflexiveCoder` — recursive Generate → Sense → Correct loop
- Distributed limb autonomy model

Until an exploratory concept is defined in a canonical paper, it has no
constitutional standing and must not be implemented as if it were law.

---

## 1. Abstract

CORE has identified a state of "Ideological Rot," characterized by the drift from a dynamic cognitive system into a static, humanoid bureaucratic pipeline. This paper defines the corrective architectural paradigm: the **Octopus-UNIX Synthesis**. This model replaces the "Centralized Humanoid" architecture (Micro-managing brain + paralyzed limbs) with the "Octopus" model (Distributed neurons + autonomous limbs) using the "UNIX Neuron" (Small, stateless, sharp tools) as the irreducible building block.

---

## 2. The Crisis: Ideological Rot

The current implementation of autonomous workflows has regressed into a "Humanoid Waterfall." This failure manifests in three ways:

1. **Centralized Truth:** Over-reliance on a central database (Mind/Postgres) that provides historical data rather than real-time sensation, leading to "Semantic Blindness" during transformations.
2. **Linear Logic:** A "Conveyor Belt" orchestration that treats failure as a terminal state rather than a context-enrichment event.
3. **Bureaucratic Guard:** A focus on metadata compliance (ID tags, headers) that strangulates reasoning logic, forcing the system to fail on "permits" before it can prove "structural integrity."

---

## 3. Pillar I: The Octopus (Distributed Autonomy)

We recognize that in a truly autonomous system, intelligence must be distributed to the execution surface.

* **The Limb:** A "Workflow" is not a sequence of steps; it is a semi-autonomous organism. It receives a mission from the Brain but handles tactics locally.
* **Local Reflex:** Limbs must contain their own recursive feedback loops. When a "Sensation Neuron" (Canary) detects "pain" (a failure), the limb must self-correct locally without escalating to the central brain until a functional result is achieved.
* **Chemosensory Context:** Context must be "tasted" at the source. A limb in motion must operate within a **Limb Workspace (Shadow Knowledge Graph)** to understand how its own changes are reshaping the environment in real-time.

*Constitutional mapping (exploratory):* The Limb concept maps to the V2
Adaptive Workflow Pattern defined in `CORE-V2-Adaptive-Workflow-Pattern.md`.
LimbWorkspace and Shadow Knowledge Graph are not yet canonically defined.

---

## 4. Pillar II: The UNIX Neuron (Architectural Atomicity)

Distributed autonomy is only safe and intelligible if the components are radically simple.

* **The Neuron:** The smallest functional part. It must follow the UNIX philosophy: *Do one thing well.*
* **Statelessness:** Neurons must be pure text or fact transformers. They do not store the "Plan"; they respond to the immediate input stream.
* **The Nerve Pipe:** The coordination of the limb is handled by the **Pipe**, not a manager. The output of one neuron is the input of the next. The "Will" emerges from the flow, not the orchestrator.

*Constitutional mapping:* UNIX Neurons correspond to AtomicActions as
defined in `CORE-Action.md`. Pipe coordination corresponds to the
Orchestrator pattern in `CORE-V2-Adaptive-Workflow-Pattern.md`.

---

## 5. Pillar III: Functional Governance

We redefine the relationship between Law and Action to prioritize logic over form.

* **Integrity First:** Logic conservation and functional correctness (as proven by tests) are the only blocking laws during the "Reasoning" phase of an autonomous loop.
* **Metadata as Execution Artifact:** Identity anchors (# ID:), file headers, and formatting are recognized as artifacts of **Execution**, not requirements of **Reasoning**.
* **The Governor:** The central Mind acts as a Governor, not a CEO. It defines the Mission (The Law) and performs the final Audit, but permits the Limbs to execute the "Reflexive Twitch" required to overcome failures.

*Constitutional mapping:* The Governor model corresponds to the
ConservationGate + IntentGuard + Canary gate pipeline defined in
`CORE-Gate.md`. Metadata as Execution Artifact is realized in the
ActionExecutor Finalizer.

---

## 6. The "Limb" Operational Model (V2.3+)

To resolve the current stagnation, the system shall move to a 5-stage "Limb Action":

1. **Isolate:** Instantiate a virtual transaction workspace (The Crate).
2. **Sense:** Build a **Shadow Knowledge Graph** representing the workspace *post-change*.
3. **Reflex Loop:** Execute a recursive `Generate → Sense → Correct` loop within the workspace until the "Pain Signal" (Traceback) is resolved.
4. **Retract:** Present the completed, functionally sound logic to the Governor.
5. **Finalize:** Apply the "Paperwork" (IDs, Headers, Formatting) automatically via the `ActionExecutor` during the final write-back to the persistent Body.

*Note:* Steps 1, 4, and 5 are canonically realized (Crate, Gates,
ActionExecutor Finalizer). Steps 2 and 3 (Shadow Knowledge Graph,
Reflex Loop) are exploratory and not yet constitutionally defined.

---

## 7. Implications for Trustworthy Autonomy

The Octopus-UNIX Synthesis provides a template for AI governance that scales without micro-management. It ensures that autonomous systems:

* **Feel at the Source:** Detect and heal errors where they happen.
* **Remain Legible:** Use simple, atomic parts that humans can understand.
* **Obey the Law:** Operate within constitutional boundaries that are enforced by a Governor that cannot be bypassed.

---

**Conclusion:** CORE is not a conveyor belt; it is an environment. The limbs must be free to move, as long as they do not break the Law. Boring parts. Exciting limbs. Stable Mind.

---

# CORE Implementation Plan: Octopus-UNIX Synthesis

**Target Version:** V2.3-REBIRTH
**Goal:** Transition from Linear Humanoid Workflows to Distributed Autonomous Limbs.
**Primary Success Metric:** 90%+ autonomous resolution of `ImportError` and `Logic Drift` during refactoring.

---

## Phase 1: The "Sensation" Layer (Shadow Knowledge) — EXPLORATORY

*Objective: Eliminate "Semantic Blindness" by allowing the limb to see its own proposed changes before they are committed.*

### 1.1. The `LimbWorkspace` (Body Layer)
* **Location:** `src/shared/infrastructure/context/limb_workspace.py`
* **Logic:** Create a governed "Overlay" filesystem handler.
* **UNIX Neuron:** `read_file(path)` → Checks the active Crate first; if missing, falls back to the Base Repo.
* **Status:** Exploratory. Not yet canonically defined.

### 1.2. Virtualize the Knowledge Graph
* **Location:** `src/features/introspection/knowledge_graph_service.py`
* **Status:** Exploratory. Not yet canonically defined.

### 1.3. Context Injection
* **Location:** `src/shared/infrastructure/context/service.py`
* **Status:** Exploratory. Not yet canonically defined.

---

## Phase 2: The "Reflex" Layer (Recursive Feedback) — EXPLORATORY

*Objective: Replace the linear "Waterfall" with a local reflexive loop within the limb.*

### 2.1. The `ReflexiveCoder` Neuron (Will Layer)
* **Status:** Exploratory. Corresponds directionally to `ReflexiveCoder` concept in V2 Adaptive Workflow.

### 2.2. The "Reflex Pipe" (Orchestration)
* **Status:** Exploratory. Loop logic not yet canonically defined.

---

## Phase 3: Functional Governance — PARTIALLY REALIZED

### 3.1. Severity Reclassification
* `purity.stable_id_anchor` downgraded to `enforcement: reporting` — **REALIZED** in current rule documents.

### 3.2. Logic Conservation Gate
* **Status:** **REALIZED** — see `CORE-ConservationGate.md`.

---

## Phase 4: The "Finalize" Layer — REALIZED

### 4.1. The `AtomicFinalizer` (Body Layer)
* **Status:** **REALIZED** — ActionExecutor runs fix.ids, fix.headers, fix.format as part of the execution ceremony.

---

## Implementation Roadmap

| Milestone | Duration | Sign-off Criteria | Status |
| :--- | :--- | :--- | :--- |
| **1. Shadow Context** | 1-2 Days | `ContextService` returns new path of moved symbol | Exploratory |
| **2. Reflex Loop** | 1-2 Days | Coder repairs `ImportError` without exiting phase | Exploratory |
| **3. Finalizer** | 1 Day | `file.edit` writes perfect headers/IDs automatically | Realized |
| **4. Integration** | 1 Day | `core-admin develop refactor` completes end-to-end | Pending |

---

**Summary:** This plan turns the "Refactor" operation into an Autonomous Limb. The canonically realized portions (Crate, ConservationGate, Canary, ActionExecutor Finalizer) provide the governance skeleton. The exploratory portions (LimbWorkspace, Shadow Knowledge Graph, ReflexiveCoder) represent the remaining work to complete the vision.
