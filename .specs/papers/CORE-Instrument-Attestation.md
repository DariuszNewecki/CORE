---
kind: paper
id: CORE-Instrument-Attestation
title: CORE — Instrument Attestation
status: draft
doctrine_tier: informational
---

<!-- path: .specs/papers/CORE-Instrument-Attestation.md -->

# CORE — Instrument Attestation

**Status:** Architectural Vision (Exploratory)
**Authority:** Policy
**Scope:** The honesty of the visibility layer — why every instrument CORE uses to see its own state must make its *own blindness* fail loud, and why this is a property each instrument carries rather than a new instrument that watches the others.
**Operationalizes (aspirationally):** UR-07 (Defensibility is Non-Negotiable) — extended from the *output* and the *process* to the *instruments that report on both*.
**Provenance:** Distilled from a governor↔Claude design conversation on 2026-06-13, downstream of the F-19 query-honesty verification (#563 Step 1). Recorded so the direction can be reconciled-against rather than re-derived.

---

## Constitutional Standing

This paper is **exploratory architectural vision, not constitutional law.** It
names one cross-cutting property — *no instrument may fail silently* — that is
**not** yet a rule in `.intent/`, **not** referenced by other governance papers,
and **not** enforced on any existing instrument. It supersedes nothing. Until
the principle is defined in a canonical paper and projected into enforceable
data, it has no constitutional standing and must not be implemented as if it
were law.

It is recorded for one reason: the F-19 verification it grew out of had to be
done **by hand**, because nothing in the system told us the instrument had gone
blind. A thing that is not written down gets re-derived; a blindness that is not
attested gets re-discovered the expensive way.

---

## 1. The gap this names

CORE's information layer has four visibility surfaces. Each points a lens at
something *outside itself*:

| Surface | Question | Object | Axis |
|---|---|---|---|
| **Conformance** (code audit) | Does the code obey the law? | the code | static / structure |
| **Vitality** (runtime dashboard) | Does the running system heal? | the behaviour | dynamic / flow |
| **Coherence** (CCC; reconciliation gate) | Is the law consistent with itself and with intent? | the law | backward / forward |
| **Disposition** (`CORE-Disposition-Governance`) | Was the right work decided at all? | the process | restraint |

None of the four answers a fifth question: **are the instruments themselves
telling the truth?** Each surface is trusted by its own output. A query that
counts nothing reports a clean number; a rule that never fires reports no
violation; a coherence checker blind to a surface is silent *about its own
missing eye*. From inside the instrument, "measuring health" and "no longer
measuring" look identical.

This is the same hole `CORE-Disposition-Governance` named one level down — *CORE
verifies the output and trusts the process* — pushed one level further: **CORE
reports its state and trusts its instruments.**

## 2. Why this is not a fifth instrument

The naïve fix is a fourth (then fifth) instrument that watches the others. It
does not terminate: a watcher that can go silently blind needs a watcher, and so
on. **You cannot watch the watchers by adding a watcher.** Surveillance is the
wrong shape.

The escape is to move the corrective *inside* each instrument: not external
observation, but **self-attestation** — every instrument emits a falsifiable
signal of its own liveness that goes red the moment it stops measuring, and that
signal is cheap enough to verify by eye and adversarially spot-checked so it
cannot itself be quietly faked. This is congruent with
`CORE-Disposition-Governance` §3.6's rejection of autonomous self-tuning in
favour of *governed* amendment: no infinite regress of automatic watchers; a
bounded, externally-falsifiable tell instead.

## 3. The disease: silent green

The failure mode is not *wrong and screaming* — that is survivable, the red is
visible. It is *wrong and quiet*: a healthy-looking number emitted by an
instrument that has stopped measuring. One disease, one per surface:

- **Conformance** — `Dispatch: 0·0`: the rule did not fire and said nothing
  (stale import, unmapped namespace, silent-inert check).
- **Vitality** — `payload = '{}'` / `total_open = 0`-while-blind: the query
  counted nothing and reported a clean zero.
- **Coherence** — an unmodelled coherence surface: the checker is silent about
  the class it cannot see (cf. the CCC scope-gap cluster).
- **Disposition** — the corner `CORE-Disposition-Governance` §5 names directly:
  *"a confident, deterministic, self-justifying [system] that ships more and
  reconciles less while reporting improvement."*

The shared signature is a **green that means "not looking," not "looking and
clear."**

## 4. The worked example — F-19

The F-19 convergence metric (`#563`) is the concrete cost of the missing
attestation:

- Its persisted operand (`system_health_log.payload.flow_24h`) has been
  **silently blinded twice** — once by a schema rename leaving dead status
  references, once by `payload = '{}'`. Both presented as healthy zeros.
- At verification time `total_open = 0` was *honest for what it measured*, yet
  excluded **102 governor-inbox subjects** (`indeterminate` /
  `resolution_mechanism = 'human'`) — unresolved work, invisible to the count.
- Nothing fired. The only reason the gaps surfaced is a **hand-verification**
  (#563 Step 1) reading the query against the live corpus.

An attested instrument would have failed loud at each of those points. The
hand-verification *is* the manual stand-in for the attestation this paper
proposes to make structural.

## 5. The seed already exists

`CORE-Disposition-Governance` **§3.4 "The anchor — so it cannot game itself"**
already writes this rule — scoped to one instrument. Every disposition must
*cite a falsifiable ground*, and a forward-CCC plus an adversarial
sample-verifier checks the ground actually covers the intent, so the disposition
telemetry cannot mark everything `reconciled-away` to look disciplined.

That mechanism is not specific to dispositions. Lift it out and it reads as the
general law:

> Every instrument must emit a falsifiable attestation of its own liveness,
> cheap to verify and adversarially spot-checked — so that *not measuring* is
> always distinguishable from *measuring and clear*.

`CORE-Disposition-Governance` stopped one generalization short: it built the
immune mechanism for the new organ and named the disease (§5), but never turned
the lens back on Conformance, Vitality, or Coherence.

## 6. What partial attestation already exists

Each surface already has an embryonic tell — uneven, none constitutional:

- **Conformance** — the audit `Dispatch:` line (non-zero = new code actually
  loaded and ran; `0·0` = stale or inert). The closest thing to a working model:
  one glance, fails visibly.
- **Vitality** — the dashboard `frozen` override (zero 24h flow is rendered as
  *frozen*, not *stable*), and a non-empty-payload precondition. Half a tell.
- **Coherence** — effectively none. CCC's blindness is presently visible only
  through manual meta-audit, exactly as F-19's was.

The `Dispatch:` line is the design template: a liveness signal a human can read
in one glance, that distinguishes "ran" from "silently did nothing."

## Thesis, in one line

> **No instrument may fail silently. Each visibility surface must emit a
> falsifiable liveness tell that goes red the moment it stops measuring —
> enforced not by a watcher (infinite regress) but by baked-in falsifiability,
> adversarially spot-checked.**

## 7. What this is NOT

- **Not a fifth instrument.** It is a property the existing four must each carry.
  A watcher-of-watchers does not terminate (§2).
- **Not a correctness guarantee.** Attestation distinguishes *not measuring* from
  *measuring*; it does not certify the measurement is right. It removes
  *silent-green*, not *wrong-but-loud*. The latter is still caught by the surface
  itself and by review.
- **Not autonomous self-repair.** A failed attestation surfaces a finding for the
  governor; it does not silently rewire the instrument. Same posture as
  `CORE-Disposition-Governance` §3.6.
- **Not free of its own recursion.** The attestation can itself be silently
  broken. The mitigation is the `Dispatch:`-line property — the tell must be
  cheap enough to verify by eye and adversarially sampled — not a deeper tower of
  automatic checks.

## 8. Open problems

- **What is a sufficient liveness tell per surface?** The `Dispatch:` line works
  for Conformance; the analogues for Vitality (a query attesting *what* it
  counted, not just the count) and Coherence (a checker attesting *which surfaces
  it had in scope*) are unspecified.
- **The recursion floor.** Attestation that is itself an instrument can go
  silently blind. How shallow can the tower be before "cheap to eyeball" stops
  being true is unproven.
- **Cost of adversarial sampling.** §5's spot-check is the external anchor; its
  cadence and cost across four surfaces are undesigned.
- **Premature hardening.** Like `CORE-Disposition-Governance`, this is wet clay.
  Encoding a uniform attestation contract before each surface's natural tell is
  understood would ossify the wrong shape. Learn the tell per surface, *then*
  generalize.

## 9. Relation to existing CORE

- **`CORE-Disposition-Governance` §3.4 / §3.5 / §5** — the seed: §3.4 is this
  rule scoped to one instrument, §3.5 is the vector-not-scalar stance, §5 names
  the silent-green disease outright.
- **CCC (`CORE-ConstitutionalCoherenceChecker`, ADR-067, ADR-073)** — the
  Coherence surface; its own scope gaps are an instance of the disease, not an
  exception to it.
- **F-19 / #563** — the worked example; the Step-1 hand-verification is the
  manual precursor of structural attestation.
- **The audit `Dispatch:` line** — the working design template for a liveness
  tell.

## 10. Revisit triggers

- Any surface ships a structural liveness tell (beyond `Dispatch:`) — promote
  that surface's section from vision to a paper/ADR pair and project the contract
  into `.intent/`.
- A "no silent instrument" rule is drafted for `.intent/rules/` — this paper
  becomes its rationale, and the F-19 example becomes its regression fixture.
- A second instrument is caught failing silently in production — record it here
  as a second worked example before generalizing the contract.
