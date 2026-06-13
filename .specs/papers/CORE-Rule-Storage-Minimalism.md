---
kind: paper
id: CORE-Rule-Storage-Minimalism
title: CORE Rule Storage Minimalism
status: superseded
doctrine_tier: constitution
---

<!-- path: .specs/papers/CORE-Rule-Storage-Minimalism.md -->

# CORE Rule Storage Minimalism

**Status:** Superseded (retained as constitutional record)
**Authority:** Constitution (derivative, non-amending)
**Scope:** Machine-readable storage of CORE Rules (retired — see below)

---

## Status: Superseded (2026-06-10)

Superseded by **Constitution Article VIII** (storage formats explicitly placed
outside constitutional scope) and **CORE Rule Canonical Form** (with its
2026-06-10 scope clarification establishing that derived artifacts — including
storage encodings — are governed by Article VIII, not by Canonical-Form).

This paper claimed Constitution-derivative authority (frontmatter) to prohibit
specific shapes in Rule storage — optional fields, schema references,
inheritance and aliasing, grouping. Constitution Article VIII lines 266–278
enumerates the domains the Constitution does **not** define and explicitly
lists "storage formats" among them, declaring them "implementation concerns,
not law." A paper deriving authority from the Constitution cannot
constitutionally make prohibitions on a domain the Constitution itself places
outside law. The paper's prohibitions were over-reach by Constitution
Article V's own definition of derived authority.

The error was surfaced by the 2026-06-10 external governance review (F-01).

Verification: the shipped `rule_document.schema.json` uses the
envelope-with-metadata pattern shared by every governed CORE document type
(`worker`, `vocabulary`, `flow`, `data_contract`, `phase`, `rule_document`);
no rule has ever been stored in the flat 5-key shape this paper described.
The schema's optional `rationale` / `scope` / `check` fields are documentation
and tooling per Canonical-Form's own Forbidden Fields treatment ("If such
concepts are needed, they must exist as derived artifacts, tooling constructs,
or documentation. They are **not law**."), not constitutional rule content.
No corpus change is required to close F-01.

The body below is retained as the constitutional record of the analysis: what
was tried, why it was wrong, and what supersedes it. Its prohibitions are no
longer in force.

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
  "phase": "<Interpret|Parse|Load|Audit|Runtime|Execution>",
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
