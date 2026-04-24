# ADR-009: CLI-depth block transient — passive instrumentation over active probe

**Status:** Accepted
**Date:** 2026-04-24
**Authors:** Darek (Dariusz Newecki)

## Context

On 2026-04-23, the `fix.placeholders` action failed repeatedly against `src/will/workers/violation_remediator.py` with the error:

> `Blocked by IntentGuard: CLI commands MUST follow 'resource action [flags]' pattern (depth=2), except admin namespace which may use depth=3.`

The error text is, verbatim, the `statement` field of the constitutional rule `cli.resource_first`, whose declared scope in `.intent/enforcement/mappings/cli/interface_design.yaml` is `src/cli/resources/**/*.py`. That scope does not — under Python 3.12's `PurePath.match` — match the target worker file.

**Failure window:** 2026-04-23 14:34:58 UTC – 16:46:05 UTC. Nine failures at ~10-minute cadence, all with identical inputs (same action, same file, same parameters). At 16:55:34 UTC the same action against the same file succeeded (proposal `63d47846…`, commit `15c8ae3e`) with no intervening change on the hot path. The failures stopped; the system self-recovered.

The 2026-04-22 session handoff framed this as an IntentGuard CLI-depth rule misfire and proposed "Option A: scope-narrow the rule in `.intent/`" as the next session's lead item. That framing assumed the YAML was wrong. This ADR records the investigation that ruled that out and the decision that follows.

### Investigation summary

Three diagnostic passes were run:

**Pass 1 — on-disk state (database + grep).** `cli.resource_first` is defined once in `.intent/rules/cli/interface_design.json` and mapped once in `.intent/enforcement/mappings/cli/interface_design.yaml`, with scope `src/cli/resources/**/*.py`. The error string appears nowhere under `src/`. All 9+ failing `action_results` rows predate commit `cf2ea63c` ("preserve IntentGuard violation structure into execution_results"), so they persist only the flat `error_message` string — no `rule_name`, no `source_policy`, no `path`. The actual `PolicyRule` that matched is not recoverable from the database.

**Pass 2 — out-of-process load.** A freshly-instantiated `IntentGuard` against `/opt/dev/CORE` reports `is_valid=True` for the target file under both `impact="write-code"` and `impact=None`. Every `cli.*` rule returns `Path.match=False` against the target. The on-disk rule set cannot produce the observed block.

**Pass 3 — live daemon memory dump.** A `gdb`-mediated in-process injection against the running daemon (PID 813659, uptime 12h 31m at capture, started 2026-04-23 19:05 UTC — **after** the self-recovery at 16:55 UTC) showed: one `IntentGuard` singleton, 140 rules loaded, all `cli.*` rules with their YAML-declared scopes intact, `check_transaction` returning clean on the target. Two `FileHandler` instances observed, both correctly pointing at the singleton. No rule mutation, no instance duplication, no scope drift.

### What the evidence establishes

- The on-disk rule definitions are correct and do not produce the observed block.
- The current daemon state does not reproduce the observed block.
- The daemon process that produced the failures was restarted at 19:05 UTC on 2026-04-23, ~2 hours after the self-recovery. The in-memory state at failure time is unavailable.
- The failure was real (nine database rows), transient (2-hour window), and self-recovered without code change.

### What the evidence does not establish

- Which `PolicyRule` actually matched at failure time. The pre-`cf2ea63c` persistence did not capture enough to reconstruct it.
- Why the matching occurred. Candidate explanations (boot-time race on mapping load, transient scope mis-derivation, state mutation in a since-gone process) cannot be distinguished from the remaining evidence.

## Decision

**Do not modify `.intent/enforcement/mappings/cli/interface_design.yaml` or any `cli.*` rule.** The YAML is correct; any change would be a false fix against a phantom condition.

**Do not attempt active reproduction** (restart-and-probe cycles against the running daemon). The bug's transient nature means reproduction is uncertain and expensive: a restart might produce another clean daemon, the test itself disrupts the remediation loop (which is the only alarm the system has for this class of bug), and the cost of a failed attempt is not zero.

**Rely on the passive instrumentation already in place.** Commit `cf2ea63c` (2026-04-23 18:31 UTC — which landed *during* the investigation of this incident, after the failures but before this ADR) added structured `ConstitutionalViolationError.to_dict()` persistence into `action_results.violations[]`, carrying `rule_name`, `path`, and `source_policy`. Any recurrence from this point forward persists full attribution directly to the database. No live introspection is required to identify the matching rule on the next occurrence.

**Park this finding until recurrence.** If the bug fires again, the new evidence identifies the rule directly and the diagnostic can resume with a known target. If it does not recur, the debt is bounded by process lifetime and cost is zero.

### What this ADR explicitly declines to do

- Narrow any `cli.*` rule scope.
- Add defensive defaults in `rule_extractor.extract_executable_rules` against the transient.
- Instrument IntentGuard init with rule-set hashing or boot-time assertions.
- Change the singleton pattern in `get_intent_guard`.

Each of these could be justified against a hypothetical bug. None is justified against the current evidence. Adding them now conflates "defensive code we happen to think of" with "defensive code the evidence demands." The north-star ordering — rules clear, enforcement real, then code — argues against speculative hardening.

## Consequences

**Positive:**

- Option A from the 2026-04-22 handoff is closed honestly rather than falsely. The false-close would have shipped a YAML change that diagnostic evidence does not support; the system would carry a hidden defect (whatever actually caused the block) masked by a confident fix.
- Recurrence, if it happens, produces better evidence than today's re-probe could — full structured violation in the database, no live introspection required, no ptrace-scope flap, no privileged attach.
- The decision records the *limits* of what was knowable: the failing process no longer exists, and no amount of current-state probing can recover its rule list. This is honest governance debt rather than forced closure.

**Negative:**

- The proximate cause of the 2026-04-23 incident remains unknown. If the bug is a recurring race, future incidents may cost real time before one is captured with full attribution.
- The fix.placeholders churn observed on 2026-04-22 (per handoff) is not evidence of the same bug. The current daemon has been running since 19:05 UTC on 2026-04-23 and has not reproduced the block. The TODO-on-violation_remediator.py write path is, in this process, succeeding.
- We have no mechanism to detect IntentGuard rule-state drift *in progress*. The live daemon can be introspected via the procedure established today (gdb attach, read-only injection), but that requires elevated privilege and does not fire automatically.

**Observability gap recorded:**

This incident revealed that CORE has no runtime signal for IntentGuard state integrity. The current options are:

1. Post-hoc DB inspection (structured-violation persistence, `cf2ea63c` and forward) — requires a failure to fire.
2. Live in-process dump via `gdb` + `pyrasite`-style payload — requires `sudo gdb` or a `ptrace_scope` flap, and only works while the process still exists.

Neither is a continuous signal. A daemon whose IntentGuard state has drifted into a wrong-but-silent configuration (for example: blocking nothing that should be blocked) would not surface until a downstream check failed. This gap is the same family as the cold-registry behavior recorded in the 2026-04-22 handoff (Option C); both are facets of "the daemon's in-memory governance state is not observable from outside." A continuous-signal design (periodic rule-set hash broadcast, `core-admin inspect intent-guard` command, or boot-time rule-count invariants) is parked as a separate decision. It is not required to close this ADR.

## Alternatives Considered

**Narrow `cli.resource_first` (and related `cli.*` rules) scope.** Rejected. The YAML is correct; narrowing a correct scope is a false fix. Shipping it would either have no effect (if the cause is not scope-related) or would mask a structural bug in the loader/extractor behind a scope override. Either outcome breaks the "enforcement real" layer of the north-star ordering.

**Restart the daemon repeatedly to reproduce.** Rejected. Transient reproduction is uncertain; a restart disrupts the remediation loop; and a failed reproduction attempt yields no evidence about whether the bug is gone or merely dormant. The cost/benefit inverts once passive instrumentation is in place.

**Add defensive rule-set validation at IntentGuard init.** Rejected at this stage. Without a hypothesis about what invariant to check, the validation either captures everything (and the first real rule change flags itself as a regression) or captures nothing useful. Deferred to the observability-gap decision above.

**Roll back the 2026-04-22 reclassification of `fix.placeholders` from `moderate` to `safe`.** Rejected. The reclassification is orthogonal to the block. The block occurred *after* the proposal was approved and dispatched; the classification only affects whether approval is manual or automatic. Rolling back would silence the alarm without addressing the cause.

## Non-Goals

- This ADR does not redefine how IntentGuard rules are loaded, derived, or cached.
- This ADR does not commit to a continuous observability mechanism for runtime governance state. That is a separate decision, informed by this incident but not bound by it.
- This ADR does not attempt a post-mortem of which specific rule matched. The evidence required is gone; forcing a conclusion would be speculation.

## Artifacts

- `reports/diagnostics/2026-04-24_intentguard_live_dump.md` — live daemon memory dump from PID 813659, captured via `gdb` injection.
- `reports/diagnostics/_ig_live_payload.py` — the read-only introspection payload used for the dump. Kept for reuse against future occurrences.
- `reports/diagnostics/2026-04-23_intentguard_cli_trace.md` — the preliminary out-of-process trace from 2026-04-23.
