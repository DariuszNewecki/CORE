# Session Handoff — 2026-04-22 (evening)

**A3 phase:** 3 (Capability gaps). Session work was primarily hygiene
and observability — completing yesterday's Option B (`details: {}`
serializer restoration), yesterday's Option A (`resolved_at` symmetric
hygiene), and Option C Decision 1 (reclassify `fix.placeholders` to
`safe`). Decision 1 validation surfaced two new issues (IntentGuard
CLI-depth misfire, cold-registry behavior) which did not exist
yesterday and would not have been visible without the autonomous loop
actually executing.

**Last session:** 2026-04-21 evening — VR routing + `resolve_entries`
predicate broadening + `claimed_at` capstone.

**Audit state at close:** PASS, 32 findings, 120/121 rules executed,
0 crashed. Count held steady across three separate full audits during
the session (pre-Option-B, post-Option-B, post-Option-A+, post-Decision-1
— all at 32).

**Daemon state:** active, PID 622877, restarted at 19:22:40 UTC during
Decision 1 recovery (see below). Running code includes all three
session commits and the reclassification.

**Blackboard state:** `fix.placeholders` is churning — every ~10 min
the purity sensor re-detects the TODO in `violation_remediator.py`, VR
creates a fresh safe proposal, auto-approves, ProposalConsumerWorker
executes, action fails at IntentGuard (CLI command depth rule
misfire). Each cycle is ~187 ms of execution + auto-approval
overhead. Cosmetic history accumulation (~144 failed proposals/day at
current cadence); not a governance violation, not harmful, but it IS
signal that the IntentGuard rule needs attention.

---

## What this session did

### Four commits + one ADR

| Commit / Doc | What | Verified by |
|---|---|---|
| `e77a59aa` | Engine-contract widening. `EngineResult.violations: list[str]` → `list[str \| dict[str, Any]]`. New `normalize_violation()` helper. Modularity dispatcher stops flattening. `rule_executor` populates `AuditFinding.context`. Two `ViolationReport`-building consumers updated to avoid TypeErrors on dict-shaped violations. Five files. | modularity findings in `reports/audit_findings.json`: 0 → 24 with populated `details` including `dominant_class_*` trio |
| `785267a3` | `resolved_at` hygiene across **all seven** terminal-state write paths (not the four the handoff initially scoped). Four `BlackboardService` methods, `_post_entry` INSERT (born-terminal heartbeats + reports), two worker-side bypass paths (`prompt_artifact_writer`, `call_site_rewriter`) that were also missing `updated_at`. | Post-restart DB query: all 48 terminal-state writes across heartbeat/report/finding types carry populated `resolved_at`, zero NULLs |
| `56f47406` | Reclassify `fix.placeholders` from `moderate` to `safe`. One-line decorator change. | Live traversal (see Decision 1 below) |
| ADR-008 | "Constitutionalize action `impact_level`." Records the deliberate parking of the structural externalization — `impact_level` currently lives in `@register_action(...)` Python decorators (~40 sites), which is a governance-in-`src/` violation. Target state: `.intent/enforcement/config/action_risk.yaml` with a loader. Reason for parking: schema should coordinate with the second-axis risk-model question from 2026-04-21's open questions before externalization. | Written; recorded as ADR in the existing `.specs/decisions/` register |

### Option B — engine-contract widening (commit `e77a59aa`)

The 2026-04-21 morning handoff framed this as "`details: {}` stripping
in audit JSON serializer." That framing was load-bearingly wrong. The
`AuditFinding.as_dict()` method is correct; it aliases `details` to
`context`. But `context` was always empty because the structural signal
was dropped three layers upstream at the engine contract itself:

1. `EngineResult.violations: list[str]` — the type forbid structure.
2. `ASTGateEngine`'s modularity dispatch: `[f["message"] for f in findings]` —
   explicit flattening of the sensor's `{message, details}` dicts.
3. `rule_executor.execute_rule` built `AuditFinding(...)` with no
   `context`, so there was nothing for `as_dict()` to serialize.

Fix widens the contract (`list[str | dict[str, Any]]`), adds
`normalize_violation()` to `base.py` as the canonical consumer helper,
stops the flattening, populates `AuditFinding.context`, and updates
all three `result.violations` consumers to use the helper. Of the
three consumers, only `rule_executor` propagates details — the two
`ViolationReport`-building paths (`code_validator`, `engine_dispatcher`)
discard details intentionally because `ViolationReport` doesn't carry
them today. Normalization at those sites is purely to prevent
TypeErrors when they see a dict-shaped violation from modularity.

Zero migration required for string-emitting engines; they continue
unchanged. Future detail-rich engines can upgrade to dict-shape
emission without touching consumers.

### Option A+ — `resolved_at` symmetric hygiene (commit `785267a3`)

Handoff named 3 `BlackboardService` methods. Code inspection surfaced
a fourth (`resolve_dry_run_entries_for_namespace` — same shape bug).
Verification then surfaced three more write paths outside
`BlackboardService` entirely: `_post_entry` for born-terminal
heartbeats/reports, and two worker-side direct-SQL bypasses
(`prompt_artifact_writer._mark_finding`,
`call_site_rewriter._mark_findings`) which were also omitting
`updated_at`.

Commit expanded accordingly. Seven paths, one commit, one unified
theme. Worker-side paths use `CASE WHEN :status IN ('resolved',
'abandoned', 'indeterminate') THEN now() ELSE resolved_at END` so
non-terminal statuses (if any caller ever passes one) preserve
existing values. `_post_entry` uses the same CASE form in its INSERT
column list.

Post-restart DB evidence:

| entry_type | status | post_restart_total | with_resolved_at | nulls |
|---|---|---|---|---|
| finding | resolved | 8 | 8 | 0 |
| heartbeat | resolved | 22 | 22 | 0 |
| report | resolved | 18 | 18 | 0 |

`abandoned` and `indeterminate` didn't fire in the 5-minute
verification window, so the CASE-guarded paths for those specific
statuses are inferred-correct via path equivalence with the observed
`'resolved'` case, not directly observed. Evidence is strong but not
ironclad — worth re-checking next time either status surfaces in
normal operation.

Historical rows pre-fix retain `resolved_at = NULL`. Not backfilled
(flagged in 2026-04-21 hazards as "three days of blackboard history
are partly false"). From these commits forward, every terminal-state
row — transitioned or born — carries its terminal timestamp.

Parked as known architectural debt: the two worker paths in this
commit write SQL directly instead of routing through
`BlackboardService`. Symptom patched, pattern unchanged. Routing
them through the service is a separate refactor.

### Option C Decision 1 — `fix.placeholders` reclassification (commit `56f47406`)

Mechanical single-line change in `src/body/atomic/fix_actions.py`:
`impact_level="moderate"` → `impact_level="safe"`. Rationale: the
action is a 5-pattern regex replacement helper with no LLM and no
judgment — same risk shape as `fix.format` (already safe and
auto-executing). Under moderate classification, the action
accumulated DRAFT proposals on every sensor cycle that sat in the
queue waiting for manual approval that was never going to come. Under
safe, it auto-approves like `fix.format` does.

ADR-008 records the decision AND parks the structural question of
why `impact_level` is in Python code rather than `.intent/` in the
first place.

**Live validation traversal (two attempts, second clean):**

*First attempt* (19:18:20 UTC) — rejected the pre-existing DRAFT
`2dadb8b2`, waited for sensor regeneration. New proposal `f55423b6`
generated carrying `overall_risk = moderate` despite the committed
reclassification. Stop-and-report triggered.

Root cause: cold registry. Daemon had restarted at 18:47:14 UTC for
Option A verification; commit `56f47406` landed after, so the running
daemon's in-memory action registry still reflected the old
classification. Plumbing correct; daemon stale.

*Second attempt* (19:22:40 UTC restart) — rejected `f55423b6`,
restarted daemon to pick up the fresh code, polled for regeneration.
Proposal `ed4ea9fb` generated within 2 minutes with `overall_risk =
safe`, auto-approved without manual intervention, dispatched to
ProposalConsumerWorker ~60 s later. Four-stage plumbing validated:

1. `@register_action(impact_level="safe")` → `risk.overall_risk = 'safe'` on proposal ✅
2. Safe proposals auto-approve without DRAFT queue ✅
3. ProposalConsumerWorker dispatches approved proposals ✅
4. Finding resolution path continues to populate `resolved_at` (commit `785267a3` cross-validated) ✅

The action itself then failed at IntentGuard — see hazards below.
That failure is orthogonal to the reclassification.

### IntentGuard misfire — surfaced, not introduced

The `ed4ea9fb` proposal executed for 187 ms and was blocked with:

> "Blocked by IntentGuard: CLI commands MUST follow 'resource action
> [flags]' pattern (depth=2), except admin namespace which may use
> depth=3."

Target file: `src/will/workers/violation_remediator.py` — a worker,
not a CLI file. The CLI-depth rule is apparently evaluating all Python
files against a CLI-shaped policy rather than limiting itself to
declared CLI command modules. Probable fix: narrow the rule's scope
in the YAML mapping (likely in `.intent/enforcement/mappings/` —
didn't trace).

**Critically:** this bug has existed since whenever the CLI-depth
rule was authored. It never fired before today because
`fix.placeholders` (the only path that routinely rewrites TODO
comments on worker files) was under moderate classification and
never executed autonomously. Reclassification didn't cause the bug
— it made a previously-invisible bug visible. Same pattern yesterday
flagged in hazards #2: "any worker with a symmetric silent bug we
haven't found yet may now surface as a new class of failure that
didn't exist when the loop was stuck."

---

## What this session did NOT do

- **Trace the IntentGuard CLI-depth rule misfire.** Surfaced at
  Decision 1 validation; needs YAML scope narrowing in
  `.intent/enforcement/mappings/`. Separate session.
- **Verify the finding-revival contract on proposal failure.**
  The Remediation paper specifies that a failed proposal should
  "revive" its linked findings by resetting them to `open`.
  Evidence from Decision 1: each 10-minute churn cycle posts a
  *new* finding for the same TODO rather than reopening the prior
  one (two `resolved` rows at different timestamps for the same
  subject). Strongly suggests the revival contract is not wired.
  Separate session.
- **Address cold-registry behavior.** Today the daemon silently
  ran stale code for 35 minutes between commit `56f47406` and the
  19:22:40 restart. No dashboard signal, no warning, detectable
  only by observing incorrect proposal output. Three approaches
  (document, detect, fix); all parked.
- **Decision 2 on `fix.modularity` DRAFT `44441112`.** 11 SplitPlans
  batched into a single proposal, created 2026-04-21 10:29, still
  in draft. Decision deferred because validating safe-path
  auto-execution end-to-end (today's IntentGuard surfacing)
  changed the risk calculus — turning AI-in-loop moderate actions
  loose before the enforcement layer has been cleanly validated
  through at least one more safe-action cycle is wrong
  risk-ordering. Separate session.
- **Decision 2 on `fix.placeholders` DRAFT 2dadb8b2 → f55423b6.**
  Technically done (both rejected), but the churn pattern it
  replaced is its own post-Decision-1 artifact that persists.
- **ADR-007 Consequences addendum + 13-file `class_too_large`
  review ADR.** Still pending from 2026-04-21 morning.
- **The morning handoff's longer parked list** — ContextBuilder
  wiring, path-mapping, `action_executor` guards, daemon
  composition root, dead `auto_remediation.yaml` entries,
  `proposals show` logger bug, `logic.di.no_global_session`,
  `autonomy.tracing.mandatory`, `purity.no_ast_duplication`,
  `ai.cognitive_role.no_hardcoded_string` campaign,
  `architecture.api.no_body_bypass` — all still parked.

---

## Carry-over — next session

Four candidates, ordered by leverage, with the IntentGuard trace
sitting at the top because it's the acute pressure point holding
everything else downstream.

### Option A — IntentGuard CLI-depth rule scope narrowing

Surfaced during Decision 1 validation. Every ~10 minutes a fix.placeholders
proposal fails at this rule on `violation_remediator.py` — a worker
file being blocked by a CLI-shape rule. The rule almost certainly
lives in `.intent/enforcement/mappings/` and wants a scope narrowing
to CLI command modules only. Once narrowed:

- The proposal churn stops (fix.placeholders succeeds, finding is
  actually resolved on disk, no fresh detection).
- Other silent-until-now cases of this rule over-firing may also
  surface — worth auditing what else the rule has been blocking
  since it was written.

Session-sized. Probably the right next move because it closes the
churn and gives you the first clean end-to-end safe-action cycle
post-reclassification.

### Option B — Revival contract verification

The Remediation paper (`.specs/papers/CORE-Remediation.md`) specifies
that failed proposals revive their linked findings. Evidence from
today suggests this isn't wired: after `ed4ea9fb` failed, the finding
didn't reopen — instead a fresh finding was posted on the next
sensor cycle. Mechanically functional (cycle is self-healing) but
contractually wrong (each failure creates a new finding instead of
recycling the one that caused it).

Investigation path: check `ProposalConsumerWorker._handle_failure`
(or equivalent), verify whether it calls `BlackboardService.update_entry_status`
or similar to set the linked finding to `open`. If yes, trace why
it isn't firing. If no, wire it. Smaller than A if it's a missing
call; larger if it's a design question.

### Option C — Cold-registry detection or fix

Three sub-options by cost:

1. **Document.** ADR or workflow note: "after any `@register_action`
   change, restart the daemon." Cheap, relies on discipline.
2. **Detect.** Dashboard widget: daemon generation timestamp vs
   max mtime on `src/body/atomic/*.py`. Passive signal.
3. **Fix.** Daemon hot-reloads action registry on file mtime change
   or checks per sensor cycle. Real work.

Today's incident is only recoverable because the validation query
caught the stale classification. Under silent-correct-looking
behavior, nobody would have noticed. ADR-sized minimum; fuller fix
is session-scale.

### Option D — `fix.modularity` DRAFT `44441112` review

11 SplitPlans batched into one proposal. Each is a per-file
architectural decision. Read-only inspection first to size the review;
then either approve/reject individual modules (if the proposal supports
that granularity) or approve/reject the whole proposal.

Probably wants a fresh session, not an end-of-session choice.

### Recommendation

**A, then B.** A stops the acute symptom and exercises the
enforcement-scope narrowing path, which is a useful capability in
its own right. B is shaped similarly to today's `resolve_entries`
fix (contractual wiring verification); cleans up a second layer of
the "autonomous loop is honest about its state" story. C and D can
wait.

---

## Open questions for next session

1. **IntentGuard CLI-depth rule scope.** Is the rule mis-scoped, or
   is there a hidden correct reason it's blocking worker files?
   The error message strongly implies mis-scoping; need the YAML
   to confirm.
2. **Revival contract wiring.** Does the PC/VR layer actually
   revive findings on proposal failure? Evidence suggests no.
   If no, is that a bug or a deliberate deviation from the paper?
3. **Verdict-threshold semantics.** PASS with N WARNINGs, still no
   written definition. Surviving from 2026-04-21 open questions.
4. **Historical resolved count composition.** What fraction was
   real transitions vs inserted-at-resolved? Still unknowable.
   Surviving from 2026-04-21.
5. **Moderate-risk second-axis.** Decision 3 in today's Option C
   framing. Surviving from 2026-04-21 and now explicitly connected
   to ADR-008's parking rationale.
6. **"Changes recorded: 0 files" coherence.** Surviving from
   2026-04-21 — still relevant; today's `ed4ea9fb` had a different
   "no changes" shape (IntentGuard blocked before write) which
   reinforces the need for the distinguishing field.

---

## Hazards worth naming

1. **`fix.placeholders` churn loop.** ~144 failed proposals/day at
   current cadence. Cheap (187 ms per cycle), cosmetic (history
   accumulation), but genuine signal that the IntentGuard rule
   needs attention. **Deliberately not silenced** — undoing
   Decision 1 (reclassify back to moderate) would mask the real
   bug. The failing proposals ARE the alarm. Option A next session
   stops the churn by fixing the underlying cause.

2. **IntentGuard rule coverage is wider than its name.** The
   CLI-depth rule fired on a non-CLI file. Raises the prior on
   other rules in `.intent/enforcement/mappings/` having similar
   over-firing scope. Worth a systematic audit at some point —
   "every rule whose scope is wider than its name suggests is a
   landmine waiting for the autonomous loop to step on."

3. **Cold-registry silent behavior.** The daemon ran stale
   classification code for 35 minutes between commit and restart
   today. No signal, no warning, detectable only by observing
   incorrect proposal output. Any `@register_action` change is
   silently non-effective until the next daemon restart. Governance
   drift without audit trail.

4. **Revival contract evidence suggests non-wired.** Today's churn
   cycle posts a *new* finding for the same subject on each
   iteration rather than reviving the prior one. Each iteration
   increments blackboard row count. Compounds hazard #1 — the
   history accumulation isn't just failed proposals, it's also
   growing finding count for the same underlying violation.

5. **Two mypy narrowing debt regions surfaced this session.**
   Option B exposed `EngineRegistry.get(str | None)` narrowing
   gaps at `engine_dispatcher.py:81` and `code_validator.py:82`.
   Decision 1 exposed 7 similar errors in `fix_actions.py`
   (lines 218/264/273/313/315/345/360). Pattern: files doing
   action registration and engine dispatch accumulate type
   debt. Not today's work, but worth sweeping when those files
   are touched anyway.

---

## North-star ordering reminder

`rules clear → enforcement real → code`. This session stayed in the
enforcement-real layer:

- **Rules clear:** unchanged. ADRs 001–008 hold.
- **Enforcement real:** improved on three axes — the engine now
  preserves structural signal end-to-end (Option B); every
  terminal-state blackboard write carries its timestamp (Option A+);
  action classification actually routes proposals through the
  correct approval path end-to-end (Decision 1, validated).
  **Also degraded on two axes:** IntentGuard rule misfire surfaced,
  revival contract evidence suggests non-wired. Net: more honest
  about actual state. "Enforcement real" means observable, not
  clean.
- **Code:** no application-logic progress this session. All work
  was infrastructure/hygiene. This is correct prioritization —
  pushing further into autonomous actions before the enforcement
  layer is cleanly validated would be inverted risk ordering, as
  today's IntentGuard surfacing demonstrated.

Yesterday ended with "the machinery producing the verdict is
trustworthy, and the autonomous loop actually closes." Today adds:
the machinery producing the proposals is also trustworthy — and
the autonomous loop is honest enough to surface its own
enforcement-layer bugs when asked to actually work.

---

**Current blockers:** None for progress. `fix.placeholders` churn is
running indefinitely until Option A lands next session (acceptable).
**Daemon state:** active, PID 622877, three post-fix commits loaded,
reclassification active.
**Audit state:** PASS, 32 findings, held across four separate runs.
**Blackboard state:** churning at ~10-min cadence on fix.placeholders
→ IntentGuard block → fresh finding. Contained.
**Active workers:** 15 registered active (unchanged).
**Next step:** Option A — IntentGuard CLI-depth rule scope narrowing.
