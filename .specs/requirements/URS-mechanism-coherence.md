---
kind: requirement
title: URS — Mechanism Coherence
status: draft
---

<!-- path: .specs/requirements/URS-mechanism-coherence.md -->

# URS — Mechanism Coherence

**Status:** Draft (initial conceptualization 2026-06-02 — awaiting governor review)
**Authority:** Requirements
**Scope:** Coherence between a governance rule's declaration in `.intent/` and the running mechanism that claims to enforce it.
**Audience:** Governor (architect, intent author, non-programmer).
**Version:** 0.1
**Relates:** ADR-027 (Coherence Sensor), ADR-067 (Constitutional Coherence Checker), `.specs/papers/CORE-ConstitutionalCoherenceChecker.md`.

---

## 1. Purpose

CORE audits `src/` against `.intent/`. The Constitutional Coherence Checker
(CCC, ADR-067) audits the constitution against itself at the document layer.
The Coherence Sensor (ADR-027) audits the autonomous remediation loop for
fix-effectiveness. **Nothing audits the mechanism layer in between** — the
question of whether a rule's running machinery actually does what its
declaration in `.intent/` claims it does.

This gap is the home of the silent-inert failure mode: a rule exists, is
correctly declared, has a governing ADR, and is *not enforcing anything at
runtime* because somewhere between declaration and execution a link is broken
— the walker doesn't visit the declared scope, the engine dispatch resolves
to a no-op, the emission type doesn't match the consumer, the loader silently
drops the entry because a schema field went unwired. Instances of this failure
mode in CORE's own history include #480 (derived-walker silent un-forbid),
#490 (three-layer drift), the half-built schema pattern, the verify vs
verify_context split, and the asymmetric state-machine wiring closed by
ADR-072.

This URS requires a Mechanism Coherence instrument — a meta-audit — that
closes the gap.

## 2. Grounding

This URS operationalizes **UR-07 (Defensibility is Non-Negotiable)** at the
mechanism layer, in the same way the CCC paper operationalizes UR-07 at the
document layer. Defensibility breaks just as completely when a declared rule
does not fire as when two ADRs contradict each other. Both are failures of
the constitution to actually constitute.

Secondary grounding is **UR-06 (Continuous Constitutional Governance)** —
governance applies to every layer of the governance graph, including the
mechanism layer. There is no exempt layer where the relationship between
declaration and enforcement may drift.

## 3. Prior Work and Scope of the Gap

Initial work has been done in the coherence family. It does not close the
mechanism-layer gap.

| Instrument | Layer | Trust posture |
|---|---|---|
| Standard audit (`core-admin code audit`) | `src/` vs declared rules | Deterministic; fail-closed |
| Constitutional Coherence Checker (ADR-067) | document vs document (ADR/rule/northstar) | LLM as candidate-finder; governor triage |
| Coherence Sensor (ADR-027) | proposal executed vs violation persists | Deterministic; finding-only |
| **Mechanism Coherence (this URS)** | **rule declaration vs rule mechanism** | **Deterministic; fail-closed (specified below)** |
| Requirement Fulfillment Verification (`CORE-URS-Verifier.md`, ADR-094) | URS claim vs CORE runtime state | Deterministic; declared-classification; URS-author authority |

The CCC paper at §10 (Non-Goals) does not list mechanism coherence. It is
therefore an *unknown-gap* rather than a *deferred-known* — the layer was
not in the paper's conceptual frame. This URS is the first conceptualization
of the mechanism layer as a discrete instrument requirement.

The CCC paper's R3 relation ("Has a rule's enforcement behaviour drifted
from its ADR's specification?") is the closest existing concept, but it
remains a document-vs-document comparison in execution — it reads the rule
declaration and the ADR text and asks the LLM whether they agree. It does
not exercise the running mechanism. R3 and mechanism coherence are
complementary, not equivalent.

## 4. User Role

Primary user: the governor (architect, intent author, non-programmer).
The governor reads ADRs and `.intent/`; the governor does not read mechanism
implementation code. The governor requires the mechanism layer to be
verified by an instrument, on the governor's behalf, with deterministic
verdicts.

Secondary user: the autonomous remediation loop. Mechanism-coherence findings
must flow through the same blackboard surface as other findings so that
existing pipelines (sensor → finding → remediator) can act on them where
appropriate.

## 5. Functional Requirements

### R-001. Mechanism honors declaration
The governor requires proof — not assumption — that every governance rule's
running mechanism enforces what the rule's declaration in `.intent/` claims
it enforces. "Trusted by inspection of the declaration alone" is not
acceptable; trust must terminate in evidence of mechanism behavior.

### R-002. Discrete chain-breakage findings
The governor requires that any breakage between declaration and remediation
be surfaceable as a *discrete* finding that identifies the broken link
(declaration / loader / scope derivation / engine dispatch / finding emission
/ blackboard / surfacing / remediation routing). A single "mechanism
incoherence" verdict that does not name the broken link is insufficient —
the governor must be able to act on the finding without re-deriving the
chain.

### R-003. Silent-inert is a constitutional violation
A rule that exists in the constitution but whose mechanism cannot be shown
to fire on a known-violating input shall, by the governor's requirement,
constitute a constitutional violation of the same class as a contradicting
ADR or a missing rule. Silent-inert is not a degraded state to be tolerated;
it is a defect to be surfaced and resolved.

### R-004. Deterministic verdict
The governor requires the mechanism-coherence verdict to be deterministic.
No LLM judgment may enter the verdict path. (Contrast with CCC paper §4,
which admits the LLM as candidate-finder for documents — that posture is
specific to natural-language artifacts. Mechanism behavior is executable
and shall be verified by execution.)

### R-005. Fixture discipline
For every governance rule, the governor requires at least one
known-violating fixture (proving the mechanism fires when it should) and at
least one known-compliant fixture (proving the mechanism does not fire
when it should not). Fixtures are constitutional surface — they live under
`.intent/` or `.specs/`, governed by the same discipline as the rules they
verify, not under `tests/` where they would be test-suite cruft.

### R-006. Declared trusted kernel
The instrument shall declare its **trusted kernel** — the small body of
code whose correctness is established by inspection rather than by
verification through itself. The kernel boundary shall be explicit, the
kernel shall be sized for inspection in one sitting, and the kernel's
membership shall be reviewable as a list. This requirement exists to prevent
the instrument from degenerating into an unaccountable meta-recursion.

### R-007. Coverage manifest
Every mechanism-coherence run shall produce a coverage manifest enumerating
every rule evaluated, with a status of `checked` or `skipped`. A `skipped`
rule requires explicit rationale. Items skipped without rationale constitute
a coverage gap and shall be surfaced as findings. (Pattern follows CCC paper
§5 — adopted unchanged.)

### R-008. Independence from standard audit verdict
The mechanism-coherence run status and the standard audit verdict are
independent. A system may hold a clean audit verdict while carrying
broken-mechanism findings, and vice versa. The governor requires both to be
surfaced separately and not collapsed into a single overall verdict.

### R-009. Normal audit surface
The mechanism-coherence instrument shall be invokable as a normal CORE
audit operation — not as a development-only tool, not as a one-off script.
Findings shall flow through the standard blackboard subjects (with a
namespace such as `coherence.mechanism::<rule_id>::<link>`) and shall appear
on the governor dashboard alongside other audit findings.

### R-010. Authoring obligation on rule authors
Adding a new governance rule shall require, by constitutional discipline,
the simultaneous authoring of the rule's fixtures (per R-005). A rule
landed without fixtures is, by R-003, silent-inert by construction and
shall fail the mechanism-coherence run on its first invocation. The
authoring gate is upstream — no rule reaches production without fixtures.

## 6. Non-Requirements

This URS does not specify:

- the database schema for mechanism-coherence run records (ADR scope),
- the exact taxonomy of chain links (mechanism implementation decision;
  the eight links named in §1 are illustrative, not normative),
- the precise fixture file format (ADR scope),
- which existing rules are prioritized for fixture authoring (sequencing
  decision, governor discretion),
- the relationship between mechanism-coherence findings and any autonomous
  remediation pathway — by default, mechanism breakage routes to the
  governor for resolution, not to an autonomous fixer. Any future autonomous
  remediation of mechanism breakage requires a separate ADR.

## 7. Acceptance Criteria for Downstream Artifacts

A paper operationalizing this URS (analogous to
`CORE-ConstitutionalCoherenceChecker.md` for ADR-067) shall:

- define the chain links normatively,
- specify the trusted-kernel boundary,
- specify the fixture file format and storage location under `.intent/`,
- specify the finding subject namespace and payload structure,
- amend the CCC paper §8 to register Mechanism Coherence as a sibling
  instrument and acknowledge the inter-instrument boundary.

An ADR operationalizing the paper shall, in turn, specify storage schema,
CLI surface, scheduling, and dashboard integration — same shape as ADR-067
to its paper.

## 8. Closing Note

CORE's working hypothesis is that the constitution shall be verified, not
assumed (CCC paper §13). That hypothesis has been operationalized at the
document layer (CCC) and at the remediation layer (Coherence Sensor). The
mechanism layer — between declaration and execution — has been operating
on assumption. This URS records the governor's requirement that it stop
doing so.
