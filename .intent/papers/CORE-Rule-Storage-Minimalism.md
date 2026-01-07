<!-- path: .intent/papers/CORE-Rule-Storage-Minimalism.md -->

# CORE Rule Storage Minimalism

**Status:** Constitutional Companion Paper
**Authority:** Constitution (derivative, non-amending)
**Scope:** Machine-readable storage of CORE Rules

---

## Purpose

This paper defines the **minimal, lossless, and boring machine-readable representation** of CORE Rules.

Its purpose is to:

* guarantee one-to-one correspondence with the Canonical Rule Form,
* prevent structural creativity in storage formats,
* ensure tooling remains dumb and replaceable,
* forbid schema-driven law creation.

Storage exists to **persist law**, not to enrich it.

---

## Constitutional Context

This paper derives its authority from:

* CORE Constitution — Article II (Rule Definition)
* CORE Constitution — Article V (Non-Existence of Implicit Law)
* CORE Rule Canonical Form
* CORE Rule Authoring Discipline

Any storage format that cannot represent canonical Rules *exactly* is invalid.

---

## Storage Principle

A stored Rule MUST:

* contain exactly the canonical fields,
* preserve values without transformation,
* allow deterministic parsing,
* introduce no additional semantics.

Storage MUST NOT:

* infer defaults,
* normalize meaning,
* enrich structure,
* embed logic.

---

## Canonical Machine Representation

A machine-readable Rule is a single object with **exactly five keys**:

```
{
  "id": "<string>",
  "statement": "<string>",
  "authority": "<Meta|Constitution|Policy|Code>",
  "phase": "<Parse|Load|Audit|Runtime|Execution>",
  "enforcement": "<Blocking|Reporting|Advisory>"
}
```

No additional keys are permitted.

---

## Allowed Formats

CORE permits storage in any format that can represent the canonical object **without loss**.

Examples (non-authoritative):

* JSON
* YAML
* TOML

The choice of format is an **implementation concern**.

The structure is not.

---

## Forbidden Storage Features

The following are constitutionally forbidden in Rule storage:

* optional fields
* comments with semantic meaning
* inline documentation
* schema references
* inheritance or reuse mechanisms
* anchors, aliases, or macros
* computed or generated fields

If a format feature cannot be disabled, the format is unsuitable.

---

## One Rule — One Record

Each stored Rule represents **exactly one** canonical Rule.

Rules MUST NOT:

* be nested
* be grouped
* share fields
* reference other Rules

Collections are storage conveniences only.

---

## Deterministic Parsing Requirement

Given the same stored Rule, all compliant CORE implementations MUST:

* parse identical values,
* derive identical canonical representations,
* reach identical evaluation outcomes.

Any ambiguity in parsing is a constitutional violation.

---

## No Validation Beyond Canon

Storage-level validation is limited to:

* presence of required fields
* absence of forbidden fields
* value membership checks

All higher-order reasoning belongs outside storage.

---

## Migration and Versioning

Storage formats MAY evolve.

Canonical Rule Form MUST NOT.

Migration of storage formats MUST NOT:

* alter Rule meaning
* introduce inferred values
* repair invalid Rules

Invalid Rules MUST be rejected, not migrated.

---

## Relationship to Schemas

Schemas MAY exist to enforce minimal shape.

Schemas MUST:

* mirror the canonical fields exactly
* introduce no defaults
* reject unknown keys

Schemas are **derivative artifacts**, not law.

---

## Anti-Entropy Guarantee

By constraining storage to a single flat object:

* drift becomes impossible,
* tooling complexity collapses,
* review becomes mechanical,
* governance remains explicit.

Boredom is enforced by design.

---

## Closing Statement

Storage exists to remember law, not to reinterpret it.

If storage becomes expressive, governance has failed.

**End of Minimalism.**
