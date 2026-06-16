---
kind: paper
id: CORE-Specification-as-Source
title: 'CORE: Specification as Source'
status: canonical
doctrine_tier: constitution
---

<!-- path: papers/CORE-Specification-as-Source.md -->

# CORE: Specification as Source

**Status:** Canonical — ratified 2026-06-16

**Depends on:**

* `papers/CORE-Constitutional-Foundations.md`
* `papers/CORE-Authority-Without-Registries.md`
* `papers/CORE-Constitution-Read-Only-Contract.md`
* `papers/CORE-Vocabulary.md`

**Ratifies the framing established by precedent in:** ADR-023 (vocabulary canonical store)

---

## Abstract

Some machine-readable artifacts under `.intent/` are not authored — they are
**compiled**. Their source is a human-authored section of a paper under
`.specs/papers/`; a regeneration command parses that section and emits the
`.intent/` artifact; a loader reads the artifact fail-closed; an audit rule
detects drift between the two. Read this way, the paper is *source code*, the
`.intent/` artifact is the *compiled output*, the regen command is the
*compiler*, and the audit rule is the *type checker*.

This paper ratifies that framing — first established by precedent in ADR-023 —
as constitutional doctrine. It states the compilation model, clarifies the
`.specs/` ↔ `.intent/` relationship under it, and — most consequentially —
defines the **test for when an artifact pair must adopt the pattern** and when
it must not. The pattern is powerful and therefore narrow: it applies only
where a machine artifact is a faithful projection of authored prose, not
wherever two artifacts happen to describe related things.

---

## 1. Motivation

CORE's deepest failure mode is drift inside the very mechanisms it operates to
prevent drift. ADR-023 found exactly this: `CORE-Vocabulary.md` (45 terms,
self-declared canonical) and `.intent/META/vocabulary.json` (16 terms,
schema-validated) both claimed authority over the same conceptual territory and
had silently diverged, with no mechanism preventing further divergence in either
direction.

The resolution was not "pick one and delete the other," and not "add metadata
describing how they relate." It was to make one the **source** and the other a
**derived projection**, and to enforce convergence mechanically. ADR-023 noted
that this resolution establishes, by precedent, a pattern broader than
vocabulary — and explicitly parked a follow-up paper to ratify it. This is that
paper.

The doctrine matters because the question it answers recurs every time a new
machine-readable artifact is proposed under `.intent/`. Without the doctrine,
the reflexive question is *"what new artifact should we author?"* With it, the
prior question becomes *"is there — or should there be — a paper that is its
source?"* That reframing is the whole point.

---

## 2. The compilation model

A **specification-as-source** artifact pair has four roles, mapped onto CORE's
existing surfaces:

| Compiler-world role | CORE surface |
|---|---|
| Source | A fenced, strict-grammar canonical section of a paper in `.specs/papers/` |
| Compiler | A regeneration command (`core-admin …`) that parses the canonical section |
| Compiled output | A schema-validated artifact under `.intent/` |
| Type checker | A constitutional audit rule that fails on drift between source and output |

The defining properties:

1. **Single direction of derivation.** Content flows source → output, never the
   reverse. Hand-editing the compiled artifact is a constitutional violation,
   exactly as committing a build artifact and editing it instead of the source
   would be a defect in any disciplined codebase.

2. **Determinism.** The compiler is a pure function of the canonical section.
   Re-running it on unchanged source produces byte-identical output. This is
   what makes drift detectable by hash (ADR-023 D3's `source_hash`).

3. **Fail-closed consumption.** Exactly one sanctioned loader reads the compiled
   artifact. A missing, malformed, or schema-invalid artifact does not fall back
   to defaults — it degrades the governance surface to a controlled stop
   (ADR-023 D4). Producing content from a fallback would mask the very failure
   the pattern exists to surface.

4. **Drift is a verdict, not a note.** The type-checker rule treats
   source-vs-output divergence as a FAIL, not an advisory. Drift in a compiled
   constitutional artifact is the worst class of drift CORE can experience; it
   does not merit a softer signal.

This is consistent with `CORE-Authority-Without-Registries.md`: the compiled
artifact is not a *registry* that accrues independent authority. It holds no
content of its own — it is a view of the paper, regenerable from it at any time.
Its on-disk persistence is a performance and validation convenience, never a
source of truth.

---

## 3. The `.specs/` ↔ `.intent/` relationship

CORE's standing division of labor is: `.specs/` is architectural reasoning read
by humans; `.intent/` is law read by the runtime. Specification-as-source does
not overturn that division — it identifies the **subset** of `.intent/` whose
content originates in `.specs/` and formalizes the link.

Two authorities must be held apart:

* **Authority over content** — *what the terms / values / entries are* — flows
  from the source paper. For a compiled pair, the paper is canonical; the
  `.intent/` artifact carries no content not derivable from it.

* **Authority over shape** — *what fields the artifact must have, what types,
  what validation* — remains with `.intent/META/` (the schema). The compiler
  must emit output that satisfies the schema; the schema does not author
  content, and the paper does not define shape.

So a compiled artifact answers to **two** masters that never overlap: its paper
for content, its META schema for shape. The audit catches violations of either
— content drift (type-checker rule) and shape violation (schema validation) are
distinct findings with distinct causes (ADR-023 D4 vs D5).

Crucially, **most of `.intent/` is not compiled.** The bulk of `.intent/` is
primary law authored directly as data — rules, mappings, flows, worker
declarations. That law has no paper "source" in the compilation sense; the paper
that *motivates* a rule is not the same as a paper that *compiles into* it.
Specification-as-source is a narrow, opt-in discipline for the specific case
defined in §4 — not a claim that every `.intent/` artifact must trace to a
paper.

---

## 4. The adoption test — when an artifact pair MUST adopt the pattern

An artifact pair `(P, A)` — a human surface `P` and a machine artifact `A` —
**must** be governed as specification-as-source when **all four** conditions
hold:

1. **Dual expression.** The same conceptual content is expressed in two forms:
   human-authored prose or tables intended for reading (`P`, in `.specs/`), and
   a machine-readable structure consumed by `src/` or the audit (`A`, in
   `.intent/`).

2. **Projection, not independent authorship.** `A`'s content is a deterministic
   transform of `P`'s content — every entry in `A` is derivable from `P` and
   carries no authored information absent from `P`. (If `A` contains content that
   exists nowhere in any paper, condition 2 fails — see §5.)

3. **Content consumption.** The runtime or the audit consumes `A`'s *content*,
   not merely its existence or shape. A schema that is validated but whose
   values never steer behavior does not meet this bar.

4. **Harmful, possible drift.** `P` and `A` can diverge, and divergence is
   constitutionally harmful — it would let the governed system act on a
   different truth than the one humans ratified.

When all four hold, leaving `(P, A)` as two independently-authored artifacts is
constitutional debt of the kind ADR-023 resolved: drift is not merely possible
but unpoliced. The pair must be wired with the obligations in §6.

### 4.1 The negative test — when the pattern MUST NOT be imposed

The pattern is coercive: it forbids hand-editing `A` and forces all change
through `P`. Imposing it where it does not fit is itself a defect. Do **not**
adopt specification-as-source when any of the following hold:

* **Legitimate divergence.** `P` and `A` are allowed to carry *different*
  content for different audiences (e.g. a narrative overview vs an operational
  subset that is genuinely curated, not derived). Forcing a single source
  destroys information. Two surfaces that must differ require two structures —
  the divergence is the design, not a bug to compile away.

* **`A` is primary law.** `A` is authored directly as the canonical artifact and
  no paper is its source. Most `.intent/` rules are exactly this. The motivating
  paper explains *why*; it does not *compile into* the rule. Condition 2 fails.

* **Inert content.** `A`'s values are never consumed by runtime or audit
  (condition 3 fails). There is nothing to keep honest; a schema check suffices.

* **No drift surface.** `P` and `A` cannot diverge — e.g. `A` is generated on
  every read and never persisted. There is no standing artifact to drift.

The four-condition test and its negative are the load-bearing contribution of
this doctrine. ADR-023 supplied the *mechanism*; this paper supplies the
*decision rule* for when the mechanism applies, so future ADRs do not relitigate
it case by case.

---

## 5. Boundary with adjacent patterns

Specification-as-source is one of several declared patterns for machine-readable
governance content. It must not absorb the others.

* **The four-artifact quartet** (paper + data + rules + enforcement), under which
  e.g. `capability_taxonomy` is governed, is a *different* shape: the data
  artifact there is authored as a first-class governed file, not compiled from a
  paper section. A quartet may coexist with, but is not, a compilation pair.
  ADR-023 D7 keeps these families separate by **location**, not by metadata —
  consistent with `CORE-Authority-Without-Registries.md`.

* **Enum and value vocabularies** (`.intent/META/enums.json`) and
  **audit-verdict vocabularies** (`audit_verdict.yaml`, ADR-005) are governed by
  their own conventions. A pair adopts *this* doctrine only by passing §4's test,
  not by analogy.

* **Direct constitutional law** (`.intent/constitution/`, `.intent/rules/`)
  remains hand-authored under the read-only contract
  (`CORE-Constitution-Read-Only-Contract.md`). Specification-as-source narrows
  *what may be hand-edited* for compiled artifacts specifically; it does not
  loosen the read-only posture for primary law.

The discipline that keeps these straight is structural, per
`CORE-Authority-Without-Registries.md`: a pair is a compilation pair because of
where its source lives and how its output is produced, not because either file
declares itself one.

---

## 6. Obligations of a compilation pair

Once §4 designates `(P, A)` a compilation pair, it must carry the full mechanism
— partial adoption reintroduces the drift the pattern exists to prevent.
Generalized from ADR-023 D2–D6:

1. **A fenced canonical section in `P`** with a declared strict grammar. Only the
   fenced content is parsed; surrounding narrative is invisible to the compiler.
2. **A grammar-validation rule** that FAILs the audit when the canonical section
   violates its declared grammar (the upstream guard against feeding the
   compiler malformed input).
3. **A regen command** that deterministically emits `A` from the canonical
   section, stamping an identity triple (`source_hash`, `generated_at`,
   `generator_version`) into `A`'s metadata.
4. **A single fail-closed loader** as the sole sanctioned reader of `A`, with
   explicit healthy / drift / broken semantics; no fallback to defaults.
5. **A drift-detection rule** that FAILs when `A`'s entries or `source_hash` do
   not match the current canonical section.
6. **A CI freshness gate** as upstream prevention, with the audit rules as the
   runtime backstop. The pre-commit hook is a convenience, never the authority —
   it can be skipped and so cannot bear constitutional weight.

A pair that has (1)–(5) but lacks (6), or vice versa, is incompletely governed:
CI catches drift before it lands; audit catches it if CI is bypassed. Both are
required.

---

## 7. Non-Goals

This paper does not:

* Convert any existing artifact into a compilation pair. Each adoption is its own
  change, justified against §4's test and (for `.intent/` writes) governed by the
  confirmation gate.
* Define the regen command's implementation, CLI naming, or output formatting —
  those are per-pair engineering decisions.
* Govern instrument-emitted schemas (e.g. `AuditStats`); whether those adopt this
  pattern, the quartet, or a hybrid is the open follow-up ADR-023 D7 names, to be
  decided by passing §4's test.
* Loosen the constitution read-only contract for primary law.

---

## 8. Conclusion

CORE already had the mechanism; it lacked the doctrine. Specification-as-source
names a precise thing: a machine artifact that is *compiled* from authored prose,
not authored beside it. Where the four-condition test holds, the paper is source,
the `.intent/` artifact is build output, the regen is the compiler, and the audit
is the type checker — and hand-editing the output is as much a defect as editing
a binary instead of its source.

The doctrine's value is as much in its boundary as its claim. Most of `.intent/`
is primary law, not compiled output; most paper-artifact relationships are
motivation, not compilation. By stating exactly when the pattern applies — and
when imposing it would destroy information — this paper lets CORE reach for
compilation where it prevents drift, and leave it alone where it would
manufacture rigidity. Authority over content stays with the paper; authority over
shape stays with the schema; drift between them is a verdict, not a note.
