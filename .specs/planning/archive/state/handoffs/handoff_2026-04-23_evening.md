# Session Handoff — 2026-04-23 (evening)

**A3 phase:** 3 (Capability gaps). Session work was governance hygiene —
closing yesterday's carry-over Option A (IntentGuard CLI-depth misfire)
by finding its actual cause in the action layer, then following the
thread all the way down. Started with one targeted bug fix, ended with
four commits spanning bounded scope, structured error persistence, a
silently-bypassed hard invariant, and a central helper promotion.

**Last session:** 2026-04-22 evening — engine-contract widening +
`resolved_at` symmetric hygiene + `fix.placeholders` reclassification
to safe (which surfaced today's IntentGuard false-block and
cold-registry bite).

**Audit state at close:** PASS, 31 findings, 120/121 rules executed,
0 crashed. Held across all four commits today: 32 → 31 → 31 → 31 → 31.
(Initial drop 32 → 31 was `purity.no_todo_placeholders` resolving when
the first commit ran successfully end-to-end.)

**Daemon state:** active, PID from the 21:05:54 CEST restart. Running
code includes all four session commits.

**Blackboard state:** `fix.placeholders` churn ended at 16:55 UTC when
proposal `63d47846…` executed cleanly (target: `violation_remediator.py`,
status: completed, no failure_reason). Yesterday's hazard #1 closed.

---

## What this session did

### Four commits

| Commit | What | Verified by |
|---|---|---|
| `c8b51ca5` | Bound `fix.placeholders` to proposal target. Added `file_path` kwarg routing (targeted mode) with sweep-mode fallback for CLI backward compat. Action was an unbounded whole-`src/` sweep that ignored the proposal target — alphabetical iteration hit `src/cli/resources/` before the actual target and tripped `cli.resource_first`, failing before ever reaching the worker file. (Note: the architect-authored rewrite was subsumed by an autonomous `fix.format` commit — see Option E / hazard #3.) | Proposal `63d47846` completed post-restart; finding resolved under autonomous commit `15c8ae3e`; audit 32 → 31. |
| `cf2ea63c` | Preserve IntentGuard violation structure into `execution_results`. `ConstitutionalViolationError` enriched: inherits from `ValueError` (was bare `Exception`, unused), carries `list[ViolationReport]`, `str()` preserves the legacy `"Blocked by IntentGuard: {msg}"` one-liner verbatim, adds `to_dict()` for JSON-safe persistence. FileHandler's `_guard_paths` raises the enriched exception. `fix.placeholders` first adopter via local `_error_data` helper. | Runtime probe: `isinstance(exc, ValueError)` True, `str(exc)` byte-identical to legacy, `to_dict()` carries `rule_name` / `path` / `source_policy` / full violations list. |
| `c770e4e8` | Prefix-strip paths in FileHandler — `lstrip("./")` → `removeprefix("./")` at 11 sites plus ordering swap in compound forms. `lstrip` takes a character set, silently coercing `.intent/foo` → `intent/foo` (defeating IntentGuard's tier-1 hard invariant — writes redirected silently to `/opt/dev/CORE/intent/`) and `../evil` → `evil` (defeating `_resolve_repo_path`'s escape-boundary check — the coercion resolved traversal before the check ran). | Empirical bash test of `.lstrip("./")` on five adversarial inputs; audit held at 31. |
| `7d6a421c` | Hoist error-data helper to `mind.governance.violation_report` as free function `extract_error_data`. Adopted at seven action-local handlers in `fix_actions.py` and — critically — at ProposalExecutor's unhandled-exception catcher. Delegating actions (`fix.headers`, `fix.ids`, `fix.duplicate_ids`) get structured persistence for free via the central catcher without per-action changes. | Runtime probe: helper importable, flat path produces `{error: str(exc)}`, structured path produces `blocked_by` + carries extra kwargs. |

### Option A (from yesterday's handoff) — reframed and resolved

Yesterday's handoff recommended "IntentGuard CLI-depth rule scope
narrowing" as Option A. That framing was **load-bearingly wrong, same
class of wrongness as yesterday morning's `details: {}` framing**: the
scope is already narrow (`src/cli/resources/**/*.py` in the mapping).
The real bug was in the action, not the rule.

Trace across three probes ruled out:
1. Duplicate `cli.resource_first` PolicyRule with a broader pattern — loader only has one.
2. `Path.match` matching the worker file against the scope — empirically False on 3.12.
3. `PatternValidators` or a second emitter with the same statement text — none found.

The answer came from reading `action_fix_placeholders`'s body, not
more probes: the action rglob's all of `src/` and writes to every file
with a placeholder, so it was trying to write to `src/cli/resources/*`
files that legitimately matched `cli.resource_first`'s scope. The rule
was firing correctly in a narrow sense; the action was out of scope.

Lesson captured: trace closing requires reading code, not running more probes.

### End-to-end verification probe surfaced a second governance bug

Between commits 2 and 3, the verification probe for the structured-error
work was:
```python
fh._guard_paths([".intent/test_probe.yaml"])
```
Should have raised unconditionally (tier-1 hard invariant). Didn't.
`".intent/test_probe.yaml".lstrip("./") = "intent/test_probe.yaml"` —
character-set strip silently defeated the invariant. Two invariants
actually broken, not one: `.intent/` protection AND `is_relative_to`
escape boundary.

Commit 3 came directly out of commit 2's verification step. Taking the
probe seriously led to finding a constitutional integrity gap that had
been in the codebase since `lstrip("./")` was written.

### Central-catcher approach (commit 4) — leverage found late

Commit 2 put the unwrapping helper as a local private function
(`_error_data`) inside `fix_actions.py`. Correct first-adopter pattern,
wrong long-term home.

Rethinking for commit 4 surfaced: ProposalExecutor has its own
exception catcher for actions that don't own a try/except. Promoting
the helper to `mind.governance.violation_report` and adopting in
ProposalExecutor means every action — including the three delegating
actions that can't adopt locally — gets structured error persistence
without being touched.

This is the correct shape for the abstraction. Local-first adoption in
commit 2 was right for validation; promotion in commit 4 was right for
scale. No rework required — commit 2's local helper just disappeared
and its two call sites switched to the imported helper.

---

## What this session did NOT do

- **Bound the sibling sweep actions to their proposal targets.** `fix.logging`, `fix.headers`, `fix.ids`, `fix.duplicate_ids`, `fix.atomic_actions`, `fix.docstrings` all still whole-repo sweeps. Not churning today because their triggering findings aren't active, but any one activating recreates today's opening symptom in a new location. Per-action design question each — not mechanical like commit 4 was.
- **Fix `_AUDIT_ENGINES` skip-list in IntentGuard.** `runtime_check` rules (like `cli.resource_first`) are still evaluated as path-restrictions by `_check_against_rules`. Today this doesn't bite because `fix.placeholders` is now bounded and won't touch `src/cli/resources/` — but any sibling sweep action that touches a scoped path re-surfaces this.
- **Fix `Path.match` `**` semantics in IntentGuard.** `Path('src/X/Y/z.py').match('src/**/*.py')` returns False on 3.12. Same engine-asymmetry class as `AuditorContext.get_files` fix two sessions ago; latent under-enforcement across every IntentGuard rule scoped `src/X/**/*.py`.
- **Cold-registry detection or fix.** Hit at session start: daemon ran yesterday's code from 2026-04-22 21:22 until today's 18:54 CEST restart. File on disk was correct; running daemon wasn't. Symptom was post-restart proposal still failing because autonomous `fix.format` had committed the change under its own message and the daemon just hadn't been restarted. No dashboard signal, detectable only by observing stale proposal behavior.
- **Address autonomous-commit-message fidelity.** `c8b51ca5` has commit message "Autonomous remediation: fix.format" but the change was an architect-authored rewrite of `action_fix_placeholders`. Audit trail misattributes authorship. Same family as the two-log gap.
- **Decision 2 on `fix.modularity` DRAFT `44441112`.** Still parked from yesterday.
- **All earlier parked items** — ContextBuilder wiring, path-mapping, `action_executor` guards, daemon composition root, `autonomy.tracing.mandatory`, `purity.no_ast_duplication`, `ai.cognitive_role.no_hardcoded_string` campaign, `architecture.api.no_body_bypass` — all still parked.

---

## Carry-over — next session

Five candidates, ordered by leverage and risk.

### Option A — IntentGuard `_AUDIT_ENGINES` skip-list expansion

The frozenset of engines that `_check_against_rules` skips
(`ast_gate`, `glob_gate`, `knowledge_gate`, `llm_gate`, `regex_gate`)
was built for content-analysis engines only. Passive-marker engines
like `runtime_check` aren't in it, so their rules get evaluated as
path-restrictions — the rule's statement becomes a bogus violation
message on any write matching the rule's scope.

Path: (1) rename `_AUDIT_ENGINES` → `_NON_PATH_RESTRICTION_ENGINES`
(truth in naming), (2) add `runtime_check` to the set, (3) small ADR
recording the category split. Low risk, medium leverage, session-sized.

### Option B — Sibling sweep actions bounded to proposal target

Copy today's `fix.placeholders` pattern (accept `file_path` from kwargs,
sweep fallback with warning) to `fix.logging`, `fix.headers`, `fix.ids`,
`fix.duplicate_ids`, `fix.atomic_actions`, `fix.docstrings`. Per-action
design because each delegates to a different internal function with
unknown API — not purely mechanical. Some of these internals may need
to accept `file_path` too, which is multi-file per action.

Probably wants three sub-sessions, grouping by internal-function shape.

### Option C — `Path.match` `**` semantics in IntentGuard

Same engine-asymmetry class as the audit-engine fix two sessions ago.
Every rule scoped `src/X/**/*.py` can't match `src/X/foo.py` (too few
parts) or `src/X/a/b/foo.py` (too many on pre-3.13). Means silent
under-enforcement across every scoped IntentGuard rule.

Risk: fixing this will cause currently-silent rules to start firing.
Audit count may jump from 31 to some unknown N. Own session with own
ADR required. Do NOT start as an end-of-session cleanup.

### Option D — Cold-registry detection

Three sub-options by cost (same as yesterday's Option C):
1. Document — workflow note "after any `@register_action` or service-level change, restart the daemon." Cheap.
2. Detect — dashboard widget: daemon `ActiveEnterTimestamp` vs `max(mtime)` of `src/body/atomic/*.py` and related. Passive signal.
3. Fix — hot-reload.

Today's incident (daemon from 18h prior still running, despite commit
`56f47406` landing) is recoverable only because of the observable
behavior (still-failing proposals). Under silent-correct-looking
behavior nobody would have noticed.

### Option E — Autonomous commit-message fidelity

Today's `c8b51ca5` shows the pattern clearly: the daemon's autonomous
`fix.format` ran, detected that the working tree had uncommitted
changes (today's manual paste of the new `fix_actions.py`), ran its
formatter over them, and committed the combined result under the
message `Autonomous remediation: fix.format`. The actual substantive
change in the commit was the architect-authored action rewrite, not
format-fixup.

This is the same family as the two-log gap — "the record describes
something other than what happened." Design question, not a bug fix:
should `fix.format` refuse to run when the working tree has
non-format-scoped diffs? Should it split commits? Should it attribute
the pre-existing working-tree diff to the prior author?

### Recommendation

**A, then D (documentation sub-option only).** A closes the class of
false-block we saw this morning and is session-sized with clean ADR
shape. D-documentation is 5 minutes and codifies the lesson from
today's two cold-registry bites into something reviewers check. Both
are low-risk hygiene that extends today's arc.

B, C, and E are all bigger than they sound. Save them for their own
sessions.

---

## Open questions for next session

1. **`_AUDIT_ENGINES` category contract.** Current set describes what
   content-analysis engines look like. Should the reworded
   `_NON_PATH_RESTRICTION_ENGINES` be an exhaustive enumeration or a
   negative-list ("anything not explicitly a path-restriction")?
   Affects whether new engines default to blocking writes.
2. **Autonomous-loop working-tree hygiene.** Should autonomous
   actions refuse to run when the working tree is dirty? Ties
   Option E to Option D.
3. **Verdict-threshold semantics.** PASS with N WARNINGs, still no
   written definition. Surviving from 2026-04-21 and 2026-04-22.
4. **Historical resolved count composition.** Still unknowable.
   Surviving from 2026-04-21 and 2026-04-22.
5. **Moderate-risk second-axis.** Surviving from 2026-04-21 and
   ADR-008.
6. **"Changes recorded: 0 files" coherence.** Surviving.

---

## Hazards worth naming

1. **Cold-registry bit the session twice.** Session start: daemon
   ran yesterday's code against today's committed file until
   18:54 CEST restart. Mid-session: forgot the restart after
   `systemctl --user stop core-daemon` and worried about false
   behavior for ~10 min before realizing. Two pattern-matches in
   one day. Hazard #3 from yesterday's handoff is upgraded from
   "known" to "biting regularly."
2. **Scope-narrowing by framing alone is untrustworthy.** Yesterday's
   handoff said "narrow the CLI-depth rule YAML scope" — the scope
   was already narrow; the real bug was elsewhere. Similar to the
   morning-of-2026-04-22 `details: {}` framing. When a handoff names
   a specific fix shape, verify the shape matches reality before
   acting. Probes that find "X is not what you think" are more
   valuable than probes that confirm "X works."
3. **Autonomous commits can be misattributed.** Today's `c8b51ca5`
   is the canonical example — the commit message describes a change
   the commit didn't make, and the commit subsumed a change the
   message doesn't describe. Under autonomous operation this is a
   growing audit-trail hazard.
4. **"Adoption via central catcher" beats "adoption per-site" when
   the catcher exists.** Commit 2 went per-site for the first
   adopter (appropriate for validation). Commit 4 promoted via the
   central catcher. Next time this pattern appears: check for a
   central catcher first, adopt there, validate locally if doubt
   exists.

---

## North-star ordering reminder

`rules clear → enforcement real → code`. This session stayed in the
enforcement-real layer:

- **Rules clear:** unchanged. ADRs 001–008 hold.
- **Enforcement real:** improved on four axes.
  - Actions honor their declared `impact_level` scope (commit `c8b51ca5`).
  - Block failures preserve structure end-to-end from IntentGuard to execution_results (commits 2 and 4).
  - Two silently-bypassed constitutional invariants now actually fire (commit 3).
  - Central-catcher promotion means every action gets structured persistence without individual adoption (commit 4).

  **Also surfaced on two axes** (not fixed): `runtime_check` rules
  still evaluated as path-restrictions (Option A); `Path.match` `**`
  semantics still miscounting scoped-rule matches (Option C). Neither
  is biting *right now* — hazard #2 of yesterday's handoff predicted
  both would become visible under actual autonomous operation, and
  today they did.

- **Code:** no application-logic progress. All infrastructure. This
  is the second consecutive "correct prioritization" session — going
  deeper into autonomous actions before the enforcement layer is
  cleanly validated would be inverted risk ordering. Today's
  constitutional integrity gap (commit 3) that hid behind a utility
  function for however long `lstrip` has been there is the argument.

---

**Current blockers:** None. `fix.placeholders` churn ended, audit PASS held.
**Daemon state:** active, restarted 21:05:54 CEST, four commits loaded.
**Audit state:** PASS, 31 findings, held across four separate runs.
**Blackboard state:** clean. `63d47846` completed, no active churn.
**Active workers:** 15 registered active (unchanged).
**Next step:** Option A (`_AUDIT_ENGINES` skip-list expansion) + Option D (documentation sub-option).
