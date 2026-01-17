# CORE-PAPER-004: The Octopus-UNIX Synthesis

**Status:** Foundational Doctrine
**Subject:** Transition from Centralized Proceduralism to Distributed Autonomy
**Depends on:** `papers/CORE-Constitutional-Foundations.md`, `papers/CORE-As-a-Legal-System.md`
**Authority:** Constitution (Supersedes all workflow-level documentation)

---

## 1. Abstract
CORE has identified a state of "Ideological Rot," characterized by the drift from a dynamic cognitive system into a static, humanoid bureaucratic pipeline. This paper defines the corrective architectural paradigm: the **Octopus-UNIX Synthesis**. This model replaces the "Centralized Humanoid" architecture (Micro-managing brain + paralyzed limbs) with the "Octopus" model (Distributed neurons + autonomous limbs) using the "UNIX Neuron" (Small, stateless, sharp tools) as the irreducible building block.

## 2. The Crisis: Ideological Rot
The current implementation of autonomous workflows has regressed into a "Humanoid Waterfall." This failure manifests in three ways:
1.  **Centralized Truth:** Over-reliance on a central database (Mind/Postgres) that provides historical data rather than real-time sensation, leading to "Semantic Blindness" during transformations.
2.  **Linear Logic:** A "Conveyor Belt" orchestration that treats failure as a terminal state rather than a context-enrichment event.
3.  **Bureaucratic Guard:** A focus on metadata compliance (ID tags, headers) that strangulates reasoning logic, forcing the system to fail on "permits" before it can prove "structural integrity."

## 3. Pillar I: The Octopus (Distributed Autonomy)
We recognize that in a truly autonomous system, intelligence must be distributed to the execution surface.
*   **The Limb:** A "Workflow" is not a sequence of steps; it is a semi-autonomous organism. It receives a mission from the Brain but handles tactics locally.
*   **Local Reflex:** Limbs must contain their own recursive feedback loops. When a "Sensation Neuron" (Canary) detects "pain" (a failure), the limb must self-correct locally without escalating to the central brain until a functional result is achieved.
*   **Chemosensory Context:** Context must be "tasted" at the source. A limb in motion must operate within a **Limb Workspace (Shadow Knowledge Graph)** to understand how its own changes are reshaping the environment in real-time.

## 4. Pillar II: The UNIX Neuron (Architectural Atomicity)
Distributed autonomy is only safe and intelligible if the components are radically simple.
*   **The Neuron:** The smallest functional part. It must follow the UNIX philosophy: *Do one thing well.*
*   **Statelessness:** Neurons must be pure text or fact transformers. They do not store the "Plan"; they respond to the immediate input stream.
*   **The Nerve Pipe:** The coordination of the limb is handled by the **Pipe**, not a manager. The output of one neuron is the input of the next. The "Will" emerges from the flow, not the orchestrator.

## 5. Pillar III: Functional Governance
We redefine the relationship between Law and Action to prioritize logic over form.
*   **Integrity First:** Logic conservation and functional correctness (as proven by tests) are the only blocking laws during the "Reasoning" phase of an autonomous loop.
*   **Metadata as Execution Artifact:** Identity anchors (# ID:), file headers, and formatting are recognized as artifacts of **Execution**, not requirements of **Reasoning**.
*   **The Governor:** The central Mind acts as a Governor, not a CEO. It defines the Mission (The Law) and performs the final Audit, but permits the Limbs to execute the "Reflexive Twitch" required to overcome failures.

## 6. The "Limb" Operational Model (V2.3+)
To resolve the current stagnation, the system shall move to a 5-stage "Limb Action":
1.  **Isolate:** Instantiate a virtual transaction workspace (The Crate).
2.  **Sense:** Build a **Shadow Knowledge Graph** representing the workspace *post-change*.
3.  **Reflex Loop:** Execute a recursive `Generate → Sense → Correct` loop within the workspace until the "Pain Signal" (Traceback) is resolved.
4.  **Retract:** Present the completed, functionally sound logic to the Governor.
5.  **Finalize:** Apply the "Paperwork" (IDs, Headers, Formatting) automatically via the `ActionExecutor` during the final write-back to the persistent Body.

## 7. Implications for Trustworthy Autonomy
The Octopus-UNIX Synthesis provides a template for AI governance that scales without micro-management. It ensures that autonomous systems:
*   **Feel at the Source:** Detect and heal errors where they happen.
*   **Remain Legible:** Use simple, atomic parts that humans can understand.
*   **Obey the Law:** Operate within constitutional boundaries that are enforced by a Governor that cannot be bypassed.

---
**Conclusion:** CORE is not a conveyor belt; it is an environment. The limbs must be free to move, as long as they do not break the Law. Boring parts. Exciting limbs. Stable Mind.

# CORE Implementation Plan: Octopus-UNIX Synthesis

**Target Version:** V2.3-REBIRTH
**Goal:** Transition from Linear Humanoid Workflows to Distributed Autonomous Limbs.
**Primary Success Metric:** 90%+ autonomous resolution of `ImportError` and `Logic Drift` during refactoring.

---

## Phase 1: The "Sensation" Layer (Shadow Knowledge)
*Objective: Eliminate "Semantic Blindness" by allowing the limb to see its own proposed changes before they are committed.*

### 1.1. The `LimbWorkspace` (Body Layer)
*   **Location:** `src/shared/infrastructure/context/limb_workspace.py`
*   **Logic:** Create a governed "Overlay" filesystem handler.
*   **UNIX Neuron:** `read_file(path)` -> Checks the active `Crate` (Intent Crate) first; if missing, falls back to the `Base Repo`.
*   **Purpose:** Allows all subsequent tools to "taste" the future state of the code.

### 1.2. Virtualize the Knowledge Graph
*   **Location:** `src/features/introspection/knowledge_graph_service.py`
*   **Logic:** Update `KnowledgeGraphBuilder.build()` to accept an optional `LimbWorkspace`.
*   **Action:** If a workspace is provided, the builder parses the "Future Code" (in-flight) rather than the "Historical Code" (on-disk).
*   **Result:** A `ShadowGraph` that correctly identifies moved classes and changed import paths.

### 1.3. Context Injection
*   **Location:** `src/shared/infrastructure/context/service.py`
*   **Logic:** Update `ContextBuilder` to prefer the `ShadowGraph` when a `task_id` is linked to an active refactoring session.

---

## Phase 2: The "Reflex" Layer (Recursive Feedback)
*Objective: Replace the linear "Waterfall" with a local reflexive loop within the limb.*

### 2.1. The `ReflexiveCoder` Neuron (Will Layer)
*   **Location:** `src/will/agents/coder_agent.py`
*   **Logic:** Modify the generator to accept `(Goal + Current Code + Pain Signal)`.
*   **Function:** If a `Pain Signal` (Traceback/Error) is present, the prompt strategy shifts from "Generate" to "Repair."

### 2.2. The "Reflex Pipe" (Orchestration)
*   **Location:** `src/will/phases/code_generation_phase.py`
*   **The Loop Logic:**
    1.  **Generate:** `ReflexiveCoder` produces a code Crate.
    2.  **Sense:** `Canary` runs tests inside the `LimbWorkspace`.
    3.  **Evaluate:** If tests fail, extract the `Traceback` (The Pain Signal).
    4.  **Twitch:** If failing, pipe the `Traceback` back to Step 1 (Max 3 iterations).
*   **Termination:** Only return a `PhaseResult` when the Canary is silent OR "Energy" (retries) is exhausted.

---

## Phase 3: Functional Governance
*Objective: Prioritize logic integrity over bureaucratic formatting.*

### 3.1. Severity Reclassification
*   **Location:** `.intent/rules/code/purity.json` and `linkage.json`
*   **Action:** Change `purity.stable_id_anchor` and `linkage.assign_ids` to `enforcement: reporting` (Advisory) during the `AUDIT` phase of a live limb.
*   **Logic:** Do not block a brilliant refactor because a UUID is missing.

### 3.2. Logic Conservation Gate
*   **Logic:** Implement a "Mass-Check" neuron. If the new code size is < 50% of the original without a "Deletions Authorized" flag, trigger a `CRITICAL` violation (Logic Evaporation).

---

## Phase 4: The "Finalize" Layer (Execution Side-Effects)
*Objective: Automate the "Paperwork" so the AI doesn't have to think about it.*

### 4.1. The `AtomicFinalizer` (Body Layer)
*   **Location:** `src/body/atomic/executor.py`
*   **Logic:** Enhance `ActionExecutor.execute("file.edit", write=True)`.
*   **Sequence:** Before writing to the permanent Body, the Executor runs a deterministic pipeline:
    1.  `fix.ids`: Assign missing UUIDs.
    2.  `fix.headers`: Correct the file path comments.
    3.  `fix.format`: Run Black/Ruff.
*   **Constitutional Shift:** The AI (Will) provides the **Logic**; the Executor (Body) ensures **Compliance**.

---

## Implementation Roadmap

| Milestone | Duration | Sign-off Criteria |
| :--- | :--- | :--- |
| **1. Shadow Context** | 1-2 Days | `ContextService` returns the new path of a moved symbol. |
| **2. Reflex Loop** | 1-2 Days | Coder repairs an `ImportError` without exiting the phase. |
| **3. Finalizer** | 1 Day | `file.edit` writes perfect headers/IDs automatically. |
| **4. Integration** | 1 Day | `core-admin develop refactor` completes end-to-end. |

---

**Summary for the Theorist:**
This plan effectively turns the "Refactor" operation into an **Autonomous Limb**. We stop trying to fix the "Brain" (Orchestrator) and instead give the "Hand" (Coder/Canary) its own nervous system.

The stagnation breaks when the system is allowed to "fail and fix" locally, rather than "fail and die" centrally.
