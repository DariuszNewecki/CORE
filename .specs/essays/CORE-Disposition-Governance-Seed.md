---
kind: paper
id: CORE-Disposition-Governance-Seed
title: "CORE — Disposition Governance: Internalizing the Governor's Pushback (seed)"
status: draft
doctrine_tier: informational
depends_on: ["CORE-Disposition-Governance"]
---

<!-- path: .specs/papers/CORE-Disposition-Governance-Seed.md -->

# CORE — Disposition Governance: Internalizing the Governor's Pushback (seed)

**Status:** Exploratory seed (feeds [[CORE-Disposition-Governance]])
**Authority:** Policy
**Scope:** Naming, precisely, what the governor's "step back / look from above / are you sure" *is* — so it can be internalized into CORE rather than supplied by hand each session.
**Provenance:** Governor↔Claude conversation on 2026-06-14, at the close of the v2.7.0 release day. The governor: *"we should bolt into CORE my pushbacks, without me having to do the pushbacks."* Recorded so next week's design conversation starts from a sharpened frame instead of re-deriving it — which is the parent paper's own thesis.

---

## Constitutional Standing

Exploratory vision, **not** constitutional law. It introduces no enforceable
concept, supersedes nothing, and is not projected into `.intent/`. It is a
problem-statement seed for [[CORE-Disposition-Governance]], recorded so the
direction is reconciled-against, not re-invented.

---

## 1. Why this exists

The governor still has to inject skepticism by hand. Across a single release day
his interruptions — *"are you sure we did all we could?"*, *"we just ordered the
doc types, now this pops up?"*, *"is MIT legacy?"*, *"check the root CHANGELOG"* —
each surfaced something real that the work itself had missed: two release-breaking
CI pins, an unmodeled `.specs/` directory minted against a just-closed vocabulary,
a sloppy framing, a two-version-stale changelog.

The goal is **not** a better checklist. It is to remove the governor as the
**manual source** of that skepticism — *"without me having to do the pushbacks."*
That is the deepest form of CORE's own thesis (AI output is verified, not trusted):
the verification function the governor performs by reflex should be encoded.

## 2. The pushback is not one thing — it is four moves

Internalizing it requires naming it precisely. The governor's pushback decomposes
into four distinct cognitive moves, each needing a *different* mechanism:

1. **Completeness interrogation** — *"are you sure we did all we could?"*
   Challenges the boundary of "done"; forces enumeration of surfaces that may have
   been skipped. (Caught the Poetry-pin release-blockers, the stale changelog.)
2. **Coherence-from-above** — *"we just established X; does this new thing respect X?"*
   Checks a fresh artifact against a frame decided moments earlier; catches drift
   from a just-made decision. (Caught the unmodeled `.specs/operational/` dir vs
   ADR-105's closed `document_kind` vocabulary.)
3. **Claim verification** — *"are you sure?"* on a specific assertion; forces
   re-derivation from source. (Caught overclaims.)
4. **Naming precision** — *"is MIT legacy?"* Challenges loose language that smuggles
   a wrong idea past review.

Collapsing these into one "are-you-sure step" is the first thing the move itself
should reject.

## 3. The load-bearing tension: the pushback works because it is *external*

The governor's "step back" works precisely **because it comes from outside the
work.** He has not absorbed the momentum that produced the miss, so he can see it.

A self-applied completeness check — run by the same agent, mid-momentum, that did
the work — inherits the **same blind spots.** The disposition that missed the
changelog will also run the "did I miss anything?" pass and miss it again. So
"bolt in the governor's skepticism" cannot mean *add a self-check step.* It must
mean **manufacturing genuine outside-ness**: an independent, adversarial vantage
that does not share the work's assumptions. (Cf. the observed value of external
reviewers — they catch what internal review structurally cannot.)

This reframes the design target: not "a skepticism phase," but "a source of
perspective the working agent does not control."

## 4. The asymmetry — what CORE already does, and the exact gap

CORE is **strong** at move #3. Claim-verification against source *is* the audit
engine — gates, honesty-gated audits, CCC's coherence of the constitution against
itself. That competency is real and enforced.

CORE is **weak** at moves #1 and #2 — boundary-completeness ("did we enumerate
every surface?") and coherence-against-a-just-made-decision. There are fragments
(firing-coverage gates, register-completeness rules that read as a to-do list, the
CCC), but no general stance that, at a decision boundary, asks *what is missing*
and *does this cohere with what we just decided.*

That weakness is not incidental. **It is exactly why the governor still performs
#1 and #2 by hand.** Named plainly: the manual pushbacks map one-to-one onto
CORE's verification blind spots.

## 5. Open questions for the design conversation (not answers)

- **Where does outside-ness come from** without a second human? Independent agent
  vantages, an adversarial reviewer that never sees the work's intent, a
  perspective seeded from `.intent/`/`.specs/` rather than from the work in flight?
- **At which boundary** does the pass fire — pre-commit, pre-"done"-declaration,
  post-decision (to catch the next artifact drifting from it)?
- **How is it measured** (disposition telemetry, per the parent paper) so it can be
  trusted and self-amended rather than asserted?
- **Which of the four moves are even mechanizable** vs. irreducibly human? #1/#2/#3
  feel encodable; #4 (naming precision) may be a property of language, not a gate.

These belong on top of [[CORE-Disposition-Governance]]'s reconciliation-gate and
disposition-telemetry concepts, not beside them.
