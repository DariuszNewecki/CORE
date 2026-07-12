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
(class-fix → #775) · T3.2 comment `50e01bc3`. **Open, tracked as issues:** #764 (T1.2 outbox) · #765
(T1.3 instrument taxonomy) · #766 (T2.1 TestRunnerSensor) · #769 (T4.1 fix.modularity/ADR-140) · #770
(T4.3 route-op gate) · #771 (T4.4 API thinness) · #772 (T4.5 work/ taxonomy) · #773 (T5 test
hardening) · #723 (T4.2 worker helpers) · #774 (ADR-040 literal sweep) · #775 (digest drift-gate).

---

## Tier 1 — "make success provable" (evidence completeness / honesty · NorthStar-anchored)

The review's spine: CORE has strong front-of-chain controls but reports some successes it cannot
fully back with durable evidence. Three instances of one class.

- [~] **T1.1 — Proposal finalization barrier.** `COMPLETED` becomes a proof state.
  *Verdict:* CONFIRMED (crux). *Status:* **ADR-148 accepted; law layer committed (`4200ba48`);
  machinery tracked in #763.** Not re-listed here — see #763.
- [ ] **T1.2 — Creation-side dual-write / finding→proposal outbox (§4d).** A proposal is reported
  *created* while its findings may not be durably linked. *Verdict:* CONFIRMED —
  `defer_to_proposal` (`will/workers/violation_remediator_blackboard.py`) wraps
  `blackboard_proposal_service.defer_entries_to_proposal` fail-soft (docstring: "a revival-layer
  failure here does not reverse the caller's proposal_created accounting"). Breaks the §7a revival
  contract (orphaned findings / duplicate proposals). *Effort:* [family] transactional — bind
  proposal creation + finding deferral (outbox). ADR-148 named this out-of-scope-next.
- [ ] **T1.3 — Instrument availability: "no findings" ≠ "couldn't look" (§4c/§5e).** *Verdict:*
  CONFIRMED across sampled workers — `post_heartbeat()` is posted *before* the input query and
  satisfies the silence invariant, so an input that returns **empty without raising** reads as
  genuinely clean (only inputs that *raise* are caught, via the Model-B cycle-error report).
  Sensors affected: `TestCoverageSensor`, `ProposalConsumerWorker`, `TestRunnerSensor`;
  `TestRemediatorWorker` additionally posts no all-clear report. *Effort:* [decision] instrument-
  result taxonomy (clean / found / unavailable / indeterminate — CORE already has the
  `Indeterminate` vocabulary term); subsumes T2.1.

## Tier 2 — bounded code fixes (confirmed concrete bugs)

- [ ] **T2.1 — `TestRunnerSensor` silent infra-drop (§5e).** On a pytest-infra exception, `run()`
  logs, `resolve_entries([entry_id])`, and `continue`s with no replacement finding — the test-gen
  chain loses its trigger. *Verdict:* CONFIRMED (`will/workers/test_runner_sensor.py::run`).
  *Effort:* [bounded] the evidence-preserving pattern already exists in the same file
  (`_adjudicate_test_quarantine` keeps subjects retryable) — apply it to `run()`.
- [ ] **T2.2 — ADR-147 (b) second symlink-dereference site.** *Verdict:* CONFIRMED — the fix landed
  at `crate_processing_service._run_canary_validation` (`symlinks=True`) but
  `FileHandler.copy_repo_snapshot` (`body/infrastructure/storage/file_handler.py`) still calls
  `shutil.copytree(...)` without `symlinks=True` — the same dereference defect, live. *Effort:*
  [bounded] one-line fix + regression test.
- [ ] **T2.3 — `modularity_fix` raw `.intent` read.** `_load_split_confidence_threshold`
  (`body/atomic/modularity_fix.py`) reads governance YAML via `PathResolver` + `yaml.safe_load`
  with a bare-except silent fallback, bypassing `IntentRepository`. *Verdict:* CONFIRMED. *Effort:*
  [bounded] route through the intent repository / a typed config projection.
- [ ] **T2.4 — Retire dormant `MicroProposalExecutor`.** Ungoverned parallel-mutation path (raw
  `.intent` read, placeholder validation-report accept, own `FileHandler`, no ActionExecutor/
  sandbox/persistence). *Verdict:* CONFIRMED dead code — **zero prod + zero test call sites.**
  *Effort:* [cheap] delete `body/autonomy/micro_proposal_executor.py` + doc refs.

## Tier 3 — cheap doc / config cleanups (confirmed)

- [ ] **T3.1 — Rule digest drift in `CLAUDE.md`.** Digest says 35+27+9=71; source is
  **37+28+8=73**. *Verdict:* CONFIRMED (`jq` over `.intent/rules/architecture/*.json`). *Effort:*
  [cheap] correct the digest.
- [ ] **T3.2 — Stale layer-mapping comment.** `layer_separation.yaml` RULE 6 marks consequence-log
  extraction `(pending)`, but `ConsequenceLogService` exists in Body and `ProposalExecutor` already
  delegates to it. *Verdict:* CONFIRMED. *Effort:* [cheap] drop the stale annotation.

## Tier 4 — governance / architecture (confirmed; decision or bounded work)

- [ ] **T4.1 — `fix.modularity` violates ADR-140 (§2f).** Not merely a stale rationale: the
  `modularity_analyze` prompt rationale still says "Body-layer LLM call," and
  `body/atomic/modularity_fix.py` **still does it** — `PromptModel.load("modularity_analyze")` +
  `cognitive_service.aget_client_for_role(...)` inline in the Body action, which ADR-140 D1 forbids.
  *Verdict:* CONFIRMED — ADR-140 was not applied to this action. *Effort:* [decision+refactor]
  migrate to the cognitive/write split (Will-injected `StepKind.COGNITIVE` → Body terminal writer),
  then fix the rationale. (May naturally shrink T6.1.)
- [ ] **T4.2 — Worker-helper whole-file exclusions (§1a/§2a).** RULE 16
  `architecture.workers.no_direct_worker_import` carries **6 whole-file `excludes:`** under
  `will/workers/` (proposal_consumer_worker, proposal_pipeline_shop_manager, violation_remediator,
  violation_remediator_proposal, audit_violation_sensor, violation_executor). An excluded file could
  acquire a real worker→worker import without the rule firing. *Verdict:* CONFIRMED (tracked as
  #723). *Effort:* [refactor] extract helpers out of `will/workers/`, then remove the excludes.
- [ ] **T4.3 — Route-operation sensitivity classification (§6d).** In a `user-facing` router, the
  AST checker permits per-route `require_governor` gates but never verifies them, so a newly added
  sensitive route could ship un-gated and pass the rule. *Verdict:* CONFIRMED
  (`ast_gate/checks/api_auth_checks.py`). *Effort:* [decision] a route-operation sensitivity taxonomy
  that proves every sensitive endpoint is gated.
- [ ] **T4.4 — API thinness boundary (§1b/§3b).** `api/v1/proposals_routes.py` constructs
  `Proposal`/`ProposalScope`, calls `compute_risk()`, instantiates `ProposalExecutor` — domain logic
  in routes; only an *advisory* rule catches it. *Verdict:* CONFIRMED. *Effort:* [decision first] is
  route-level domain construction acceptable orchestration or debt? Then move behind a service.
- [ ] **T4.5 — ADR-147 (a) `work/` target-class taxonomy.** `work/` is absent from
  `.intent/taxonomies/target_class_boundaries.yaml`; canary scratch falls through to `repo-source`
  (strictest), forcing the janitor's special-case deletion. *Verdict:* CONFIRMED open. *Effort:*
  [decision] follow-up ADR adding a `work/` ephemeral-scratch prefix.

## Tier 5 — test coverage / fault-injection (confirmed)

- [ ] **T5.1 — conftest fragility (§5c).** `tests/conftest.py` silently `pytest.skip()`s all DB tests
  when the LAN Postgres host is unreachable, and the cleanup fixture `except Exception: pass` on
  truncation. *Verdict:* CONFIRMED. *Effort:* visible suite modes (unit / hermetic-integration /
  external); a skipped DB suite should fail a release gate unless waived; log truncation failures.
- [ ] **T5.2 — Failure-semantics fault-injection gaps (§5a).** *Verdict:* PARTIAL — genuinely absent:
  (1) `core.action_results` write failure on a succeeded action, (2) consequence persistence failing
  after `mark_completed`, (3) git commit failing after clean sandbox propagation, (4) `_defer_to_
  proposal` undercount, (5) a proposal abandoned mid-`EXECUTING` (vs the generic claim reaper).
  *Note:* (2)(3)(5) land naturally with #763's fault-injection tests.
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

---

## Cross-references
- **#763** — ADR-148 finalization machinery (D1–D5 + fault-injection tests). Absorbs T5.2(2)(3)(5).
- **#723** — worker-helper extraction (T4.2).
