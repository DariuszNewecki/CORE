---
kind: adr
id: ADR-113
title: ADR-113 — Per-finding evidence class (proven / judged / attested)
status: accepted
---

<!-- path: .specs/decisions/ADR-113-per-finding-evidence-class.md -->

# ADR-113 — Every finding declares how it was established: proven, judged, or attested

**Status:** Accepted — governor-ratified 2026-06-18
**Date:** 2026-06-18
**Grounding paper:** `CORE-BYOR.md` — §9 grounding item 4 ("per-finding attestation as a first-class evidence-trail field"), §5 parameter 2 (deterministic skeleton vs. semantic satisfaction), §7 (the honesty guardrail) — primary.
**Kindred (distinct) principle:** `CORE-Instrument-Attestation.md` — the honesty of the *instruments*; this ADR is the honesty of each *finding*. Same value (UR-07 defensibility), different surface; neither subsumes the other.
**Operationalizes:** UR-07 (Defensibility is Non-Negotiable) — primary; UR-01 (governs any artifact type) — secondary.
**Serves:** the GRC gap-analysis service (Scenario 4 — the commercial wedge) and CORE's own self-audit (Scenario 1). Independent of the parked BYOR onboard/floor work (ADR-112).

---

## Context

The governor has scoped the program to two configurations: **CORE governing
itself (Scenario 1)** and **GRC gap-analysis for a customer (Scenario 4)**, with
Scenario 4 as the revenue priority. The first concrete slice of Scenario 4 is a
gap report over a folder of a customer's documents against a handful of compliance
requirements — built specifically to demonstrate the one advantage we can defend
that no competitor leads with: **honest per-finding provenance.**

Recon (2026-06-18) confirmed the engine is already domain-general and that most of
the slice exists:

- A new artifact type ("compliance document") is a data declaration, not code
  (`.intent/artifact_types/`; `spec_markdown.yaml` already anticipates "compliance
  docs, regulatory evidence").
- Reading a document corpus already works — file selection is glob-driven from rule
  scopes (`audit_context.get_files`), not code-locked to `.py`.
- **Proven** verdicts already exist (the deterministic gates: ast/regex/glob/artifact/…).
- **Judged** verdicts already exist (`llm_gate`).

What does **not** exist is the thing that makes the report honest rather than just
another verdict stream: a finding does not currently say *how it was established*.
`AuditFinding` (`shared/models/audit_models.py`) carries `check_id`, `severity`,
`message`, `context` — but nothing distinguishing "I mechanically proved this" from
"an AI judged this" from "no automated method can settle this; a human must attest."
Today that distinction is implicit in *which engine ran* and is lost by the time a
finding reaches a report.

In a regulated market that structurally distrusts black-box AI, that lost
distinction *is* the product. This ADR makes it a first-class, derived,
non-inflatable property of every finding.

## Decision

### D1 — Every finding carries a first-class `evidence_class`

`AuditFinding` gains a required field `evidence_class ∈ {proven, judged, attested}`
(a new `EvidenceClass` enum beside `AuditSeverity` in `shared/models/audit_models.py`):

- **proven** — established by a deterministic method (file present/absent, pattern
  match, date arithmetic, structural check). Reproducible; no judgment.
- **judged** — established by an AI/semantic reading of content. Carries the model's
  reasoning and the evidence passage; is *an opinion, labelled as one* — never a fact.
- **attested** — *cannot* be established automatically. The finding states what a
  human reviewer must decide; it becomes settled only when a human attests.

### D2 — `evidence_class` is DERIVED from the producing engine, never hand-set

The label is not authored per rule or per finding. Each engine declares how it
establishes truth — a class-level `evidence_class` attribute on `BaseEngine`
(`mind/logic/engines/base.py`) — and `rule_executor` stamps the finding from the
engine that produced it, at the single construction point that already knows
`rule.engine`. This mirrors the existing `_map_enforcement_to_severity` pure
derivation. Deriving from engine identity (not a separate lookup table, not a
hand-label) is what makes the label trustworthy: it cannot drift from the method
that actually ran, and there is no seam where an author could inflate it.

Engine declarations: the deterministic gates declare `proven`; `llm_gate` (and its
stub) declare `judged`; the new attestation engine (D4) declares `attested`.

### D3 — The honesty invariant: never report a weaker method as a stronger one

A finding's `evidence_class` states how it was *actually* established. No code path
may upgrade it — a `judged` finding may never surface as `proven`, an `attested`
item may never be silently auto-resolved. This is the load-bearing rule; everything
else is plumbing. Selling a `judged` result as `proven` would fail the Final
Invariant in the exact market where defensibility is the whole value.

**Fail-closed default.** If an engine does not declare an `evidence_class`, findings
from it default to the **weakest** class (`attested` — "treat as unproven, needs a
human"), never to `proven`. Absence of a claim is never read as the strongest claim.

### D4 — `attested` is a first-class outcome, not a failure or an omission

An engine that cannot settle a requirement returns an explicit "requires human
attestation" result — carrying *what* the reviewer must decide — modelled on the
`RefusalResult` precedent (a refusal is a first-class outcome, not a bare
`ok=False`). Crucially, an un-checkable requirement is **surfaced, not skipped**:
the gap report shows "this needs your reviewer," it never quietly drops the line.
Silent omission is precisely the dishonesty this product is sold against.

### D5 — `evidence_class` is orthogonal to `severity`; they are two fields, not one

Provenance ("how was this established") and severity ("how much does the gap
matter") are independent surfaces. A `proven` finding can be low-severity; an
`attested` item can be the most material gap in the report. They are not encoded in
one another — two surfaces, two fields.

### D6 — Scope: a general engine/finding property, first exercised by GRC

This applies to **all** audits, not only the GRC slice. CORE's own self-audit
(Scenario 1) gains honest labels for free — its deterministic gates report `proven`,
its `llm_gate` rules report `judged` — which is the "we govern ourselves the same
way we govern you" credibility anchor made literal (the hinge from the design
discussion: our engine labels its own findings by the same honesty rule). The GRC
gap report is the first consumer to surface the column to a paying customer; the
offline audit's text/JSON output gains the field.

## Consequences

- **The differentiating advantage becomes mechanical, not marketing.** The report
  can say, per line, exactly what was proven vs. judged vs. handed to a human — and
  the architecture makes lying about it impossible (D2/D3).
- **The smallest honest slice is now buildable on existing infrastructure** — the
  only new code is the `EvidenceClass` enum + field, the `BaseEngine` attribute and
  its per-engine declarations, the single derivation line in `rule_executor`, and the
  one attestation engine. Everything else (corpus reading, deterministic + semantic
  checks, report emission) already exists.
- **CORE's own audits get more honest immediately** — every existing finding gains a
  truthful provenance label at no extra authoring cost.
- **A new obligation on every future engine:** it must declare its `evidence_class`.
  The fail-closed default (D3) makes forgetting safe (it degrades to `attested`,
  never to a false `proven`), but the linter/test surface should flag an undeclared
  engine so the omission is visible, not silent.

## Alternatives considered

- **Hand-label the class per rule or per finding.** Rejected — it is a drift and
  dishonesty vector (an author could mark a `judged` rule `proven`), and a label you
  can set by hand is a label you cannot trust. Derive from the method that ran (D2).
- **A central engine→class lookup table.** Rejected in favour of each engine
  declaring its own class — a central table drifts out of step with the engine set
  (the enum-list-vs-dispatch-chain failure mode), and the engine is the rightful
  authority on how it establishes truth.
- **Skip requirements that can't be checked automatically.** Rejected — silent
  omission is exactly the failure mode this product exists to beat. The un-checkable
  ones must be the most *visible* lines in the report (D4).
- **Encode provenance inside `severity`.** Rejected — they are orthogonal surfaces;
  conflating them loses information both ways (D5).

## References

- `CORE-BYOR.md` — §9 item 4 (this ADR), §5 parameter 2, §7 (honesty guardrail).
- `CORE-Instrument-Attestation.md` — the kindred instrument-honesty principle (distinct surface).
- `CORE-USER-REQUIREMENTS.md` — UR-07 (defensibility), UR-01 (any artifact type).
- `src/shared/models/audit_models.py` — `AuditFinding`, `AuditSeverity` (the attach point; new `EvidenceClass`).
- `src/mind/logic/engines/base.py` — `BaseEngine`, `EngineResult` (the new `evidence_class` declaration).
- `src/mind/governance/rule_executor.py` — `_map_enforcement_to_severity` (the derivation pattern this mirrors; single finding-construction point).
- ADR-112 (parked) — the BYOR onboard/floor work this is independent of.
