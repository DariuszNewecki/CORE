---
kind: paper
id: CORE-Internal-Truthfulness
title: CORE — Internal Truthfulness
status: draft
doctrine_tier: constitution
depends_on:
  - CORE-Enforcement-Completeness
---

<!-- path: .specs/papers/CORE-Internal-Truthfulness.md -->

# CORE — Internal Truthfulness

**Status:** Draft — proposed constitutional doctrine, not yet canonical
**Intended doctrinal tier:** Constitution
**Scope:** Every claim CORE makes about its own compliance, coverage, or
coherence — rules, engines, projections, tests, and verdicts alike.

---

## 1. Purpose

CORE does not need another design. It needs the existing design to become
internally truthful.

This paper states the constraint that binds every other doctrine governing
enforcement, taxonomy, projection, and verdict behavior: **CORE must never
claim more authority, coverage, coherence, or enforcement than its mechanisms
can prove.** Where a mechanism cannot prove a claim, the claim must not read
as proven. This is not a new mechanism. It is the invariant that the recent
dispatch-integrity work (#820) enforced by hand, one fail-open edge at a
time, before this paper existed to name the pattern.

---

## 2. Definition

CORE is internally truthful when every architectural or governance claim is
represented according to its actual evidentiary state, and no unknown,
aspirational, retired, partial, or unenforced condition is presented as
proven compliance.

More bluntly: **false green is worse than visible red.** A system that
reports DEGRADED because a mechanism genuinely cannot evaluate a rule is
telling the truth about the limits of its own knowledge. A system that
reports PASS under the same condition is not.

---

## 3. The Five Truthful Claim Postures

CORE must represent every claim using one of five truthful postures. The
first three are outcomes of mechanical adjudication. The final two identify
claims that are deliberately not mechanically adjudicated. Collapsing any
of the last four into the first is the defect this paper names.

### Mechanically adjudicated

1. **Compliant** — an executable mechanism evaluated the declared invariant,
   over its intended scope, and produced sufficient evidence that it holds.
   ("Compliant," not "Proven": the claim is bounded by the declared
   mechanism and scope, not an assertion of absolute proof.)
2. **Violated** — the mechanism evaluated the invariant and produced
   evidence that it does not hold.
3. **Unknown / degraded** — the mechanism could not evaluate the invariant
   reliably or completely (missing vocabulary, a raised error during
   discovery, an unsupported check_type, a mapping-required rule with no
   dispatch target).

### Not mechanically adjudicated

4. **Advisory / doctrine** — the principle remains normatively valid but is
   subject to governor or architectural review rather than automated
   verdict.
5. **Retired** — the declaration is retained only as historical
   traceability and makes no claim about current enforcement.

The five postures describe the evidentiary status of a claim. A rule's
`enforcement` field (`blocking` / `reporting` / `advisory`) describes how
CORE responds to that claim and is a separate axis.

For mechanically adjudicated rules:

- a `blocking` or `reporting` rule may be Compliant, Violated, or
  Unknown / degraded;
- its enforcement tier determines the consequence of a violation, not
  whether the rule was successfully evaluated.

An `advisory` declaration is deliberately outside automated adjudication.
It occupies the Advisory / doctrine posture and makes no claim of
mechanically proven compliance. A retired declaration occupies the Retired
posture and makes no current normative or enforcement claim.

A claim must not use an advisory or retired declaration to support a PASS
verdict, coverage percentage, or assertion of automated enforcement.

The forbidden collapse:

```text
unknown
advisory
retired
not executed
unsupported
empty failure
        ↓
      PASS
```

An absence of findings is evidence of compliance only when the responsible
mechanism was demonstrably capable of evaluation, actually executed, and
covered the declared scope. An absence of findings from a mechanism that
could not run, did not run, evaluated only part of the declared surface, or
ran against an unavailable or empty vocabulary is not evidence of
compliance. Presenting it as PASS is the specific failure this paper
forbids.

---

## 4. The Claim Chain

Truthfulness is not a property of any single artifact. It is a property of
the chain from concept to verdict, and every link in that chain carries an
obligation not to overstate what the next link can actually prove:

```text
Concept
  ↓
Canonical doctrine/specification
  ↓
Executable declaration
  ↓
Enforcement mechanism
  ↓
Runtime execution
  ↓
Evidence and verdict
```

- A specification must not claim an implementation that does not exist.
- A rule must not map to an unsupported check_type.
- An engine must not advertise a capability it does not implement.
- An execution failure must not render as an empty pass.
- A projection must not become a competing source of truth.
- A test must not legitimize accidental fail-open behavior.
- A verdict must not state PASS when coverage is unknown.
- Semantic judgment must not masquerade as deterministic enforcement.
- Retired mechanisms must be explicitly retired, not merely abandoned.

A break at any link makes every downstream claim that depends on that link
untrustworthy, unless that claim is independently evidenced through another
declared mechanism.

---

## 5. Grounding: #820 as Worked Cases

This paper is not speculative. Four commits landed against the dispatch
contract before this paper was drafted, and each is a concrete instance of
Section 3's collapse being found and closed:

- **`623b745a`** — unsupported dispatch stopped returning silent green;
  `ok=False` with no violations stopped disappearing; a genuinely inert
  blocking rule (`action_pattern`) was repaired rather than hidden. This
  moved CORE from "no finding means compliant" toward "no finding means
  compliant only when the mechanism was demonstrably capable of evaluating
  the rule" — Section 3's Compliant/Unknown distinction, applied for the
  first time to dispatch itself.
- **`4d0a316b`** — corrected the *first* fix's own remaining false-green
  paths: a missing `check_type` had still been walking past the guard;
  vocabulary-discovery errors were read as "declares nothing" rather than
  "could not be read"; a capability (`write_defaults_false`) that was
  declared but never implemented was deleted rather than left to advertise
  falsely. This is the clearest evidence available that the discipline in
  Section 2 is process, not a one-time patch — the subsequent follow-up
  corrected the first implementation's remaining false-green paths.
- **`674a20f0`** — capability declarations were reconciled against the
  canonical taxonomy instead of preserving private synonyms, and the
  commit did not conceal what that reconciliation cost: YAML and DB now
  diverge, two roles have zero eligible resources, and there is no declared
  synchronization mechanism. This is Section 3 applied to a case where
  truthfulness makes the system *less* operationally comfortable — accepted
  because the prior comfort depended on two matching non-canonical mistakes
  agreeing with each other, not on either being correct.
- **`0ff9a99e`** — replaced two independent local interpretations of
  "mapping required" with one canonical predicate, applied uniformly to
  dispatch-parity coherence, unmapped-rule accounting, and effective
  coverage — while explicitly declining to "fix" an unrelated audit-verdict
  contradiction on the grounds that verdict semantics are governed
  elsewhere. Recording a known gap instead of opportunistically patching it
  outside its own governance surface is itself an application of Section 4:
  a change must not overstate what it settled.

The broader reconciliation remains open. The dispatch-contract defects
closed by `623b745a` and `4d0a316b` are resolved at their specific layer.
The later commits deliberately exposed unresolved downstream conditions:
YAML/DB divergence, unroutable roles, resource-taxonomy drift, and the
audit-verdict gap. This paper cites all four as evidence of the method, not
as proof that CORE has already achieved complete internal truthfulness.

---

## 6. Relationship to Existing Doctrine

This paper generalizes an invariant that already exists in narrower form in
several places. It does not supersede or formally own them; each remains
independently authoritative, and this paper states the common shape behind
them in prose, not through a governed parent/child structure that does not
otherwise exist in `.specs/`.

- **CORE-Enforcement-Completeness** (`depends_on`, above) already treats
  silent incompleteness — a vocabulary gap that produces no finding — as
  constitutionally unacceptable, and requires that a check's vocabulary be
  verified against runtime reality rather than curated by hand. This paper
  generalizes that requirement beyond runtime gates and audit checks to
  every claim CORE makes about itself.
- **ADR-070 (source–projection coherence)** already governs drift between a
  source of truth and a derived projection as an observable, bounded
  condition. Section 4's "a projection must not become a competing source
  of truth" places that requirement inside the broader claim-chain model:
  source/projection disagreement is one instance of claim/evidence
  disagreement, not a separate concern.
- Dispatch parity and audit-verdict semantics are further applications of
  Section 3 to specific governance surfaces. Taxonomy canonicality is
  demonstrated by `674a20f0`; mapping-required accounting is demonstrated
  by `0ff9a99e`. Each applies the same truthfulness invariant without
  requiring a separate foundational justification.

---

## 7. Non-Goals

This paper does not:

- define the specific fix for any open #820 disposition (Groups A, B, C
  remain tracked as implementation work, not doctrine);
- introduce a formal umbrella, parent-paper, or ownership relation over the
  papers named in Section 6 — `depends_on` states a reasoning dependency,
  not a hierarchy;
- resolve the YAML/DB divergence or zero-eligible-resource condition
  `674a20f0` surfaced — those require a declared projection or authoring
  contract, tracked separately;
- change any rule's `enforcement` posture (`blocking` / `reporting` /
  `advisory`) — Section 3's postures and enforcement tiers answer different
  questions but are not fully independent: `blocking` and `reporting` rules
  may occupy Compliant, Violated, or Unknown / degraded, while an `advisory`
  declaration occupies the Advisory / doctrine posture;
- claim to be canonical. It is `status: draft` until its obligations are
  checked against the completed #820 dispositions and found defensible
  without qualification.
