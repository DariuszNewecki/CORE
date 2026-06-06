<!-- path: .specs/concepts/CORE-URS-Intake-Concept.md -->

# CONCEPT — CORE URS Intake

**Status:** Concept (exploratory — this is a new artifact class; not a paper, not a URS, not an ADR)
**Authority:** Pre-requirements thinking
**Scope:** The bootstrap-paradox gap — CORE has no surface that takes external intent as input, processes it through the constitutional pipeline, and reports back to the governor.
**Audience:** Governor (architect, intent author) and future authors of the URS that would formalize this concept.
**Date:** 2026-06-06
**Authors:** Darek (Dariusz Newecki) + Claude (joint exploration this session)
**Relates:** ADR-085 (the 5+3 list whose existence lives outside CORE's awareness today), URS-mechanism-coherence (the closest pattern in the coherence family — but checks rules' mechanisms, not URSs' fulfillment), `.specs/papers/CORE-ConstitutionalCoherenceChecker.md` (CCC — document-vs-document coherence, again a different layer).

---

## 1. Why this concept exists

This session surfaced a question the governor had been carrying without yet naming:

> "CORE has a lot to sustain dumbest coder on earth. But where is anything in CORE that tells CORE what needs to be developed next?"

Verified by grep, not by emphatic agreement: zero. CORE has:

- A constitutional governance engine (`.intent/` rules)
- An audit pipeline (finds violations)
- An autonomous remediation loop (fixes violations through proposals)
- A coherence family (CCC document-vs-document; ADR-027 fix-vs-violation; URS-mechanism-coherence the third layer in flight)
- Self-derived intake (TestCoverageSensor walks `src/`; AuditViolationSensor walks `src/`)

CORE does not have:

- A reader for `.specs/papers/`, `.specs/requirements/`, `.specs/planning/` that asks "does CORE fulfill this?"
- A reader for `.specs/decisions/` (ADRs) that asks "has this decision been enacted?"
- An inbound integration to GitHub (the 7 src/ files that mention "github" all *emit* — F-10's annotation formatter — none receive)
- A surface that consumes ADR-085's 5+3 list and routes capacity (the planning doc is read by the governor, never by CORE)

CORE is a software factory with a production floor, QA, packing, and shipping — but no order desk. The orders have always been the governor, speaking through a Claude Code CLI session, into the file system.

This concept records the governor's intent to build the order desk.

## 2. Grounding in existing coherence-family work

This concept is the *fourth* layer in the coherence family, distinct from the three already named (memory `reference_coherence_family_three_layers`):

| Layer | Asks | Status |
|---|---|---|
| Document (CCC + ADR-067) | Do constitutional documents agree with each other? | Shipped |
| Mechanism (URS-mechanism-coherence v0.1) | Does each rule's running mechanism honor its declaration? | URS only |
| Remediation (ADR-027) | Did the fix actually fix? | Shipped |
| **Intent (this CONCEPT)** | **Does CORE's runtime honor what URSs claim it should do?** | **Concept only — needs URS, then paper, then ADR** |

The fourth layer is upstream of all three: a URS *makes a claim* about what the system should do. The three existing layers verify the constitution against itself once the claim has been encoded. This layer verifies whether the encoding even matches the claim.

URS-mechanism-coherence asks "does the *rule* honor its declaration?" The Intent layer asks "does *CORE itself* honor the URS's claim of what CORE is for?" Same family discipline (deterministic verification, fixtures, fail-closed), different subject of verification.

## 3. The sketched intake pipeline

What the governor sketched, joint-formalized through this session:

```
URS author (governor) writes/updates .specs/requirements/URS-X.md
   ↓
[1] URS schema validates structural shape
   ↓
[2] URS Verifier asks "is CORE's current state already meeting URS-X's acceptance criteria?"
       ├─ YES → mark satisfied, no further work
       ├─ PARTIAL → continue with the unsatisfied subset
       └─ NO → continue with the full set
   ↓
[3] URS Decomposer breaks unsatisfied criteria into CORE-digestible work:
       new feature? new shared functionality? new atomic action? amend existing ADR?
   ↓
[4] ADR Proposer drafts the governance decision(s) the decomposition implies
   ↓
[5] Governor approval gate — accept / reject / amend the ADR(s)
   ↓
[6] Administrator files GitHub issues, dispatches workers, queues
    human-intervention requests where decomposition flagged judgment-only work
   ↓
[7] Execution under existing pipelines (atomic actions, proposal consumer,
    audit loop, etc. — this is what CORE already has)
   ↓
[8] URS Verifier re-runs and reports satisfaction delta
```

## 4. Hidden dragons per stage

Each stage has a known-hard problem that, if ignored, will collapse the pipeline under unhappy paths.

### Stage 1 — URS schema

**Today's reality:** `.specs/requirements/` exists, holds 5 URSs (`CORE-Ask-URS.md`, `CORE-Governor-Ask-URS.md`, `CORE-Governor-Dashboard-URS.md`, `URS-consequence-chain.md`, `URS-mechanism-coherence.md`), format inconsistent (per memory `reference_coherence_family_three_layers` URS directory note). No `urs_document.schema.json` in `.intent/META/`.

**Dragon:** The schema must balance "rigid enough to parse mechanically" with "loose enough to author at thinking-speed." Over-schematized URSs become forms; under-schematized URSs become prose blobs the Verifier can't operate on. CCC paper §5's coverage-manifest discipline is the closest precedent — every URS section maps to a known kind, every unknown kind is a coverage finding.

### Stage 2 — Verifier

**Today's reality:** Nothing reads URSs. Two adjacent patterns exist that don't transfer cleanly: CCC walks `.specs/papers/` for *document* coherence (does paper A cite paper B's claim correctly?); the audit pipeline walks `src/` for *rule* compliance. Neither asks "is this URS's claim satisfied by current state?"

**Dragon:** **This is the load-bearing stage.** Verification splits into three classes:
- **Mechanical** — existence checks, grep predicates, type matches (e.g., URS says "fix.* exists for rule X" → grep `@register_action` decorators)
- **Behavioral** — fixture-driven, deterministic execution against known inputs (the URS-mechanism-coherence shape, R-004 + R-005)
- **Judgmental** — requires human observation (URS #561 "outside developer reproduces install from public docs" — no scanner can verify)

The Verifier must *classify which class* a criterion belongs to. A URS that mixes the three (most do) needs per-criterion classification with per-criterion verification path. R-007's coverage manifest applies: every criterion is `checked` or `skipped`-with-rationale.

### Stage 3 — Decomposer

**Today's reality:** CORE has `Flow` declarations and `@atomic_action`s. Composition vocabulary is small and well-shaped. But the gap from URS to action-shape requires deciding *which kind* of work the URS implies — and that kind may not exist as a registered shape today.

**Dragon:** Recursive. If the URS implies a new atomic-action shape that doesn't exist (e.g., URS asks for non-Python remediation — the F-43 conversation we just had), the decomposer is proposing a *code-shape change*. Proposing a new action requires `@register_action` additions, which IS implementation, which IS what we're trying to decompose into. The recursion needs a base case: at some level of decomposition, the work has to fit existing shapes OR the proposal becomes "amend the shape vocabulary first."

### Stage 4 — ADR Proposer

**Today's reality:** ADRs are governor-authored prose with structured frontmatter. CoderAgent → cognitive_service → LLM generates code, not governance. No "ADR Drafter" cognitive role.

**Dragon:** ADR authorship requires *citation discipline* (referencing prior decisions, the URS itself, the relevant memory artifacts, the ADR-074 D13 / ADR-080 §D5 append-only patterns). Today the governor + Claude Code CLI handle this through broad-context reading; a focused cognitive role would need retrieval over `.specs/decisions/` + the URS + the memory store. Prompt engineering is heavier than for code generation because the output must satisfy *constitutional* validity (an ADR that contradicts an existing ADR without naming the amendment is invalid).

### Stage 5 — Approval gate

**Today's reality:** `Proposal.approval_required = true` exists as the primitive for per-action approval. The governor dashboard surfaces "1 approval required" (this morning's count).

**Dragon:** **Wrong grain.** Today's approval is "execute fix.docstrings on file X." The URS pipeline's approval is "accept this multi-ADR change-set + downstream issue plan + human-intervention queue." That's a *bundle* with a *plan*. The review surface needs to support reading multiple ADR drafts side-by-side, asking for revisions on specific decisions while keeping others, and approving with conditions. No existing surface supports that grain.

### Stage 6 — Administrator

**Today's reality:** Zero GH inbound; zero GH outbound (no API client, no `GH_TOKEN` usage). Filing issues happens via Claude Code CLI invoking `gh issue create`. The "human intervention request" pattern doesn't exist as a first-class blackboard entry — today's blackboard subjects are sensor findings, proposal outcomes, worker heartbeats; none are "governor, please decide X."

**Dragon (two of them):**
1. **Outbound integration** is straightforward engineering (write a GH API client, `GH_TOKEN` config, error handling). Bounded.
2. **Human-intervention-as-data** is the conversation-as-data problem. Blackboard is async + finding-shaped; intervention is dialogue + clarification + revision. The grain mismatch is real. CORE's proposal pipeline doesn't model "ask the governor a clarifying question" as a first-class state.

## 5. Happy path is the easy design

The governor explicitly named this: the pipeline above is the *happy path*. The honest architectural questions live in the unhappy paths:

- **URS contradicts an existing ADR** — Verifier finds satisfaction-impossible-without-amendment. Decomposer must propose amending the ADR (constitutional change), not just adding a feature.
- **URS underspecified** — Decomposer can't find a CORE-digestible shape. Loops back to governor with a clarification request. Today's pipeline has no clarification primitive.
- **Decomposer's proposal stalls** — needs an atomic-action shape that doesn't exist, requiring meta-decomposition.
- **Governor rejects ADR proposal three times in a row** — the system needs a "this URS is contentious, route to slower deliberation" signal, not just retry with another LLM pass.
- **Intervention queue grows faster than it drains** — back-pressure. The dashboard's "Governor Inbox" red signal (175 indeterminate) is the existing instance of this dragon; URS intake adds another class.
- **Verifier says satisfied; reality drifts afterward** — the freshness problem. Verification is a snapshot; satisfaction can decay. Periodic re-verification needed but cadence unknown.

Each unhappy path is its own design problem. The CONCEPT does not solve them; it names them so a URS author can decide which to scope in/out.

## 6. What this CONCEPT explicitly does NOT do

- It does not specify the URS schema (Stage 1 dragon — separate URS-level work).
- It does not name the Verifier's classification taxonomy beyond "mechanical / behavioral / judgmental" (Stage 2 dragon — needs URS).
- It does not decide where the Decomposer lives (worker? service? cognitive role?). The recursion problem (Stage 3 dragon) is acknowledged but not closed.
- It does not pre-commit ADR-091 D6-style forward contracts. Forward contracts are decision artifacts; CONCEPTs come before decisions.
- It does not bind which existing instruments the intake pipeline reuses (e.g., should it share CoherenceSensorWorker's chain-of-resolution semantics, or define its own?). That's an ADR-level call.

## 7. Non-rivalry with existing intent

This CONCEPT does not displace or supersede:

- **URS-mechanism-coherence v0.1** — that URS owns the rule-vs-mechanism layer. This CONCEPT owns the URS-vs-runtime layer. Both are needed; they verify different things.
- **CCC + ADR-067** — document coherence is upstream of URS quality but doesn't verify implementation.
- **The autonomous remediation loop** — that loop handles constitutional-debt remediation (audit violations have a fix.*). This CONCEPT handles intent-to-implementation, which is a different lifecycle.

## 8. Open questions worth surfacing before drafting the URS

1. Is `.specs/requirements/` the right home for URS, or is a more structured subtree warranted (e.g., `.specs/requirements/intake/`)?
2. Does URS authorship require an existing pattern (ADR-085 the closest), or is URS shape itself part of what needs declaring?
3. Should the Verifier's classification of criteria (mechanical / behavioral / judgmental) be declared per-criterion in the URS, or inferred at verification time?
4. Where does the ADR Proposer's output land before approval — proposal table? new staging area? Markdown draft files committed to `.specs/decisions/drafts/`?
5. How does the Administrator distinguish "file an issue for governor visibility" from "file an issue and assign back to the autonomous loop"?
6. What is the freshness model — when does Verifier re-run? Cron? Event-driven by `.specs/` changes? Both?

## 9. Path forward — how this CONCEPT matures

This CONCEPT is the seed. The path from here, mirroring the CCC / URS-mechanism-coherence pattern:

```
CONCEPT (this doc)
   ↓ governor reads, names what's load-bearing
URS — formal requirements (R-001 .. R-NNN), acceptance criteria
   ↓ governor accepts URS as governing requirement
PAPER — operational design (chain definition, fixture format, trusted kernel)
   ↓ paper accepted as canonical architecture
ADR(s) — storage schema, CLI surface, scheduling, dashboard, governance integration
   ↓ ADRs accepted
Implementation under existing pipelines
```

The CONCEPT exists so the URS author has a place to argue *against* before committing to formal requirements. Concepts are debatable; URSs are governance.

## 10. Self-reflection — why a CONCEPT artifact class at all

This document is itself an admission: the governor's thinking arrived at a question (the intake gap) that the existing artifact classes (URS, paper, ADR) are too formal to receive at this stage of maturity. CCC went straight from paper to ADR; URS-mechanism-coherence sits at v0.1 URS without a paper. Both bypassed the pre-URS exploratory stage because the gap they identified had clearer prior art.

The URS intake gap doesn't have clearer prior art. There's no obvious existing pattern to point at and say "do that, but for `.specs/`." The CONCEPT class exists to hold the *understanding* phase the governor named: *"designing new feature is not difficult, having good understanding what it means is even harder."*

If this CONCEPT matures into a URS, the precedent — that ill-defined intake problems get a CONCEPT before a URS — is itself worth codifying. If it doesn't mature, this document becomes a checkpoint of what was considered and why nothing further was built. Either outcome is honest.

---

## 11. Reception and freeze

This CONCEPT received four substantive external reviews on the day it was authored. Their convergence and divergence are recorded here so the maturation path is honest about which subsequent decisions were already argued.

### Convergence across reviews (3-of-4 or 4-of-4 agreement)

1. **MVP-narrow.** All four reviewers, differently phrased, agree the first iteration must scope to the Verifier alone — no decomposer, no ADR proposer, no GitHub adapter, no conversation primitives. The mega-orchestrator framing in §3 of this CONCEPT is correct as architecture but wrong as first-shipment scope.
2. **Classification declared by URS author, not inferred.** Open question 3 in §8 is answered: each acceptance criterion shall carry declared `verification_class` (mechanical | behavioral | judgmental) metadata, with the Verifier authorized to *reject* misclassified criteria but not to silently reclassify them. Authority over verification strategy stays with the URS author.
3. **CONCEPT artifact class needs its own governance.** §10's by-fiat introduction is structurally sound as exploratory honesty but is itself a coherence finding (`.specs/` artifact-class taxonomy is not governed the way `.intent/taxonomies/` is, per ADR-068). The downstream URS or a separate META decision shall codify CONCEPT's lifecycle states (exploratory → promoted-to-URS → archived → rejected) and bounds (what a CONCEPT may and may not do).
4. **Decomposer recursion (§4 Stage 3) is unresolved at architectural level.** Reviewers agree the base case isn't proven; one reviewer warns the loop could be non-terminating for certain URS classes. Sequencing implication: the decomposer does not ship in the first URS or its operationalizing paper. Re-opens later when the Verifier's evidence shapes the decomposition vocabulary.

### Strongest single architectural correction (Reviewer 1)

> "A `URSSatisfactionSensor` that walks `.specs/requirements/` and emits 'URS-X criterion 3 unsatisfied' findings is architecturally continuous — not a new pipeline. Collapses Stages 1-2 into existing sensor/finding machinery."

This reframe is adopted by the downstream URS. The CONCEPT's 8-stage pipeline framing is correct as the eventual full shape but conflates "new architectural class" with "new sensor instance of an existing class" for Stages 1–2. The sensor reframe also makes the freshness problem (§8 open Q4) trivial — sensors run on the existing cycle, no new schedule.

### Divergence requiring governor's call

- **Reviewer 1 vs Reviewer 4 on the human-intervention-as-data primitive.** R1: collapse to two findings + a URS edit, reusing `resolution_authority: principal.governor` (#428's in-flight work). R4: new first-class `DecisionRequest` object with rich state. Governor decision (2026-06-06): R1's collapse is the v0 path — fewer new primitives, leans on existing in-flight governance. R4's structured object remains available as a view layer if the primitive proves insufficient.
- **Reviewer 4's "URSs are accepted requirement claims, not law"** softens the URS authority too far against URS-mechanism-coherence R-003 ("silent-inert is a constitutional violation of the same class as a contradicting ADR"). Governor framing preserved: URSs declare what shall be true; ADRs decide how that truth is constructed in the architecture. Both governed, different roles.

### Substantive critiques nobody else made

- **Reviewer 3 — Stage 2 double-duty.** The classification taxonomy in §4 Stage 2 conflates *verification strategy* (how do we check?) with *criterion kind* (what kind of claim?). These can diverge. Open whether the downstream URS separates them or admits the divergence cases explicitly.
- **Reviewer 1 — Verifier self-qualification.** "Instrument qualification before trust" applies to the Verifier itself. The CONCEPT names trust models for criteria but not for the instrument that adjudicates them.

### Critiques the reviews collectively missed

- **None tested the existing 5 URSs against the proposed criterion-manifest reform.** Retrofitting `CORE-Ask-URS.md`, `CORE-Governor-Ask-URS.md`, `CORE-Governor-Dashboard-URS.md`, `URS-consequence-chain.md`, and `URS-mechanism-coherence.md` to carry declared classification metadata is not free. The downstream URS shall name retrofit sequencing as a non-requirement (deferred work) so it doesn't gate v0 shipment.
- **Recursive depth.** If CONCEPT becomes a governed META kind, this very document becomes something the URS-intake pipeline would eventually verify against. Cute or load-bearing? Reviews didn't ask; URS shall not yet answer.

### Freeze decision (2026-06-06)

This CONCEPT is **frozen as of 2026-06-06**. Its body shall not be revised; subsequent thinking lands in the downstream URS (`URS-requirement-fulfillment-verification`) and the artifacts that flow from it. The convergence points above are baked into the URS rather than back-ported to the CONCEPT. The CONCEPT becomes the historical record of what was considered before requirements crystallized; the URS becomes the active design surface.

The freeze is honest about the CONCEPT's limits: it named the gap, framed the dragons, and made external review possible. The strongest correction (Reviewer 1's sensor reframe) is one that none of the joint authors saw until external eyes pointed at it. Recording that the document was reviewed and where it fell short is more valuable than silently revising it to look retrospectively correct — per memory [[docs_must_mirror_code_reality]] (fuller mirror over tighter narrative).

### Path forward (active link)

- **URS:** `.specs/requirements/URS-requirement-fulfillment-verification.md` — the v0 URS that operationalizes only the Verifier (Stages 1–2), reframed as a sensor per Reviewer 1, with declared classification per Reviewers 2/3/4.
- **Future CONCEPT (possible):** A separate CONCEPT on conversation-as-data may be warranted if R1's "collapse to findings + URS edit" pattern proves insufficient under load. Reviewer 3 suggested this carve-out explicitly; this CONCEPT does not pre-commit it.
