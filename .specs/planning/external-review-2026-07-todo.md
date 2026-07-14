<!-- path: .specs/planning/external-review-2026-07-todo.md -->
---
kind: planning
title: "ToDo — External Architecture Review (2026-07)"
status: active
---

# ToDo — External Architecture Review (2026-07)

**Basis:** external reviewer's report against public snapshot `87182fa0` (2026-07-12).
**Method:** every testable claim verified against source — 12 directly (session of 2026-07-12) +
6 parallel verification agents covering §1–§9. Each line below carries a verdict and a citation.
**Rule:** only **confirmed-and-open** findings are ToDos. Refuted, stale, healthy-by-design, and
already-done items are listed at the bottom so the accounting is complete and nothing masquerades
as work.

**Progress (2026-07-12):** six commits on `main`. **Done:** T1.1 law layer `4200ba48` (machinery →
#763) · T2.2 symlink `bf15cbc1` · T2.3 modularity→operational_config `66cf7316` (closed #767) ·
T2.4 retire MicroProposalExecutor `df2b1551` (closed #768) · T3.1 digest reconciled `f50249f2`
(class-fix → #775) · T3.2 comment `50e01bc3`.

**Progress update (2026-07-14):** every remaining tracked issue from the 2026-07-12 batch has
since closed except two. **Closed:** #763 (T1.1 finalization-barrier machinery) · #764 (T1.2
outbox, `e6adbd97`) · #765 (T1.3 instrument taxonomy, `6091d64d`) · #766 (T2.1 TestRunnerSensor,
`f17eb794`) · #769 (T4.1 fix.modularity/ADR-140, `e05e7a7f`) · #770 (T4.3 route-op gate,
`60441213`) · #771 (T4.4 API thinness, `20c80a8a`) · #772 (T4.5 work/ taxonomy, `84a8b491`) ·
#775 (digest drift-gate, `99532a3e`). **Still open:**
#773 (T5 test hardening) · #774 (ADR-040 literal sweep — 5 commits landed as of 2026-07-14,
sweep continues). Tier 1–4 items below are retained for their technical detail but are no
longer open ToDos — see the closure marks inline and the "Not ToDos" section. **One exception: T4.2** (worker-import excludes) is only half-done — the rule shipped (#723) but the excludes removal is still open and untracked; see its corrected note in Tier 4.

---

## Tier 1 — "make success provable" (evidence completeness / honesty · NorthStar-anchored)
**All closed as of 2026-07-14.**

The review's spine: CORE has strong front-of-chain controls but reports some successes it cannot
fully back with durable evidence. Three instances of one class.

- [~] **T1.1 — Proposal finalization barrier.** `COMPLETED` becomes a proof state.
  *Verdict:* CONFIRMED (crux). *Status:* **ADR-148 accepted; law layer committed (`4200ba48`);
  machinery tracked in #763.** Not re-listed here — see #763.
- [x] **CLOSED — #764.** **T1.2 — Creation-side dual-write / finding→proposal outbox (§4d).** A proposal is reported
  *created* while its findings may not be durably linked. *Verdict:* CONFIRMED —
  `defer_to_proposal` (`will/workers/violation_remediator_blackboard.py`) wraps
  `blackboard_proposal_service.defer_entries_to_proposal` fail-soft (docstring: "a revival-layer
  failure here does not reverse the caller's proposal_created accounting"). Breaks the §7a revival
  contract (orphaned findings / duplicate proposals). *Effort:* [family] transactional — bind
  proposal creation + finding deferral (outbox). ADR-148 named this out-of-scope-next.
- [x] **CLOSED — #765.** **T1.3 — Instrument availability: "no findings" ≠ "couldn't look" (§4c/§5e).** *Verdict:*
  CONFIRMED across sampled workers — `post_heartbeat()` is posted *before* the input query and
  satisfies the silence invariant, so an input that returns **empty without raising** reads as
  genuinely clean (only inputs that *raise* are caught, via the Model-B cycle-error report).
  Sensors affected: `TestCoverageSensor`, `ProposalConsumerWorker`, `TestRunnerSensor`;
  `TestRemediatorWorker` additionally posts no all-clear report. *Effort:* [decision] instrument-
  result taxonomy (clean / found / unavailable / indeterminate — CORE already has the
  `Indeterminate` vocabulary term); subsumes T2.1.

## Tier 2 — bounded code fixes (confirmed concrete bugs)
**All closed as of 2026-07-14.**

- [x] **CLOSED — #766.** **T2.1 — `TestRunnerSensor` silent infra-drop (§5e).** On a pytest-infra exception, `run()`
  logs, `resolve_entries([entry_id])`, and `continue`s with no replacement finding — the test-gen
  chain loses its trigger. *Verdict:* CONFIRMED (`will/workers/test_runner_sensor.py::run`).
  *Effort:* [bounded] the evidence-preserving pattern already exists in the same file
  (`_adjudicate_test_quarantine` keeps subjects retryable) — apply it to `run()`.
- [x] **CLOSED — landed `bf15cbc1` (2026-07-12).** **T2.2 — ADR-147 (b) second symlink-dereference site.** *Verdict:* CONFIRMED — the fix landed
  at `crate_processing_service._run_canary_validation` (`symlinks=True`) but
  `FileHandler.copy_repo_snapshot` (`body/infrastructure/storage/file_handler.py`) still calls
  `shutil.copytree(...)` without `symlinks=True` — the same dereference defect, live. *Effort:*
  [bounded] one-line fix + regression test.
- [x] **CLOSED — #767, `66cf7316`.** **T2.3 — `modularity_fix` raw `.intent` read.** `_load_split_confidence_threshold`
  (`body/atomic/modularity_fix.py`) reads governance YAML via `PathResolver` + `yaml.safe_load`
  with a bare-except silent fallback, bypassing `IntentRepository`. *Verdict:* CONFIRMED. *Effort:*
  [bounded] route through the intent repository / a typed config projection.
- [x] **CLOSED — #768, `df2b1551`.** **T2.4 — Retire dormant `MicroProposalExecutor`.** Ungoverned parallel-mutation path (raw
  `.intent` read, placeholder validation-report accept, own `FileHandler`, no ActionExecutor/
  sandbox/persistence). *Verdict:* CONFIRMED dead code — **zero prod + zero test call sites.**
  *Effort:* [cheap] delete `body/autonomy/micro_proposal_executor.py` + doc refs.

## Tier 3 — cheap doc / config cleanups (confirmed)
**All closed as of 2026-07-14.**

- [x] **CLOSED — #775, `99532a3e`.** **T3.1 — Rule digest drift in `CLAUDE.md`.** Digest says 35+27+9=71; source is
  **37+28+8=73**. *Verdict:* CONFIRMED (`jq` over `.intent/rules/architecture/*.json`). *Effort:*
  [cheap] correct the digest.
- [x] **CLOSED — landed `50e01bc3` (2026-07-12).** **T3.2 — Stale layer-mapping comment.** `layer_separation.yaml` RULE 6 marks consequence-log
  extraction `(pending)`, but `ConsequenceLogService` exists in Body and `ProposalExecutor` already
  delegates to it. *Verdict:* CONFIRMED. *Effort:* [cheap] drop the stale annotation.

## Tier 4 — governance / architecture (confirmed; decision or bounded work)
**All closed as of 2026-07-14 except T4.2** (worker-import excludes: rule shipped, excludes-removal still open).

- [x] **CLOSED — #769, `e05e7a7f`.** **T4.1 — `fix.modularity` violates ADR-140 (§2f).** Not merely a stale rationale: the
  `modularity_analyze` prompt rationale still says "Body-layer LLM call," and
  `body/atomic/modularity_fix.py` **still does it** — `PromptModel.load("modularity_analyze")` +
  `cognitive_service.aget_client_for_role(...)` inline in the Body action, which ADR-140 D1 forbids.
  *Verdict:* CONFIRMED — ADR-140 was not applied to this action. *Effort:* [decision+refactor]
  migrate to the cognitive/write split (Will-injected `StepKind.COGNITIVE` → Body terminal writer),
  then fix the rationale. (May naturally shrink T6.1.)
- [~] **PARTIAL — rule shipped (#723, `7dc46e57`), excludes NOT yet removed (still open, untracked).** **T4.2 — Worker-helper whole-file exclusions (§1a/§2a).** RULE 16
  `architecture.workers.no_direct_worker_import` carries **6 whole-file `excludes:`** under
  `will/workers/` (proposal_consumer_worker, proposal_pipeline_shop_manager, violation_remediator,
  violation_remediator_proposal, audit_violation_sensor, violation_executor). An excluded file could
  acquire a real worker→worker import without the rule firing. *Verdict:* CONFIRMED (tracked as
  #723). *Effort:* [refactor] extract helpers out of `will/workers/`, then remove the excludes.
  **Correction (2026-07-14):** #723 created the AST rule and is closed, but the 6 whole-file
  excludes are **still present** in `.intent/enforcement/mappings/architecture/layer_separation.yaml`
  (labeled "Pending extraction ... #723 follow-up"). The exclusion-removal half — the actual point
  of T4.2 — is open and has no tracking issue. Confirmed by the 2026-07-14 external review (findings
  1a/2a/7a) and re-verified against the mapping file. An earlier note in this doc mismarked T4.2 as
  fully closed off #723's closure; that was closed-by-issue-reference, not closed-by-evidence.
- [x] **CLOSED — #770, `60441213`.** **T4.3 — Route-operation sensitivity classification (§6d).** In a `user-facing` router, the
  AST checker permits per-route `require_governor` gates but never verifies them, so a newly added
  sensitive route could ship un-gated and pass the rule. *Verdict:* CONFIRMED
  (`ast_gate/checks/api_auth_checks.py`). *Effort:* [decision] a route-operation sensitivity taxonomy
  that proves every sensitive endpoint is gated.
- [x] **CLOSED — #771, `20c80a8a`.** **T4.4 — API thinness boundary (§1b/§3b).** `api/v1/proposals_routes.py` constructs
  `Proposal`/`ProposalScope`, calls `compute_risk()`, instantiates `ProposalExecutor` — domain logic
  in routes; only an *advisory* rule catches it. *Verdict:* CONFIRMED. *Effort:* [decision first] is
  route-level domain construction acceptable orchestration or debt? Then move behind a service.
- [x] **CLOSED — #772, `84a8b491`.** **T4.5 — ADR-147 (a) `work/` target-class taxonomy.** `work/` is absent from
  `.intent/taxonomies/target_class_boundaries.yaml`; canary scratch falls through to `repo-source`
  (strictest), forcing the janitor's special-case deletion. *Verdict:* CONFIRMED open. *Effort:*
  [decision] follow-up ADR adding a `work/` ephemeral-scratch prefix.

## Tier 5 — test coverage / fault-injection (confirmed)
**Still open — tracked as #773.**

- [ ] **T5.1 — conftest fragility (§5c).** `tests/conftest.py` silently `pytest.skip()`s all DB tests
  when the LAN Postgres host is unreachable, and the cleanup fixture `except Exception: pass` on
  truncation. *Verdict:* CONFIRMED. *Effort:* visible suite modes (unit / hermetic-integration /
  external); a skipped DB suite should fail a release gate unless waived; log truncation failures.
- [ ] **T5.2 — Failure-semantics fault-injection gaps (§5a).** *Verdict:* PARTIAL — genuinely absent:
  (1) `core.action_results` write failure on a succeeded action, (2) consequence persistence failing
  after `mark_completed`, (3) git commit failing after clean sandbox propagation, (4) `_defer_to_
  proposal` undercount, (5) a proposal abandoned mid-`EXECUTING` (vs the generic claim reaper).
  *Note:* (2)(3)(5) were slated to land with #763's fault-injection tests — #763 is now closed; re-verify these three sub-items are actually covered before closing T5.2, don't assume.
- [ ] **T5.3 — Per-symbol finding linkage (§5e).** Only the *first* symbol proposal receives the
  deferred findings; sibling symbol proposals have no independent Finding→Proposal link, so §7a
  revival can't re-trigger them. *Verdict:* CONFIRMED (`test_remediator/worker.py`). *Effort:*
  per-proposal (fan-out) deferral.

## Tier 6 — watch / long-horizon (confirmed, not defects)

- [ ] **T6.1 — `modularity_fix.py` size (§7c).** 841 lines, multiple responsibilities. *Verdict:*
  CONFIRMED. *Note:* per the "responsibility not lines" rule, split only if genuinely two concerns;
  the T4.1 migration may shrink it first. Watch.
- **T6.2 — `CoreContext` breadth (§7d).** Cross-layer dependency bag (infra + optional cognitive +
  factories + mutable file-cache + post-construction wiring). *Verdict:* CONFIRMED accurate, but
  disciplined (TYPE_CHECKING, typed Optionals) — **"not a defect."** Watch, no action.

---

## Not ToDos — verified and cleared (so the picture is honest)

**Refuted / stale (the reviewer was wrong or out of date):**
- **"No `EXECUTING`-proposal reaper"** — REFUTED. `ProposalPipelineShopManager` /
  `fetch_stuck_executing` exists, named in governed law (`proposal.stuck_executing`, ADR-091 D2).
- **ADR-139 mypy "largest recent declared debt"** — STALE. Backlog fully cleared; `mypy src/` clean
  over 1039 files; `quality.type_safety` promoted to **blocking** (`5da14b3b`). Done.

**Healthy / correct-by-design (no action):**
- §4a sleep = `max(interval − elapsed, 0)` · §4b heartbeat-at-start + separate registry lease ·
  §4c silence-invariant mechanism · §4e `claim.proposal` atomic conditional-UPDATE + unique index ·
  §1d atomic-action decoration contract (ActionResult + `@atomic_action` + `**kwargs` + governed
  risk overlay + fail-closed executor init) · §2d no manual event loop in Mind · §6a
  `require_governor` no-op (OSS trust boundary) + AST checker inspects all `APIRouter` assigns · §6b
  subprocess sanctuary (no shell, timeouts, structured failures) · §6c no JWT/role creep.

**Implemented ADRs (§3a):** 140, 141, 142 (scoped to symbol-existence, behavioral verify deferred),
143, 144, 146. ADR-145 genuinely deferred (activation criterion unmet). ADR-138 implemented with one
residual → folded into T-none (a passive-gate rule `ai.prompt.constitutional_grounding_section` has
no mechanical detector; review-time invariant only — low value, noted not tracked).

**Closed this session:** ADR-148 accepted + finalizing law layer (vocabulary, `proposal_status`
enums, Python enum, `CORE-Proposal.md`) committed `4200ba48`.

**Verification flags closed:** symbol-ID audit ran repository-wide → **0 violations (PASS)**
(`core-admin code audit -r purity.stable_id_anchor`).

**Closed since 2026-07-12 (Tier 1–4, verified against `gh issue view` 2026-07-14):** #763 (T1.1),
#764 (T1.2), #765 (T1.3), #766 (T2.1), #767 (T2.3), #768 (T2.4), #769 (T4.1), #770 (T4.3), #771
(T4.4), #772 (T4.5), #775 (T3.1). (#723 shipped the T4.2 *rule* but not the excludes removal — T4.2 remains partially open, see Tier 4.) T2.2 and T3.2 landed as direct commits without a
tracking issue. See each Tier item above for its closing commit.

---

## Second external review (2026-07-14, snapshot `d481c7dd`)

A second external architecture review ran against HEAD `d481c7dd` with the deep-dive focus on
**constitutional enforcement closure across the autonomous mutation pipeline**. It independently
re-derived essentially this doc's entire open surface from an outside read — a strong honesty
signal. Confirmed-and-tracked: #792 (its #1 pick), #790, #773, #774, #787. Corrected one
mis-mark: T4.2 (above). Newly filed: **#793** (worker-exclusion extraction, the real T4.2 work).

**Emergent patterns the reviewer named as worth formalizing** (recorded here before deciding
whether each earns an ADR — governor call):

1. **Measurement-gated activation.** Accept a decision and define its activation trigger, then
   gather live evidence and either activate or leave deferred. Exemplar: ADR-140's 2026-07-14
   amendment recording pytest-in-the-loop fired NO on measured evidence (the predicted failure
   class had fallen to zero). Candidate for a short paper or an ADR template so the lifecycle is
   reusable rather than re-invented per decision.
2. **Evidence-grade recovery.** A reconciler may restore lifecycle state with *complete*,
   *partial*, or *reconstructed* evidence; the grade must be explicit, not silently equivalent to
   directly-captured evidence. This is #790 (reaper reconstructs consequences with null
   `pre_sha`/`post_sha`/`changed_files`) generalized. ADR-113's `EvidenceClass` vocabulary is the
   likely home.
3. **Exemption debt.** Every whole-file / module-level constitutional exclusion should carry an
   owner, a reason, a closure condition, and preferably a machine-checkable expiry — so an
   exclusion cannot quietly outlive its justification (the #793 / T4.2 failure mode as a class).
   **Conceptual correction (2026-07-14):** this is **already decided** — **ADR-049 D3** ("Each
   excludes entry must reference a closure ADR and carry a deadline") states exactly this, generally,
   with a two-stage warn→block enforcement design. The gap is that D3's enforcement was **never
   built** (no engine in `src/` parses exclusion deadlines/closure refs), so the worker excludes
   carry none of its required fields. A first-drafted new ADR-149 restating D3 was withdrawn as a
   reflex-ADR (decision-vs-application). Correct artifacts: (a) **an issue to wire ADR-049 D3's
   enforcement** — the standing check that was decided and never shipped; (b) an open intent call
   for the governor: was D3 meant to bind *all* rules or only `architecture.shared.no_layer_imports`
   (its statement reads general; its motivation was shared-only)? A separate, genuinely-undecided
   concern is **silent scope loss** — narrowing whole-file excludes to pattern-level so an excluded
   file can't acquire a *new* real violation invisibly; that is not what D3 addresses and may warrant
   its own decision, scoped deliberately rather than reflex-filed.

**Reviewer's "one thing to carry forward":** CORE's strongest emerging property is that it is
beginning to distinguish "the operation happened" from "the operation can be defended" — do not
weaken that distinction in recovery code (pattern 2 above).

---

## Cross-references
- **#763** — ADR-148 finalization machinery (D1–D5 + fault-injection tests). CLOSED. Absorbed
  T5.2(2)(3)(5) — re-verify those sub-items are covered before closing T5.2.
- **#723** — created the worker-import AST rule (CLOSED, `7dc46e57`). NOTE: the T4.2 helper-extraction + excludes-removal it was meant to enable is **not done** — 6 whole-file excludes remain; now tracked as **#793**.
- **#793** — worker-exclusion extraction (the real T4.2 work): extract co-located helpers out of `will/workers/`, remove the 6 whole-file excludes. OPEN.
- **#792** — `build.test_for_symbol` mid-file `from __future__` on append → collection SyntaxError. Fixed 2026-07-14 (`strip_leading_future_imports` in `shared/utils/test_gen_utils.py` + regression tests); issue closure pending governor commit.
