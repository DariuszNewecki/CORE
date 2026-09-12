---
kind: adr
id: ADR-159
title: 'ADR-159 — Acceptance boundary for the autonomy thesis: three thresholds, the containment rule, and the adaptation line'
status: accepted
---

<!-- path: .specs/decisions/ADR-159-autonomy-thesis-acceptance-boundary.md -->

# ADR-159 — Acceptance boundary for the autonomy thesis: three thresholds, the containment rule, and the adaptation line

**Status:** Accepted — governor (D.Newecki), 2026-09-04.
**Date:** 2026-09-04
**Prompted by:** the ITAM Governance Library run — CORE's first attempt to prove *autonomy*
rather than to review a repository or score a benchmark — and the recognition that the
fifteen-gate production-readiness manifest, read on its own, misidentifies gate-closure as the
mission.
**Relates:** `.specs/requirements/URS-production-readiness.md` and
`.specs/attestations/production-readiness.yaml` (the gates this ADR subordinates, D7);
ADR-118 (the `ITAM/` workspace as corpus-coverage and authority precedent — the Trial-1
subject); ADR-156 (fail-closed verdict discipline, applied here to the experiment's own
result); ADR-113 (proven / judged / attested evidence classes, the vocabulary D6 uses).
**Supersedes:** nothing.

---

## Context

### What the first autonomy attempt exposed

The ITAM Governance Library run was not a repository review. It was CORE's first attempt to
produce an autonomy claim, and it established that CORE could not yet produce a trustworthy
one. Six specific failures were surfaced:

- external-catalog execution surfaces did not line up cleanly;
- cognitive roles and LLM resources lacked integrity;
- some blocking rules were not demonstrably enforced;
- dependency unavailability could be read as compliance;
- autonomous approval lacked an independent boundary;
- the consequence chain lacked durable blackboard proof.

Each of those is a break in the same chain: **decide → propose → govern → execute or refuse →
preserve evidence.** The internal work since (#821, G2, G8, unavailable-state handling, the
safe-approval envelope) was corrective work on that chain, not general improvement. It was
justified by, and scoped to, the failed attempt.

That attempt is a sealed artifact, not a recollection. `work/external-validation/`
`phase1-benchmark-SEALED.json` (sealed 2026-08-27, governor-signed; run closed 2026-08-29) pins
both `core_baseline_pin.commit = c4d9fdf9dc52c7d71981e367b64d00b0c994910b` — the CORE state that
produced the diagnostic, confirmed an ancestor of the corrective commits `def9e2b9`, `342db641`,
`22021136`, `133376f2`, `9329c8a0` — and `corpus_pin.repo = DariuszNewecki/ITAM-Governance-Library`
`@ a2fe0a62`. Its eight-row benchmark is the **pre-registered answer key** for the trials below.
Phase 1 was the failed first attempt, not a completed trial; D5 and D6 do not supersede it, they
score against it.

### Why the readiness manifest cannot be the compass

The fifteen-gate manifest is a good instrument and a bad north star. It is unbounded by
construction: every gate closed reveals sub-criteria that were invisible until the gate was
examined (G5 closed its mandatory criterion and disclosed two more; G8 reached full acceptance
proof and disclosed that the remaining work was a signature; G9 closed #822 and disclosed two
further fixtures). Discovery rate exceeds closure rate. By CORE's own Convergence Principle,
the readiness arc — as a *tracking surface* — is diverging.

A product is not finished when no improvements remain. It is finished, at a version, when it
satisfies a **predeclared** acceptance boundary. Absent one, "production-ready" is a horizon:
CORE is permanently almost-ready, and every newly discovered weakness silently becomes a new
prerequisite.

### The unrecorded-intent defect this ADR closes

The repository currently records no north star. A reader with access to the whole tree — a
collaborator, a future governor, or an AI architect reading it cold — will conclude from the
README, the URS, the CI attestation job, and issue #799 that closing the fifteen gates *is* the
mission, because nothing in the tree says otherwise. The actual mission has lived only in
conversation.

That is an unmarked-intent defect of the same class CORE already treats as first-class
elsewhere: an undeclared exclusion in a manifest is indistinguishable from an omission, and an
unrecorded stopping rule is indistinguishable from having none. This ADR is the record.

---

## Decisions

### D1 — The thesis, stated

**CORE is polyvalent governance machinery, not a bespoke governor of its own repository.**

The claim to be proven is:

> CORE governed an unfamiliar target autonomously, safely and explainably, **without requiring
> CORE to be redesigned for that target.**

Success is *not* "CORE found more defects." Defect-finding is a capability the thesis assumes,
not the thesis itself.

### D2 — Three thresholds

Each threshold is a distinct, separately-claimable state. A threshold is reached only when
every criterion under it holds, and — consistent with the attestation manifest's own invariant —
a threshold claim requires dated, human-signed evidence. Claude never signs a threshold.

| Threshold | Criteria |
|---|---|
| **T-A — Experiment-ready** | The two `code.imports.*` rule gaps under #855 reconciled (dead mapping parameters; F821/F401 not testing resolution); CI green on the resulting `main`; G8 governor-attested (`verified_by` + `verified_at` written into `production-readiness.yaml`); the resulting commit frozen and tagged as the certified runner baseline. |
| **T-B — Pilot-ready** | A bounded external-repository autonomy test (D6, Trial 1) succeeds against its declared pass criteria, with honest and reconstructable evidence — including honest reporting of unavailable evidence. |
| **T-C — Production-ready autonomy** | A controlled *write* experiment against a disposable target succeeds; recovery and rollback proven; **then** a sustained soak with no unauthorized writes, no lost proposals and no ambiguous lifecycle states. |

T-A is a state of the runner. T-B is a state of the claim. T-C is a state of sustained
operation. They are ordered and not skippable.

### D3 — The containment rule

**Anything discovered beyond a threshold's declared criteria is backlog, unless it invalidates
the result of the trial in progress.**

"Invalidates" is narrow and must be argued explicitly in writing: the finding must show that
the trial's evidence is *wrong*, not merely that CORE could be *better*. A finding that CORE
has a weakness which did not affect the trial's outcome is backlog. This rule exists to make
the thresholds load-bearing; without it they are advisory and the perpetual-improvement failure
mode returns intact.

No new general framework, architecture programme, or readiness epic may intervene between T-A
and T-B unless it blocks the T-B trial.

### D4 — The adaptation line

The thesis in D1 turns on what "without requiring CORE to be redesigned" means. That line is
drawn **now**, before the trial, so that the outcome cannot be argued after the fact.

**Acceptable adaptation** (consistent with the thesis; expected; measured and reported but not
thesis-negative):

- a target-repository `.intent/` — rules, policies, manifests, authority declarations;
- GRC catalogs and requirement sets (ADR-116 law-as-data);
- domain profiles and applicability gating (ADR-118);
- configuration, resource bindings, and cognitive-role assignment.

**Thesis-negative adaptation** (permitted if necessary, but it MUST be recorded as a negative
result against D1 rather than absorbed as ordinary work):

- new modules under `src/`;
- new check types or rule classes in the audit engine;
- target-specific branches, special-cases, or conditionals in runtime code;
- schema changes made to accommodate the target.

The trial report MUST state, quantitatively, how much of each category the trial required. If
every external repository requires the second category, CORE is not polyvalent — it is being
custom-built repeatedly, and that is a finding about the thesis, not a task list.

### D5 — Trial 0 is a rehearsal of the apparatus, not a proof

**Runner:** the T-A certified baseline. **Subject:** frozen CORE at
`c4d9fdf9dc52c7d71981e367b64d00b0c994910b` (the Phase 1 `core_baseline_pin`), read-only, with no
later issues, commits, ADRs or benchmark answers visible. **Outputs:** stored separately from the
subject and from the runner's own repository.

Trial 0 **cannot** produce evidence for D1, and must not be reported as if it could. The runner
carries part of the subject's answer key in its own `.intent/` — the subject's defects are
described in the runner's rules, vocabulary and decision records. Recovering them demonstrates
neither generalisation nor autonomy.

What Trial 0 *does* prove is (a) the experimental apparatus — read-only enforcement holds; output
isolation holds; no later-state leakage occurs; every outcome is reconstructable from the
blackboard; the mutation and authority boundaries refuse correctly — and (b) **regression-detection
recall against the pre-registered key**: of the eight sealed Phase 1 benchmark rows, how many the
runner independently recovers, stated as a number before any interpretation is offered.

Trial 0's exit criteria are therefore apparatus integrity plus a declared recall figure — *not*
findings volume. Trial 0 findings about the frozen subject beyond the sealed eight are backlog by
D3. The recall figure is a measurement, not a threshold: it does not gate T-B.

### D6 — Trial 1 is the proof

**Subject:** the ITAM Governance Library at `DariuszNewecki/ITAM-Governance-Library @ a2fe0a62`
(the Phase 1 `corpus_pin`; a later pin may be substituted only if recorded in Notes with the
reason) — chosen because it differs from CORE in kind (governed documents, not software
machinery), so success there is evidence of cross-domain portability rather than
self-recognition.

Trial 1 passes only if **all** of the following hold, each answerable from stored evidence by
someone who did not run it:

1. **Comprehension** — CORE operated against the unfamiliar corpus without a human decomposing
   the target for it.
2. **Independent planning** — CORE planned its own investigation and made governed decisions
   about what to examine, rather than executing a human-authored plan.
3. **Boundary respect** — authority and mutation boundaries held; every refusal is attributable
   to a named rule.
4. **Honest unavailability** — where evidence was unavailable, CORE reported it as unavailable.
   Silence read as compliance (the ADR-118 fault) is an outright fail, not a partial pass.
5. **Reconstructability** — every outcome is reconstructable from the blackboard, end to end,
   without access to the runner's logs or source.
6. **Marginal value** — the governed run adds value over the single-agent and multi-agent
   comparison arms.

Criteria 4 and 5 are mandatory: failing either fails the trial regardless of the other four.

### D7 — The fifteen gates are subordinate

The production-readiness gates serve the thresholds; they do not define them. Specifically:

**G11 (upgrade and migration safety)** is reclassified **pilot-blocking for third-party
installation**, not experiment-blocking. Its risk is a damaged database; today there is one
database, one operator, one machine under governor control. It must close before any third
party installs CORE. It does not gate T-A or T-B.

Its recorded status of `not_started` understates the defect and should be corrected to
`not_met` when the gate is next touched. The mechanism exists — `infra/migrations/manifest.yaml`
plus `MigrationService` plus `core._migrations` is a real ordered ledger — but it has never been
proven to work, and three properties are verified against the tree:

- **The ledger is never seeded on a fresh install.** `migrate.py`'s own docstring holds the
  schema snapshot canonical for fresh installs and the ledger for incremental changes on
  existing databases; nothing in `install-core.sh`, `docker-compose.test.yml` or CI calls
  `bootstrap_migrations()`. A fresh install therefore has a current schema and an empty ledger,
  i.e. the full manifest reads as pending.
- **Roughly a third of the ledger is unguarded DDL** — 11 of 38 migration files contain
  `CREATE`/`ALTER`/`DROP` with no `IF [NOT] EXISTS` guard, so that pending set is not safely
  replayable.
- **Apply and record are two independently-committed steps, with no transaction spanning
  both.** `apply_sql_file` opens its own `session.begin()` and is therefore atomic *within* a
  single migration file; `record_applied` then opens a second, separate one. Nothing is atomic
  *across* the sequence. A failure at migration N leaves 1..N-1 applied and recorded with no
  reverse path, and a `record_applied` failure after a committed apply leaves applied-but-
  unrecorded state that fails on retry against the unguarded DDL. URS §G11's rollback criterion
  is therefore **actively violated**, not merely absent — which is `not_met` by the manifest's
  own status vocabulary.

Separately, and in the same drift: the canonical fresh-install snapshot named in `migrate.py`'s
docstring, `infra/sql/db_schema_live.sql`, **does not exist in the tree**. The artifact actually
used is the root `schema.sql`. A reader following the documented model finds nothing.

**G4 (soak)** is a **T-C** criterion only. A sustained-autonomy soak is not a prerequisite for a
first bounded proof, and must not be used to postpone one.

### D8 — This ADR is the north star of record

`README.md` and `URS-production-readiness.md` MUST reference this ADR as the statement of what
the gates are *for*. A reader arriving cold must be able to determine, from the tree alone, that
gate-closure is a means and the autonomy thesis is the end.

### D9 — The evidence apparatus must be retrievable, and inaccessible to the runner under test

`work/*` and `ITAM` are both in `.gitignore` (lines 88 and 48; `ITAM` is a root symlink to an
external mount, never versioned). The sealed benchmark, the VM-302 blind-author isolation runbook
and the neutral catalog-mechanics spec therefore exist on the operator's disk only, outside
version control and outside the tree any reviewer can read.

A sealed artifact nobody else can retrieve is not evidence; it is a claim about evidence. This is
the D8 defect one level down. It is also no longer only a Trial-1 concern: D5's declared recall
figure is itself a scored claim, checked against these same eight rows, and a claim only its
author can check is exactly what this rule forbids.

**Before Trial 0 runs**, the Phase 1 seal MUST become retrievable and integrity-checkable by
someone other than its author. The mechanism is a planning decision, not a constitutional one —
committing the sealed JSON (its blind-author isolation is served by the seal's hash, not by the
file being unreachable), publishing a hash of it, or holding it in a governed store all satisfy
this — but the property is constitutional: **no trial result may rest on an artifact only its
author can produce.** The `.gitignore` entries themselves may remain; what may not remain is the
seal being reachable by exactly one person.

Retrievability and runner-accessibility are not the same property and both bind. Whatever
mechanism satisfies retrievability MUST NOT place the seal, or its eight rows in readable form,
inside the filesystem or `.intent/` the Trial-0 runner has access to while auditing the frozen
subject — a runner that can read its own answer key produces a recall figure of no evidential
value. The harness design (`.specs/planning/`) MUST state affirmatively how it keeps these two
requirements simultaneously true, not merely satisfy whichever one is checked first.

This ADR is itself subject to that constraint: it ships in the runner's own tree, so it references
the seal by pin and location only and MUST NOT enumerate the eight rows, restate their content, or
be amended to do so.

---

## Consequences

- The immediate sequence is fixed: reconcile #855 → verify CI → governor signs G8 → freeze the
  baseline → make the Phase 1 seal retrievable (D9) → Trial 0 (apparatus + recall) → Trial 1
  (the proof). Nothing else intervenes without an explicit D3 invalidation argument.
- The run design for Trials 0 and 1 — harness, isolation mechanics, output layout, procedure —
  is revisable mechanics and belongs in `.specs/planning/`, not here. This ADR fixes only what
  must not drift.
- A trial that fails is a result, not a setback. A failed Trial 1 tells us something true about
  D1; an indefinitely postponed Trial 1 tells us nothing at all.
- Accepting this ADR means accepting that CORE can be *finished at a version* while known
  weaknesses remain open. That is the intended consequence.

---

## Notes

<!-- Append-only. Amendments are added here, never by rewriting the decisions above. -->

### 2026-09-05 — Governor ruling: bounded external-autonomy safety package authorized

Governor ruling, verbatim intent: *"Authorize the bounded safety package now; EC-1A must precede
EC-1B."*

- The bounded pre-experiment safety package (process-level target-binding validation for a future
  external-run command) is authorized to proceed now, as a bounded safety package — not as a
  general readiness programme.
- **EC-1A** (the read-only external-code evaluation) **must precede EC-1B** (the later controlled-
  write evaluation). EC-1B must not begin until EC-1A has completed.
- This ruling does not authorize a general architecture programme, and does not authorize any
  target-specific runtime adaptation. Multi-target support, `Proposal`/database schema changes,
  API work, and `core-cli` work remain out of scope of this ruling.
- This note records the ruling only. It does not alter D1–D9 above, does not redefine T-A/T-B/T-C
  or any G-numbered threshold, and does not resolve where EC-1A/EC-1B sit relative to those
  thresholds — that determination remains for a separate, explicit Governor decision.

### 2026-09-06 — Governor ruling: Unit C fixture safe-auto-approval envelope ratified

Governor ruling, verbatim intent: *"Ratify only `fix.format` for Python files under `package/`,
with only the existing policy declarations required by that action."*

- Authorizes exactly: action `fix.format`; path prefix `package/`; extension `.py`; only the
  existing policy identifier genuinely required by `fix.format`'s current registration —
  `rules/code/purity` (the sole entry in `@register_action(policies=[...])`; `ActionExecutor.
  _validate_policies` is the only runtime consumer of `ActionDefinition.policies`, and it checks
  nothing else for this action — confirmed by direct inspection of `body/atomic/fix/format_code.py`,
  `body/atomic/executor.py`, and `body/atomic/registry.py`).
- Does not authorize: any other action; `tests/`, `scripts/`, `deploy/`, `.intent/`, or
  repository-root files as authorized targets; target-specific runtime logic; new policy meaning;
  new rules or enforcement engines.
- Scope: the Unit C neutral external-target fixture (`tests/fixtures/external_target/`) used to
  prove the target-local authority boundary in isolation, ahead of any write experiment. This note
  records the ruling only — it does not alter D1–D9, redefine any threshold, or authorize execution
  of `fix.format` itself (Unit C is read/validate-only; the controlled write happens in Unit D,
  inside a disposable copy).

### 2026-09-07 — Governor ruling: fixture-local `proposal_consumer_worker` declaration authorized

*Recorded retrospectively, approved 2026-09-10 — this entry is a summary of the 2026-09-07 ruling,
written from the implementing commit, not a verbatim quotation reconstructed from that date.*

- Authorized the fixture-owned `proposal_consumer_worker` declaration solely for
  `package/example.py`, using the production declaration's existing permitted tools —
  `crate.create`, `canary.validate`, `crate.apply`, and `git.commit` — and a fixture-local UUID
  (`b7e25f7a-91f3-4f77-ba34-d29a871c3e0c`, distinct from the production worker's
  `c1d2e3f4-a5b6-7890-cdef-123456789abc`).
- This did not alter CORE's root `.intent/` or broaden the safe-auto-approval envelope —
  `fix.format` on `package/*.py` remained the sole authorized action/path.
- Implemented at `8569f02f5357e843ec05818445b902b5cde90f5e`.

### 2026-09-07 — Governor ruling: `rules/will/proposal_lifecycle` policy dependency authorized

*Recorded retrospectively, approved 2026-09-10 — this entry is a summary of the 2026-09-07 ruling,
written from the implementing commit, not a verbatim quotation reconstructed from that date.*

- Authorized copying the fixture-owned, already-existing `rules/will/proposal_lifecycle` policy
  document into the fixture overlay, byte-identical to CORE's own copy, solely because production
  action `claim.proposal` — invoked internally by `ProposalExecutor` for any proposal regardless of
  the action it carries — declares it as a required policy, and the fixture's minimal
  machinery-floor `.intent/` carried no `rules/will/` tree at all.
- This enabled resolution of an existing dependency; it created no new policy meaning or action
  authority.
- Implemented at `bd2b336f76c51f4d931bace79cd5c7de2983507e`.

### 2026-09-10 — Governor ruling: Trial 0 and Trial 1 runner baselines

- Retained `27160a0a8768cf72bbe2a8fecc3d9169db758efc` (tag `autonomy-experiment-ready-2026-09-04`)
  as Trial 0's runner. Not rebaselined.
- Selected `b57423dc85c11c6650a9515c136bab49b02107ec` (Unit C.1) as Trial 1's separately frozen,
  disclosed runner.
- This does not recertify T-A, does not change Trial 0's baseline, and does not grant threshold
  credit to Units A–E.

### 2026-09-10 — Governor ruling: experiment sequence and EC-1A/EC-1B scope resolved

Resolves the boundary the 2026-09-05 Note above explicitly deferred ("does not resolve where
EC-1A/EC-1B sit relative to those thresholds").

- Sequence: D9 (seal retrievability and isolation) → Trial 0 → Trial 1/T-B (established only if
  ADR-159's criteria pass) → EC-1A → EC-1B → ADR-159's qualifying T-C recovery/rollback/soak work.
- Units D/E remain preliminary, out-of-sequence engineering evidence — they occurred before D9 and
  T-B and receive no T-C or other threshold credit.
- Trial 1 is governance-document evaluation (CORE's Phase 1 apparatus against the frozen ITAM
  Governance Library, D6); EC-1A is the later source-code evaluation. Different subjects,
  modalities, evaluation claims, and thresholds — not folded together.

### 2026-09-10 — Governor ruling: D9 blindness, authorship, and runner boundaries

- The same sealed eight-row Phase 1 benchmark supports both Trial 0 and Trial 1. The semantic
  procedures for both trials, including their prompts, authority boundaries, permitted inputs,
  required outputs, and scoring rules, must therefore be authored and frozen before the seal is
  published in a location accessible to ordinary repository assistants.
- Neither Claude Code nor any session loading CORE project memory may serve as blind procedure
  author or trial runner. Blind procedure authorship must use a fresh stateless session with no
  project memory, conversation history, connectors, repository access, web access, or
  sealed-content access. It receives only the frozen blind-author brief.
- After both semantic procedures are frozen, D9 custody will use a tracked public attestation
  containing the exact sealed artifact and its SHA-256 manifest, provided a non-printing automated
  scan first proves that the artifact contains no credentials or sensitive material. If that scan
  fails, publication is refused and a new custody ruling is required.
- Trial 0 and Trial 1 will be executed by their frozen CORE runners directly inside the isolated
  coldroom substrate. Claude Code is not the runtime wrapper. CORE may use only its pinned
  cognitive/LLM resources. No Claude Code memory, interactive-agent context, connector state, or
  server-side browsing/fetch capability may enter either runner.
- Network access is restricted, not absent. After pinned inputs are provisioned, the runner may
  reach only the exact LLM API endpoints its frozen configuration requires. GitHub and
  content-delivery endpoints remain denied, and model-provider tools capable of server-side
  retrieval, browsing, connectors, URL fetching, or search must be absent or disabled.

### 2026-09-10 — Governor ruling: seal scope correction and operator sign-off

**Seal scope.** This corrects the preceding 2026-09-10 Note's opening statement that "the same
sealed eight-row Phase 1 benchmark supports both Trial 0 and Trial 1." It does not:

- Direct eight-row seal-recall scoring, as D5 describes it, applies to **Trial 0 only**.
- Trial 1's PASS/FAIL is governed exclusively by D6's six criteria. No seal-recall criterion is
  added to Trial 1 by this or any other Note.
- The seal remains unavailable to the Trial 1 governed runner and to the comparison arms, and is
  not opened or used during Trial 1 scoring.

Consequence: the preceding Note's requirement that Trial 1's semantic procedure be frozen before
seal publication no longer derives from seal scoring, because Trial 1 does not score against the
seal. No other text in this ADR (D1–D9) independently requires Trial 1's procedure to be frozen
before seal publication — D9 names only "the Trial-0 runner" in its access constraint, and D6
states Trial 1's six criteria without reference to publication timing. The requirement to freeze
both procedures before seal publication therefore stands as an operational design choice recorded
in `.specs/planning/`, not as an ADR-level requirement for Trial 1 specifically.

**Operator and sign-off.** The Governor states he has not read the sealed benchmark. The trial
design does not rely on that fact: the Run Operator role is deterministic and mechanical (detailed
in `.specs/planning/CORE-D9-Trial0-Apparatus-Design.md`), so operator blindness is not a control
this ADR depends on.

Stateless computational instances may perform independence roles — witnessing, reconstruction,
scoring, adjudication. These substitutions never transfer constitutional sign-off: the human
Governor alone accepts threshold evidence and authorizes progression (D2: "Claude never signs a
threshold").

### 2026-09-12 — Governor ruling: D3 invalidation filed against the preregistered trial sequence

On 2026-09-12 the Governor filed a D3 invalidation against the preregistered trial sequence.

**Ground.** `.specs/planning/CORE-Autonomy-Trial-Runner-Interface-Appendix.md` establishes, by
direct object-level inspection of both frozen runner pins (`27160a0a...`, `b57423dc...`,
byte-identical on every file cited), that neither pin exposes an interface matching what the
blind-authored Trial 0 and Trial 1 procedures assume (Document A §A6 / Document B §B6): a
component that accepts a free-text goal, autonomously plans and executes a multi-step
investigation, and records its own findings to the blackboard. The appendix's addendum further
finds that the one production, non-agentic route for external-repository governance present at
either pin — BYOR onboarding into `--offline` audit — does not close this gap: `--offline` audit
produces **no blackboard record of any kind** (`stateless_audit.py`'s own docstring: "No
filesystem writes. No DB access... No worker dispatch"), and both BYOR and Scout's write paths are
**unreachable end-to-end at both pins** (BYOR has no CLI wiring at either pin; Scout's full
`induce_rules` has zero call sites in `src/`, and its live API route explicitly does not write,
with no CLI caller of either the route or `induce_rules` present at either pin). Mapped against
D6's criteria: C1 (comprehension) and C2 (independent planning) are unsupported, and **C5
(reconstructability), mandatory per D6, is unsupported** — there is nothing to reconstruct from.

This is a written invalidation argument, not a report of a weakness the D3 containment rule would
route to backlog: the finding does not say CORE could be better, it says the trial as
preregistered cannot produce the evidence D6 requires, because the runner it would run against
cannot execute the procedure the trial assumes.

**Consequence.** Trial 0 and Trial 1 are suspended. They are not cancelled, rebaselined, or
loosened. Both pins remain frozen exactly as recorded in the 2026-09-10 Note above
(`27160a0a...` for Trial 0, `b57423dc...` for Trial 1). No trial may start until a new runner
baseline is certified against D6's criteria — certification, not a patch to either existing pin
mid-flight, consistent with D5's own instruction that the frozen runner is never patched during a
trial.

**Root cause.** The T-A gate set (G1–G8) certified CORE's governance machinery — policy
validation, impact authorization, the blackboard, the proposal lifecycle — without testing
whether CORE could execute the specific experiment that machinery was certified for. Record this
as the defect to avoid when defining any future readiness gate: a certified baseline is evidence
that CORE is safe to run, not evidence that CORE has anything to run.

**D9 and the seal work remain valid, and are deferred, not discarded.** Nothing in this
invalidation reopens D9's custody requirements, the blind-author brief, or the frozen procedures
themselves (`.specs/attestations/adr-159-blind-author-raw-claude-opus-5-20260910.md`). They
resume once a certified runner baseline exists.

**Remediation scope — and nothing beyond it.** CORE must gain:

1. an interface accepting a target and a goal;
2. self-directed planning of its own investigation;
3. Blackboard recording of findings, refusals, and explicit unavailability;
4. export of that record.

`706437a6` (#873) addresses item 3 in part — a genuine `GoalExecutionWorker` making one
CORE-internal goal-driven run reconstructable from the blackboard, with a correlated run
identity. It does not address items 1, 2, or 4, and does not by itself make Trial 0 or Trial 1
runnable.

### 2026-09-12 — Governor ruling: three cold-review tightenings to the D3 invalidation Note

**a. Certification wording.** Verified: D6's criteria (above) include criterion 6, "Marginal
value — the governed run adds value over the single-agent and multi-agent comparison arms," which
cannot be evaluated without running Trial 1 itself — there is no arm comparison to measure before
the trial runs. The preceding Note's "certified against D6's criteria" therefore names a
certification condition Trial 1's own outcome would need to satisfy, which a runner cannot be
certified against in advance.

Corrected: the new runner baseline must be certified as capable of executing the frozen
procedures (Document A / Document B, per the blind-author brief) and producing the evidence
required to evaluate D5 and D6 — not certified against D6's criteria themselves. Runner readiness
and trial success are distinct: the former is a property of the apparatus, checkable before any
trial runs; the latter is the trial's own result.

**b. Remediation item 2 is too broad.** Verified against
`.specs/planning/CORE-Autonomy-Mission-Runner-Reconnaissance.md`: both frozen pins already
contain a goal-driven planner. `develop_from_goal` reaches `ParsePhase.execute()`, which calls
`PlannerAgent.create_execution_plan(goal)` — "a real LLM call... genuine plan synthesis, not
fixed pattern matching" (document item 1, point 4) — byte-identical at both pins and current
HEAD. What the document confirms absent is: external-target binding (item 1, point 3: "no traced
path accepts a path or repository parameter"); target reconnaissance before planning (item 1,
point 4: `reconnaissance_report` is always empty; "`ReconnaissanceAgent` does not exist anywhere
in `src/` at any of the three refs"); document-corpus operation (item 1, point 10: "source code
only... no document-corpus workflow exists"); and Blackboard evidence and export (item 1, points
7-8: "zero matches" for any blackboard call in the chain; "no blackboard export to reconstruct
from").

Remediation item 2 ("self-directed planning of its own investigation") is restated: the missing
capability is **target-grounded reconnaissance and comprehension followed by self-directed
investigation planning over an unfamiliar bound target** — not "self-directed planning" bare,
which already exists in `PlannerAgent` and risks building a redundant second planner rather than
extending the one that already works.

**c. Rebaselining does not reset D4 adaptation accounting.** Verified: `GoalExecutionWorker`
already documents itself as D4 thesis-negative adaptation — the implementing module's own
docstring states it is "the genuine Worker that owns goal-driven execution and its Blackboard
evidence lifecycle (#872, ADR-159 D4 thesis-negative adaptation)"
(`src/will/autonomy/autonomous_developer.py:10-13`), and the Worker's own module docstring names
its out-of-scope boundary against "ADR-159 D4 / #872" directly
(`src/will/workers/goal_execution_worker.py:44-49`). This stands as the worked example: any
remediation required to make the preregistered trial executable that falls into D4's
thesis-negative categories (new `src/` modules, new check/rule classes, target-specific branches,
schema changes) remains quantified and reported in the eventual Trial 1 result. Rebaselining the
runner does not zero this accounting — it is cumulative across the remediation, not reset at each
new frozen pin.
