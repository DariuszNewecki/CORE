# CORE Cognitive Role–Capability–Resource Taxonomy

## Abstract

CORE separates **cognitive responsibility**, **technical ability**, and **execution engines** in order to maintain governance, observability, and replaceability of AI systems.

This paper defines the formal taxonomy used by CORE to govern cognitive execution:

* **Roles** represent cognitive responsibility.
* **Capabilities** represent technical abilities required to fulfill that responsibility.
* **Resources** represent concrete execution engines (LLMs, embedding models, etc.).

This separation ensures that:

* cognitive intent remains stable,
* technical requirements remain explicit,
* execution engines remain interchangeable.

The taxonomy enables **constitutional routing**, **observability**, and **performance measurement** across heterogeneous AI resources.

---

# 1. Motivation

AI systems typically bind **tasks directly to models**:

```
task → model
```

This coupling creates several systemic failures:

* model lock-in
* inability to measure model suitability per task
* lack of observability
* brittle orchestration
* architectural drift

CORE rejects this coupling.

Instead, CORE introduces a three-layer cognitive taxonomy:

```
Role → Capability → Resource
```

Where:

* **Role** expresses intent.
* **Capability** expresses technical requirements.
* **Resource** performs execution.

This separation preserves **architectural clarity and governance** even as models evolve.

---

# 2. Core Definitions

## 2.1 Cognitive Role

A **Cognitive Role** represents a stable responsibility within the CORE system.

Examples:

* Planner
* Architect
* Coder
* CodeReviewer
* IntentTranslator
* Vectorizer

Roles describe **why cognition is required**, not how it is executed.

Roles must remain stable over time to preserve observability and governance.

---

## 2.2 Capability

A **Capability** describes a technical ability required to perform a cognitive role.

Examples:

```
planning
reasoning
code_generation
code_understanding
refactoring
code_review
embedding
json_output
vision_understanding
```

Capabilities form a **controlled vocabulary** used to match roles to execution resources.

Capabilities answer:

> “What technical abilities are required to fulfill this role?”

---

## 2.3 Resource

A **Resource** represents an execution engine capable of providing one or more capabilities.

Examples include:

* local LLMs
* cloud LLM APIs
* embedding models
* multimodal models

Example resource identifiers:

```
deepseek_coder
anthropic_claude_sonnet
ollama_qwen_coder_small
local_embedding
```

Resources declare their abilities through:

```
provided_capabilities
```

---

# 3. Matching Semantics

CORE selects resources by matching role requirements to resource capabilities.

A resource is eligible for a role if:

```
required_capabilities ⊆ provided_capabilities
```

This rule ensures that:

* resources cannot be assigned arbitrarily
* role requirements remain enforceable
* resource capabilities remain explicit

Routing decisions must always respect this capability constraint.

---

# 4. Cognitive Routing Model

At runtime, CORE resolves cognitive execution using the following process:

```
Task → Role → Required Capabilities → Eligible Resources → Selected Resource
```

Example:

```
Task: generate refactoring plan

Role: RefactoringArchitect

Required Capabilities:
  - code_understanding
  - refactoring
  - reasoning

Eligible Resources:
  - anthropic_claude_sonnet
  - deepseek_coder
  - ollama_qwen_coder_large

Selected Resource:
  anthropic_claude_sonnet
```

Routing policies may incorporate additional criteria such as:

* latency
* cost
* availability
* prior performance metrics

However, capability matching is always the **first constraint**.

---

# 5. Observability and Performance Measurement

The Role–Capability–Resource taxonomy enables precise measurement of AI system behavior.

CORE records execution events containing at minimum:

```
task_id
role
selected_resource
required_capabilities
execution_latency
success_or_failure
quality_feedback
```

This data enables analysis such as:

* model performance by role
* latency by role
* success rates per resource
* escalation frequency
* cost efficiency

Example insight:

```
Resource deepseek_coder performs well for Coder role
but poorly for RefactoringArchitect role.
```

Such insights are impossible without separating **intent from execution**.

---

# 6. Stability Principles

To maintain architectural integrity, the taxonomy obeys the following invariants.

## 6.1 Roles Must Be Stable

Roles represent **cognitive responsibilities**, not specific models.

Models may change.

Roles must not.

---

## 6.2 Capabilities Must Be Controlled

Capabilities must belong to a **finite vocabulary**.

Synonymous capabilities are prohibited.

Example of invalid capability drift:

```
analysis
reasoning
thinking
logic_processing
```

Such drift destroys observability.

Capabilities must remain standardized.

---

## 6.3 Resources Are Replaceable

Resources represent concrete execution engines and may change frequently.

Examples:

```
deepseek_coder → replaced by ollama_qwen_coder_large
anthropic_claude → replaced by future model
```

The taxonomy allows such changes without affecting roles or capabilities.

---

# 7. Anti-Patterns

The taxonomy explicitly forbids several failure modes.

## 7.1 Model-Named Roles

Invalid:

```
Role: ClaudePlanner
Role: GPTArchitect
```

Roles must never reference models.

---

## 7.2 Capability Drift

Capabilities must not proliferate uncontrolled synonyms.

---

## 7.3 Capability-Free Resources

Resources must always declare capabilities.

Example violation:

```
qwen_local → provided_capabilities = []
```

Such resources cannot be reliably routed.

---

## 7.4 Role–Model Coupling

Roles must not implicitly bind to specific resources.

Example violation:

```
Planner always uses Claude
```

Routing must remain capability-driven.

---

# 8. Relationship to CORE Architecture

The taxonomy operates at the boundary between **Will and Body** in the CORE architecture.

```
Mind  → constitutional law
Will  → deliberation and routing
Body  → execution
```

The taxonomy governs how **Will selects execution resources**.

This ensures that execution decisions remain:

* explainable
* measurable
* constitutionally constrained

---

# 9. Long-Term Implications

This taxonomy enables CORE to evolve toward **autonomous cognitive infrastructure**.

Over time, CORE can:

* benchmark models per role
* automatically select best-performing resources
* retire underperforming models
* route workloads adaptively

This capability transforms CORE from a static system into an **adaptive governed cognitive infrastructure**.

---

# 10. Summary

The Cognitive Role–Capability–Resource taxonomy establishes a constitutional separation between:

* **intent**
* **technical requirements**
* **execution engines**

This separation enables:

* model replaceability
* capability-based routing
* observability
* performance measurement
* governance of autonomous systems

Without this taxonomy, AI orchestration degenerates into model-specific heuristics.

With it, CORE maintains **constitutional control over cognitive execution**.
