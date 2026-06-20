---
kind: adr
id: ADR-118
title: ADR-118 — GRC verdict unit is requirement-over-corpus, gated by domain applicability
status: accepted
---

<!-- path: .specs/decisions/ADR-118-grc-verdict-unit-requirement-over-corpus.md -->

# ADR-118 — GRC verdict unit: requirement-over-corpus, gated by domain applicability

**Status:** Accepted — 2026-06-20
**Date:** 2026-06-20
**Relates:** ADR-116 (GRC catalogs are law-as-data — the requirements being evaluated);
ADR-113 (per-finding evidence class proven/judged/attested — the *how-we-know* axis this
keeps orthogonal); the `ITAM/` workspace (the corpus-coverage + authority precedent this
generalizes); CORE-BYOR backlog T5b/T5d (the catalog + internal-corpus pipeline this verdict
unit sits on top of).
**Revises:** the per-document judged model shipped in the Scenario-4 gap-analysis
(`GRCGapAnalysisService`, #677, and `grc_judge` / commit `af576e03`) — that model becomes an
evidence-contribution sublayer, not the verdict surface (D7).
**Supersedes:** nothing.

---

## Context

The Scenario-4 GRC gap-analysis judges **each document against each requirement** and rolls
the per-document verdicts up. A live run over a neutralized governance corpus (commit
`c7c7d505`) exposed the model's fault: requirement 3.5.3 (MFA for remote access) returned
**"met"** because no document *described* remote access without MFA — i.e. every document was
*silent* on it, and silence was read as satisfaction. The mirror failure is equally wrong:
flagging every silence as a gap would make every document "fail" every requirement it was
never meant to address (a patching policy SHOULD be silent on MFA).

Both failures share one root cause: **the document is the wrong unit.** Two distinct concepts
were collapsed into one:

- **silent** — a property of *one document*: it says nothing about requirement X.
- **not covered** — a property of *the whole corpus*: *no* document addresses X.

Document-level silence is mostly expected noise; corpus-level non-coverage is the signal that
matters. A second, independent concept was missing entirely: **applicability** — a "not
covered" only means anything once the framework is *in-domain* for the corpus. Evaluating an
ITAM governance corpus against a cloud-infrastructure framework yields "not covered"
everywhere — technically true, operationally useless.

The `ITAM/` workspace already solved both: it scores **coverage per (domain × lifecycle-stage)
cell across the whole corpus**, with an evidence mass and a `Primary_Deficit` field
("No authoritative governance material; Generic governance only"). The per-document GRC engine
is a regression from that maturity. This ADR makes the corpus-coverage model the GRC contract.

## Decision

**D1 — The verdict unit is the requirement evaluated over the corpus, not per document.**
The unit of a GRC verdict is one `RequirementVerdict` per requirement, derived from the whole
in-scope corpus. Per-document signals are inputs to it, never the reported surface.

**D2 — An applicability gate precedes scoring (detect → suggest → confirm).**
Before any requirement is scored, CORE establishes domain fit between corpus and framework:
*detect* the corpus's domain(s) from its content; *suggest* the in-domain framework(s) /
requirement subset; *confirm* with the operator. CORE MUST NOT silently assume domain fit.
**Out-of-scope is surfaced, never silently dropped** — "N requirements were not assessed
because this corpus reads as domain D; confirm if wrong" — the same honesty discipline as
ADR-113's evidence labelling, one level up. `applicability` is itself a judged/attested call,
not a fact, and carries its own evidence class. The gate is defined here within the GRC
pipeline; "detect the domain of a corpus before judging it" is a candidate **general** CORE
capability (reuse beyond GRC), flagged for a future ADR — not generalized now.

**D3 — The status vocabulary.** A `RequirementVerdict.status` is one of:

| status | meaning |
|---|---|
| `not_applicable` | framework out of domain for this corpus — **not a gap**; surfaced with reason |
| `satisfied` | covered authoritatively; the requirement is met |
| `deficient` | addressed somewhere in scope but falls short — the *addressed-but-failing* gap |
| `not_covered` | no evidence anywhere in scope (silent across the corpus) — the structural gap |
| `covered_unauthoritatively` | evidence exists, but not in the document expected to own it |
| `needs_human` | irreducibly human (the attestation lane) |
| `unavailable` | a verdict could not be established (transient AI failure / engine crash) |

`covered_unauthoritatively` is **kept as a distinct state** (resolving an open design
question): it is the richest GRC signal — ITAM's `Primary_Deficit` already produces it, and
"the control is mentioned in a work-instruction but missing from its owning policy" is a real
governance finding, not a deficiency of substance. It requires a notion of *expected
placement* per requirement (which DocType/section should own it); ITAM's `domain_profiles.yaml`
(required sections per DocType per maturity) is the precedent for sourcing that.

**D4 — Silence is not a verdict; it is absence of evidence.** A document that does not address
a requirement contributes nothing to that requirement's evidence pool — it is neither a gap nor
a satisfaction. The verdict emerges from the pool: empty → `not_covered`; non-empty but weak /
mislocated → `deficient` / `covered_unauthoritatively`; strong + authoritative → `satisfied`.

**D5 — Evidence is localized and part of the verdict.** Each verdict carries the evidence that
produced it: which document(s), a relevance score, an authority signal, and a citation/excerpt
— answering not just "is this covered" but "where, and how authoritatively." (ITAM's evidence
mass + authority concentration is the precedent.)

**D6 — Status is orthogonal to evidence class (ADR-113).** `status` is *what we found*;
`evidence_class` (proven / judged / attested) is *how we established it*. Every verdict carries
both. A `not_covered` can be proven (deterministic absence) or judged (AI read the corpus and
found nothing); the two axes never collapse into one.

**D7 — Pipeline consequence.** The loop flips from `N_documents × N_requirements` per-file LLM
calls to **`N_in-scope_requirements` judge calls, each over the corpus evidence retrieved for
that requirement** (top-k relevant chunks). Cheaper and more honest. The existing per-file
`grc_judge` becomes the evidence-contribution layer beneath the verdict unit; ITAM's vectorizer
+ coverage scoring is the evidence-gather + coverage layer. The two converge on one engine.

The canonical `RequirementVerdict` contract:

```
RequirementVerdict:
  requirement_id  : str
  applicability   : in_scope | out_of_scope | uncertain      # D2
  status          : satisfied | deficient | not_covered
                    | covered_unauthoritatively | not_applicable
                    | needs_human | unavailable               # D3
  evidence        : [ { document, relevance, authority, cite } ]  # D5
  evidence_class  : proven | judged | attested                # D6 (ADR-113)
  rationale       : str
```

## Consequences

- The current per-document model is revised, not deleted: `grc_judge` keeps producing
  per-evidence judgments, but the reported unit becomes `RequirementVerdict`. The CLI status
  vocabulary (`gap`/`met`/`pending_ai`/`unavailable`) is subsumed by D3's richer set.
- "Silent → met" (the live-run defect) and "silent → gap" (the noise flood) both become
  impossible by construction: silence is no longer a verdict-bearing state.
- The applicability gate adds an operator confirmation step to every analysis. This is a
  deliberate honesty cost: a one-click confirm that prevents confidently-useless cross-domain
  reports. It also requires a corpus-domain classifier (ITAM has one to adapt).
- `covered_unauthoritatively` requires expected-placement metadata per requirement; catalogs
  without it degrade gracefully to `satisfied` (coverage known, placement unknown).
- Implementation is follow-on work (not in this ADR): the `RequirementVerdict` model, the
  applicability gate, evidence retrieval/localization, and the engine reshape. Sequenced under
  CORE-BYOR T5b/T5d.

## Alternatives considered

- **Keep per-document verdicts, fix the rendering only.** Rejected: it treats the symptom
  (the "met"-on-silence label) and leaves the unit wrong — corpus-level `not_covered` remains
  invisible, which is the verdict that matters most.
- **Fold `covered_unauthoritatively` into `deficient`.** Rejected: collapses a distinct,
  high-value governance signal (right control, wrong/weak home) that ITAM already surfaces
  separately. Authority and substance are different deficiencies and remediate differently.
- **No applicability gate — score every framework against every corpus.** Rejected: produces
  confidently-useless "not covered everywhere" output for out-of-domain pairings (the
  ITAM-vs-cloud case) and erodes trust in the honest verdicts.
- **Silence as a fourth verdict state.** Rejected: silence is per-document and expected; making
  it a reported state re-imports the noise the corpus unit exists to remove. Silence belongs in
  the evidence layer (absence), not the verdict layer.

## References

- ADR-116 (GRC catalog residency / law-as-data); ADR-113 (per-finding evidence class).
- `ITAM/` workspace — corpus-coverage heatmap, evidence mass, `Primary_Deficit` authority
  signal (`OUTPUT/itam_heatmap_actions.csv`, `.INTENT/domain_profiles.yaml`).
- `src/body/services/grc/gap_analysis_service.py`, `src/mind/logic/engines/grc_judge.py`
  (the per-document model this revises); commits `af576e03`, `c7c7d505`.
- `.specs/planning/CORE-BYOR-Program-Backlog.md` — T5b (catalog), T5d (internal corpus).
