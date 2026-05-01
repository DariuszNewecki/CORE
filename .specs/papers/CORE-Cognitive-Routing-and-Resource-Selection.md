<!-- path: .specs/papers/CORE-Cognitive-Routing-and-Resource-Selection.md -->

# CORE Cognitive Routing and Resource Selection

## Abstract

CORE must often choose between multiple eligible execution resources capable of fulfilling a cognitive role. This paper defines the constitutional principles governing how CORE selects among those resources while preserving governance, observability, and architectural neutrality.

The goal is not to prescribe a specific algorithm, but to define the invariants that any routing implementation must respect.

---

# 1. Problem Statement

Within the CORE architecture, a role may be satisfiable by multiple resources.

Example:

```
Role: Coder

Eligible Resources:
- deepseek_coder
- ollama_qwen_coder_small
- ollama_qwen_coder_large
- anthropic_claude_sonnet
```

If routing decisions are made arbitrarily, the system becomes:

* unpredictable
* difficult to benchmark
* difficult to govern

CORE therefore defines formal principles for **cognitive routing**.

---

# 2. Routing Preconditions

Routing decisions may only occur **after capability validation**.

Eligibility rule:

```
required_capabilities ⊆ provided_capabilities
```

Resources failing this condition must not be considered.

This rule ensures that routing never violates the Role–Capability–Resource taxonomy.

---

# 3. Selection Criteria

Once eligibility is established, CORE may apply multiple selection criteria.

Examples include:

* latency
* cost
* historical success rate
* resource availability
* user or system preference

These criteria must remain **explicit and observable**.

Routing must never rely on hidden heuristics.

---

# 3a. Tier-Based Selection Guidance

Model parameter count is not a routing criterion. Models will change constantly. The following routing logic should stay stable.

Each role is evaluated against four properties:

```
1. task nature        — generation, review, reasoning, classification, or embedding
2. call frequency     — how often the role is invoked per workflow
3. cost of error      — consequence of a wrong or degraded output
4. acceptable latency — whether the caller can tolerate a slower response
```

The governing principle:

> Frequent roles optimize for speed-adjusted competence.
> Rare, high-impact roles optimize for maximum intelligence.

This produces four natural tiers:

**Tier 1 — Strategic Reasoning**
Low frequency. High consequence. Slow or expensive is acceptable; bad decisions are not.
External premium models are justified here.

```
Architect           → external premium model
RefactoringArchitect → external premium model
```

**Tier 2 — High-Throughput Code Work**
High frequency. Medium consequence. Speed and specialization outweigh raw model size.
Latency compounds at this tier — do not replace with larger slower models on benchmark scores alone.

```
Coder      → specialized fast local model
LocalCoder → smallest competent local model
```

**Tier 3 — Judgment Roles**
Moderate frequency. Quality-sensitive. Stronger models are justified even at higher latency.
Review requires understanding intent, not just syntax.

```
CodeReviewer → strongest available local coder model
```

**Tier 4 — Structured and Deterministic Tasks**
High frequency. Low consequence. Small fast models are optimal.
Intelligence beyond a threshold adds no value here.

```
CapabilityTagger  → small fast model
IntentTranslator  → small fast model
Vectorizer        → embedding-specialized model
```

When assigning or reassigning roles, consult this tier classification before selecting a resource.

---

# 3b. Role-to-Tier Binding Authority

The tier classifications in section 3a are **architectural guidance**, not
constitutional law. They describe the reasoning behind assignments but do
not themselves constrain runtime behaviour.

**The binding of a role to a resource is declared in `.intent/` and is
human-authored.** Specifically:

- Role-to-resource bindings are declared in
  `.intent/mind/cognitive/` (or equivalent path declared in
  `governance_paths.yaml`).
- The human architect is the sole authority for creating, modifying, or
  retiring a role-to-resource binding.
- CORE reads bindings at startup from `.intent/` via the declared path.
  It never writes them.
- A binding change takes effect on the next daemon restart.

**Role-to-resource bindings are not Rules** in the constitutional sense.
They are not evaluated by the audit engine and do not produce Findings.
They are operational declarations read by the CognitiveOrchestrator at
runtime. Changing a binding is a governance act (human edits `.intent/`)
but not a constitutional violation if done correctly.

The consequence: which model writes production code is a human decision,
declared in `.intent/`, with no autonomous override path. This is the
same authority model that governs all `.intent/` content.

---

# 4. Preference Hierarchies

CORE may define preference hierarchies when multiple resources are available.

Example hierarchy:

```
local resources
↓
internal infrastructure
↓
external cloud providers
```

Such hierarchies allow CORE to prioritize:

* privacy
* cost control
* infrastructure independence

while still maintaining fallback options.

---

# 5. Fallback Semantics

If a selected resource fails execution, CORE may retry using another eligible resource.

Fallback rules must ensure that:

* capability requirements remain satisfied
* routing decisions remain logged
* fallback frequency is measurable

Example sequence:

```
Primary: ollama_qwen_coder_small
Fallback: deepseek_coder
Fallback: anthropic_claude_sonnet
```

---

# 6. Observability

All routing decisions must be recorded.

Minimum required fields:

```
task_id
role
eligible_resources
selected_resource
selection_reason
execution_latency
success_or_failure
fallback_invoked
```

This allows CORE to analyze:

* routing effectiveness
* model performance per role
* infrastructure bottlenecks

---

# 7. Adaptive Improvement

Routing policies may evolve over time based on observed performance.

CORE may adaptively prefer resources that demonstrate:

* lower latency
* higher success rates
* lower operational cost

However, adaptive routing must always remain bounded by the constitutional rules defined in this paper. Adaptive preference operates within the declared binding — it may select among fallback options but may not override the primary binding declared in `.intent/`.

---

# 8. Anti-Patterns

CORE prohibits the following routing behaviors.

## Hidden Heuristics

Routing logic that cannot be explained or observed.

## Capability Violations

Selecting resources that do not satisfy required capabilities.

## Hardcoded Model Preference

Embedding specific model names directly into orchestration logic.

Example violation:

```
if role == "Coder":
    use claude
```

## Size-Based Routing

Selecting resources purely by parameter count without regard to task nature, frequency, or latency profile.

Example violation:

```
larger model → always better → assign to all roles
```

---

# 9. Relationship to CORE Cognitive Taxonomy

This paper complements the **CORE Cognitive Role–Capability–Resource Taxonomy**.

That taxonomy defines:

```
Role → Capability → Resource
```

This paper defines how CORE selects among multiple valid resources once eligibility is established.

---

# 10. Summary

Cognitive routing determines which execution resource fulfills a cognitive role.

By enforcing capability validation, explicit selection criteria, and observable decision logging, CORE ensures that routing decisions remain:

* explainable
* measurable
* constitutionally governed

Role-to-resource bindings are human-authored `.intent/` declarations.
Which model writes production code is a human decision, not an autonomous one.

These guarantees allow CORE to evolve its execution infrastructure without compromising governance or architectural integrity.
