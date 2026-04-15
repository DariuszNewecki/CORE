# CORE Capability Taxonomy

## Abstract

CORE relies on a controlled vocabulary of **capabilities** to match cognitive roles with execution resources. Capabilities represent the technical abilities required to perform a cognitive responsibility. By standardizing this vocabulary, CORE ensures that routing, observability, and performance measurement remain stable even as models evolve.

This paper defines the canonical capability taxonomy used by CORE and establishes the governance rules required to prevent capability drift.

---

# 1. Motivation

Without a controlled capability vocabulary, AI orchestration systems quickly degrade into semantic ambiguity.

Examples of capability drift:

```
reasoning
analysis
thinking
logic
planning_logic
```

While these terms appear similar, they fragment routing semantics and destroy observability.

CORE therefore enforces a **controlled capability taxonomy** that all resources and roles must use.

This ensures that:

* routing decisions remain deterministic
* metrics remain comparable over time
* resources remain interchangeable

---

# 2. Capability Definition

A **Capability** represents a technical ability that an execution resource may provide.

Capabilities are used to express:

* what a role requires
* what a resource provides

Capabilities must be:

* atomic
* technology‑agnostic
* stable over time

Capabilities must never reference specific models or providers.

Example violation:

```
claude_reasoning
```

Correct form:

```
reasoning
```

---

# 3. Capability Families

Capabilities are organized into conceptual families to simplify governance.

## 3.1 Reasoning Capabilities

Used for planning, analysis, and decision support.

```
reasoning
planning
analysis
```

---

## 3.2 Code Capabilities

Used for software engineering tasks.

```
code_generation
code_understanding
code_review
refactoring
```

---

## 3.3 Structured Output Capabilities

Used when deterministic machine‑readable outputs are required.

```
json_output
schema_compliance
structured_response
```

---

## 3.4 Retrieval and Knowledge Capabilities

Used for semantic indexing and retrieval tasks.

```
embedding
semantic_search
vectorization
```

---

## 3.5 Perception Capabilities

Used for multimodal understanding.

```
vision_understanding
document_parsing
```

---

# 4. Capability Matching

Capability matching is the mechanism that determines whether a resource can fulfill a role.

A resource is eligible if:

```
required_capabilities ⊆ provided_capabilities
```

Example:

Role requirements:

```
code_understanding
code_review
json_output
```

Resource capabilities:

```
code_understanding
code_review
json_output
reasoning
```

Result:

The resource is eligible.

---

# 5. Capability Governance

Capabilities must follow strict governance rules.

## 5.1 Canonical Vocabulary

All capabilities must belong to the CORE capability vocabulary.

New capabilities require constitutional review before introduction.

---

## 5.2 Atomicity

Capabilities must represent **single technical abilities**.

Invalid example:

```
advanced_reasoning
```

Correct decomposition:

```
reasoning
planning
analysis
```

---

## 5.3 Technology Neutrality

Capabilities must not reference providers or models.

Invalid example:

```
openai_function_calling
```

Correct abstraction:

```
structured_response
```

---

## 5.4 Vocabulary Stability

Capabilities should evolve slowly.

Removing or renaming capabilities may invalidate historical performance data.

---

# 6. Capability Anti‑Patterns

CORE explicitly prohibits several common capability failures.

## Synonym Drift

Multiple capabilities describing the same ability.

Example:

```
reasoning
analysis
thinking
```

---

## Model‑Specific Capabilities

Capabilities referencing vendor technologies.

Example:

```
gpt_function_calling
```

---

## Capability Explosion

Creating overly granular capabilities.

Example:

```
python_code_generation
javascript_code_generation
```

Correct abstraction:

```
code_generation
```

Language specialization should instead be expressed in resource metadata.

---

# 7. Relationship to CORE Cognitive Taxonomy

Capabilities form the middle layer of the CORE cognitive routing model:

```
Role → Capability → Resource
```

Roles declare **required capabilities**.

Resources declare **provided capabilities**.

Routing is performed by matching the two sets.

---

# 8. Observability

Capabilities enable CORE to analyze resource performance across cognitive functions.

Metrics can be grouped by:

* role
* capability
* resource

This enables insights such as:

```
Resource A performs well for code_generation
but poorly for reasoning
```

---

# 9. Long‑Term Evolution

As CORE evolves, the capability taxonomy becomes a key governance mechanism for autonomous systems.

By enforcing a stable capability vocabulary, CORE ensures that:

* resources remain replaceable
* routing remains explainable
* performance metrics remain comparable

The capability taxonomy therefore acts as a **semantic contract between roles and resources**.

---

# 10. Summary

The CORE capability taxonomy provides a controlled vocabulary describing the technical abilities required for cognitive execution.

By enforcing capability discipline, CORE ensures that:

* roles remain stable
* resources remain interchangeable
* routing remains deterministic
* performance remains measurable

This capability layer is essential for maintaining constitutional governance over AI‑driven execution.
