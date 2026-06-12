<!-- path: .specs/papers/CORE-Disposition-Governance.md -->

# CORE — Disposition Governance

**Status:** Architectural Vision (Exploratory)
**Authority:** Policy
**Scope:** Internalizing the verification *discipline* — how the human↔agent loop reconciles intent against the corpus before work, and how that discipline is measured and self-amended under governance.
**Operationalizes (aspirationally):** UR-07 (Defensibility is Non-Negotiable) and UR-06 (Continuous Constitutional Governance) — extended from *outputs* to the *process that produces them*.
**Provenance:** Distilled from a governor↔Claude design conversation on 2026-06-12. Recorded so the direction can be reconciled-against rather than re-derived — which is itself the thesis below.

---

## Constitutional Standing

This paper is **exploratory architectural vision, not constitutional law.** It
introduces concepts — the reconciliation gate, disposition telemetry,
governed self-amendment — that are **not** yet in the canonical phase model,
**not** referenced by other governance papers, and **not** projected into
`.intent/`. It supersedes nothing. Until a concept here is defined in a
canonical paper and projected into enforceable data, it has no constitutional
standing and must not be implemented as if it were law.

It is recorded for one reason: a thing that is not written down gets
re-derived. This is the cheapest insurance against that.

---

## 1. The gap this names

CORE governs the **shape of its outputs** — layers, atomic actions, blackboard
attribution, symbol IDs, phase ordering, the `.intent/` projection, CCC's
coherence of the constitution against itself. That part is real and enforced.

CORE does **not** govern the **discipline of its process**. The disciplines that
actually prevent wasted and wrong work — *reconnoitre before proposing, verify
before asserting, reconcile against existing decisions before building, stop
when the work is already decided or unnecessary* — live today in `CLAUDE.md`
and an agent's accumulated memory. They are **trusted by default**: prose an
agent may or may not read, scar-knowledge that does not ship with the repo.

This is the hole in *"AI output is not trusted by default — it is verified."*
CORE verifies the **output** and trusts the **process**. The most valuable
behaviour in practice — *not building the wrong thing* — is produced by
agent-plus-`CLAUDE.md`, with the corpus's traceability acting as a
*probabilistic* safety net (a citation the agent might or might not trip over),
not a guarantee. The gap between *"CORE works well with this agent"* and
*"CORE works with any agent"* **is** `CLAUDE.md`.

## 2. The direction

Route the human↔agent exchange **through CORE**, so the discipline becomes a
property of the system rather than of the operator's manual:

- **CORE manages its own operator-instruction files.** `CLAUDE.md`/memory do
  not vanish — CORE becomes their curator. The discipline persists; its
  authorship moves inside.
- **A permanent, pipeline-structured discussion** with whichever model holds
  the role — not a one-shot canonicalisation of intent.
- **Deterministic, but not hard-coded.** The pipeline *structure* is fixed and
  auditable; its *thresholds and gates* evolve.
- **Measurement points make it adaptive — under governance.** The telemetry
  does not auto-tune weights; it emits governed amendment proposals.

The spine already partially exists: declared stages
`interpret.intent → parse.plan_actions → load.operational_context → runtime → audit → execution`,
real interpreters (`natural_language_interpreter`, `request_interpreter`), a
`workflow_orchestrator`. What is **absent**: a conversational front door
through that spine, a pre-proposal reconciliation gate, and any disposition
telemetry. The scaffold is real; the intelligence is the unbuilt 80%.

## 3. The core design

### 3.1 The reframe — measure dispositions, not changes

The unit of measurement is not "a piece of work." It is **an intent and what
happened to it.** Every intent receives exactly one recorded disposition:

```
intent → { built | reconciled-away | refused | reframed | deferred | escalated }
```

The *non-build* dispositions become **first-class logged events with a cited
ground.** This converts the counterfactual — *work correctly not done* — from
an absence into a positive, countable record. **Restraint stops being invisible
and becomes a decision with a reason.** That single move is what makes the most
valuable behaviour measurable at all.

### 3.2 The reconciliation gate

At `load.operational_context`: for each intent, check whether an existing
decision already covers it **before** work begins. This is **CCC turned
forward** — CCC audits the constitution against itself *after the fact*; the
gate audits a *proposal* against the constitution *before* the agent spends a
session on it. It is the single most valuable missing component, and it is
buildable from machinery that already exists.

### 3.3 The measurement points

| # | Where | What | When |
|---|-------|------|------|
| 1 | `load.operational_context` | **Reconciliation hit** — did the gate find a covering decision? `{hit, matched_artifact, would-have-re-derived}` | per intent, pre-runtime |
| 2 | `parse.plan_actions` exit | **Disposition** + cited ground; the *distribution* is the restraint metric | per intent, at decision-to-act |
| 3 | `interpret↔parse` loop | **Frame stability** — revisions before disposition; high-revisions→`built` is red (forced frame), →`reframed` is green | per intent |
| 4 | `interpret.intent` | **Interpretation fidelity** — divergence between raw human input and the canonical task (measures canonicaliser loss instead of assuming it) | per intent |
| 5 | post-`execution`, trailing | **Rework / fate** — of `built` items, fraction reverted / superseded / abandoned-finding / CCC-caught within N days | windowed lookback |
| 6 | decision-to-act + trailing | **Conviction calibration** — agent logs conviction + grounding before acting; correlate with rework; detects acting-without-conviction | stated per intent, scored trailing |

### 3.4 The anchor — so it cannot game itself

Every disposition **must cite a falsifiable ground** (an ADR, a rule, a roadmap
item), and the forward-CCC plus an adversarial sample-verifier check whether
the cited ground *actually covers* the intent. The system cannot mark
everything `reconciled-away` to look disciplined, because a sample is
adversarially falsified against the corpus. **This is UR-07 applied to the
discipline layer: defensibility of the *decision*, not just the output.** The
external corrective is *falsifiability of the stated reason*, spot-checked — not
a human in every loop.

### 3.5 The composite — so it never collapses to throughput

Never optimise one number. Health is a **vector**, and the system alarms on the
**pathological corners**, each a named failure with a metric:

- 100% `built` → rubber-stamp gate
- ~100% `reconciled-away` → paralysis
- high-revisions-then-`built` → forced wrong frames
- high interpretation-divergence → lossy canonicaliser
- conviction uncorrelated with rework → the agent is guessing

Health is "all corners empty," not "throughput up."

### 3.6 The self-amending loop — the "smart"

Measurements emit **governed amendment proposals**, not autonomous weight
updates. *"Class X is running 40% rework → propose tightening gate X"* becomes
a proposal: audited, versioned, and approved by the governor. The pipeline
structure stays deterministic; its thresholds evolve via governed
self-amendment driven by telemetry. This is the only "smart" that survives the
defensibility claim.

### Thesis, in one line

> **Measure dispositions, not changes; force every disposition to cite a
> falsifiable ground; watch the corners of the vector, not the top of one
> metric; and let the telemetry propose its own tightening under governance.**

That measures restraint, resists gaming, and resists the throughput trap.

## 4. What this is NOT (hard-won caveats — do not build the naïve version)

- **Not full automation of judgment.** The pipeline can guarantee the *check
  happens*; it cannot guarantee the *reasoning over what the check found is
  good*. It removes the *"agent didn't bother to check"* failure mode and keeps
  the *"checked and reasoned wrong"* need. Half the discipline (mechanical)
  moves into CORE; the other half (judgment) stays in the agent.
- **Not removal of the human — relocation.** Deterministic *and* adaptive
  reconciles only if every adaptation is itself a governed, versioned proposal.
  That moves the governor from *author of the discipline* to *approver of its
  amendments.* Better placement, not absence.
- **Not LLM-fungibility of the ceiling.** "Any assigned model following the
  pipeline" holds for the *floor* (everyone gets the context, the gates run),
  not the *ceiling* (judgment quality is model-bound). Swap models and the
  measurements partly reset, because they measure the model as much as the
  pipeline.
- **Not a licence to canonicalise intent upfront.** CORE as a *context-injector
  + real-time reconciliation gate* augments the conversation. CORE as an
  *intent-canonicaliser that pre-digests the human before the agent sees them*
  destroys the raw, high-bandwidth exchange that produces the judgment in the
  first place. Keep the dialogue raw; let CORE **inform** it, not **digest** it.
  (MP #4 exists to *measure* this loss, not to license it.)

## 5. Open problems

- **Measuring restraint is the hard 80%.** §3.1 makes it *possible* (log the
  disposition), but pricing a `reconciled-away` against the rework it avoided
  depends on a trustworthy MP #5 baseline. Get the metrics wrong and the result
  is not a dumb system but a *confident, deterministic, self-justifying* one
  that ships more and reconciles less while reporting improvement.
- **The external anchor.** §3.4 proposes falsifiability-plus-sampling. Whether
  that is sufficient corrective once the governor is out of the authoring seat
  is unproven and must be designed on paper before the loop is wired.
- **Premature hardening.** The discipline is still wet clay; this very session
  added to it. Encoding it into governed pipeline logic too early ossifies the
  wrong shape. Sequence matters: learn the discipline, *then* internalise it.

## 6. Relation to existing CORE

- **UR-07 / UR-06** — the grounding, extended from outputs to process.
- **CCC (`CORE-ConstitutionalCoherenceChecker`, ADR-067, ADR-073)** — the
  reconciliation gate is CCC's logic pointed forward at proposals rather than
  backward at the corpus.
- **Workflow stages** (`.intent/workflows/stages/`) — the spine the measurement
  points attach to.
- **`CLAUDE.md`** — the present, trusted-by-default home of the discipline this
  paper proposes to internalise.

## 7. Revisit triggers

- The reconciliation gate ships as a real pre-proposal check — promote the gate
  section from vision to a paper/ADR pair and project it into `.intent/`.
- The first measurement point emits telemetry — this paper's §3.3 becomes a
  data contract, not prose.
- A second model is assigned to the role — §4's floor/ceiling caveat gets its
  first empirical test; record the result here.
