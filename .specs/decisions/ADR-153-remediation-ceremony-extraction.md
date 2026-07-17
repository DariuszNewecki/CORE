---
kind: adr
id: ADR-153
title: "ADR-153 — Extracting the remediation ceremony to retire ViolationExecutorWorker's worker-to-worker import"
status: accepted
---

<!-- path: .specs/decisions/ADR-153-remediation-ceremony-extraction.md -->

# ADR-153 — Extracting the remediation ceremony to retire `ViolationExecutorWorker`'s worker-to-worker import

**Date:** 2026-07-17
**Governing paper:** none directly — implements the remedy stated in
`architecture.workers.no_direct_worker_import`'s own rule text
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-17 — drafted under governor direction, issue #793)
**Relates to:** #793 (worker-import exclude extraction — this ADR is the
architectural sixth of its six files; the other five are plain-function
relocations handled directly, no ADR), ADR-152 (the exemption-schema work
that surfaced this file while investigating #793's premise), ADR-104 D9
(the remediation-attempt-cap circuit breaker this ceremony's callers both
respect)

---

## Context

### The exclude's premise is false for one of its six files

`architecture.workers.no_direct_worker_import`'s mapping carries 6
whole-file `excludes:` (`.intent/enforcement/mappings/architecture/layer_separation.yaml`),
commented "helper modules co-located in will/workers/ — not Worker
subclasses." These 6 excluded files (the *importers*) are
`proposal_consumer_worker.py`, `proposal_pipeline_shop_manager.py`,
`violation_remediator.py`, `violation_remediator_proposal.py`,
`audit_violation_sensor.py`, `violation_executor.py`. Verified against
every module *they import* (a distinct, larger list, since several
excluded files import more than one helper — `proposal_consumer_effects.py`,
`proposal_consumer_revival.py`, `circuit_breaker.py`,
`violation_remediator_blackboard.py`, `violation_remediator_proposal.py`
itself, `audit_violation_filter.py`, `audit_violation_normalizer.py`):
true for 5 of the 6 excluded files — none of their imports define a
`Worker` subclass. Those five files' exclude is a straightforward
extraction, handled directly alongside this ADR, no architectural
decision required (see Consequences).

The sixth, `violation_executor.py`, is not what the comment claims.
`ViolationExecutorWorker` imports `ViolationRemediator` from
`will.workers.violation_remediator_body` — and `ViolationRemediator`
**is** a `Worker` subclass
(`class ViolationRemediator(BlackboardMixin, CeremonyMixin, ContextMixin, LLMMixin, Worker)`).
It is not a type reference: `violation_executor.py` instantiates it and
calls it inline, synchronously, taking the result back:

```python
remediator = ViolationRemediator(
    core_context=self._ctx, target_rule=target_rule,
    write=self._write, caller_uuid=self._worker_uuid,
)
ok = await remediator.process_file(file_path, findings)
```

This is exactly what the rule forbids — one Worker holding a reference to
another and calling its methods, bypassing the blackboard-recording
guarantee that inter-worker communication is supposed to go through. The
exclude has been giving this a pass, mischaracterized, since the rule
shipped.

### `ViolationExecutorWorker` and `ViolationRemediatorWorker` are not the same lineage — a naming trap worth naming explicitly

Before proposing a fix, it's worth ruling out an assumption the similar
names invite: is `will/workers/violation_remediator.py`'s
`ViolationRemediatorWorker` related to `violation_remediator_body`'s
`ViolationRemediator`, such that they should consolidate? Checked
directly — they are not. `ViolationRemediatorWorker` handles **mapped**
rules (a `remediation_map` entry exists): "no LLM, no file writes,"
converts findings into governed Proposals routed through
`ProposalConsumerWorker`/`ProposalExecutor`'s approval pipeline.
`ViolationExecutorWorker` is explicitly documented as "the discovery path
for **unmapped** rules" — findings with no codified fix yet — and
delegates to `ViolationRemediator`'s direct LLM ceremony as the fallback
for that population. `ViolationRemediatorWorker` is mentioned in roughly
thirty places across `src/` (`blackboard_query_service.py`,
`blackboard_proposal_service.py`, `proposal_supervision_service.py`,
`circuit_breaker.py`, `violation_remediator_proposal.py`, and others) —
every one of them a docstring, comment, or log-message string; grepped
directly, none is an import or an instantiation. `ViolationRemediatorWorker`
is not imported or instantiated by the other lineage, and vice versa.
These are two deliberately separate remediation strategies for two
non-overlapping populations. This ADR does not touch
`ViolationRemediatorWorker` or the Proposal pipeline at all.

### The ceremony is already a self-contained, parameterized, claim-independent unit

`ViolationRemediator.process_file(file_path, findings)` is documented in
its own docstring as "the Will → Body delegation interface for file
remediation," called "after [the caller] has already claimed findings and
performed the RemediationMap gate check." It delegates to
`_process_file` → `_plan_file` (read source, build architectural context,
gate on confidence) → `_execute_file` (LLM invocation, Crate, Canary,
apply, git commit). Verified directly: the three mixins backing this path
(`CeremonyMixin`, `ContextMixin`, `LLMMixin`) reference exactly two `self`
attributes between them — `self._ctx` and `self._target_rule` — both
plain constructor-set values, nothing Worker-specific. The ceremony does
not care who claimed the findings or how; it only needs the file path,
the findings, and somewhere to record outcomes.

### There is no autonomous/daemon path — three real consumers, verified, none of them "autonomous"

The first draft of this ADR assumed two consumers — the executor
(delegate) and an autonomous `run()` loop, "always-invoked, properly
registered." That assumption doesn't survive checking the worker's own
declaration. `.intent/workers/violation_remediator_body.yaml` states
directly: *"CLI-triggered Body-layer acting worker for per-rule LLM
remediation. **Not daemon-run**. Instantiated directly by `core-admin
workers remediate`. The daemon discovery path is `ViolationExecutorWorker`."*
`metadata.status: paused`. No daemon startup path registers this worker
anywhere in `src/body/infrastructure/` or `src/cli/commands/daemon.py`.

The real consumer set, verified against `src/cli/resources/workers/remediate.py`:

1. **Executor-delegate** (`violation_executor.py:316`, daemon-live) —
   `ViolationExecutorWorker` claims unmapped-rule findings, gates on the
   RemediationMap, then calls `ViolationRemediator(..., caller_uuid=self._worker_uuid).process_file(...)`.
   Today's identity substitution (Context, next section) lives here.

2. **CLI rule-mode** (`remediate.py:290-323`, `_run_rule_pipeline`) —
   genuinely clean today: `ViolationRemediator(core_context=..., target_rule=..., write=...)`,
   no `caller_uuid`, then `await remediator.start()` — the real `Worker.start()` →
   `run()` → real `_claim_open_findings()` under its own genuine
   `_worker_uuid`, real blackboard claim/mark. CLI-triggered, not
   daemon-scheduled, but not impersonating anyone either.

3. **CLI file-mode** (`remediate.py:138-215`, file-audit pipeline) — also
   real identity, no `caller_uuid` — but `.start()` runs with
   `_claim_open_findings`, `_mark_findings`, **and `_mark_finding`**
   monkeypatched onto the instance to bypass the blackboard entirely,
   feeding synthetic findings built from an ad-hoc single-file audit (the
   code's own comment: *"Bypass blackboard: ... no blackboard entries
   exist"*). This is a real, deliberate diagnostic mode, not a workaround
   to route around.

No path is "autonomous" in the daemon-scheduled sense. D3 below is
written against these three real paths, not the two originally assumed.

### The dependency surface is broader than "posting"

`_execute_file` calls `self.post_observation(...)` and `self.post_report(...)`
directly (`Worker`/`BlackboardPublisher` base-class methods).
`blackboard.py`'s `_post_failed` — called from both `_plan_file` and
`_execute_file` on every failure branch — does the same
(`blackboard.py:33`: *"Requires self.post_finding() from Worker base"*).
`_mark_findings` (also called from both phases) mutates blackboard-entry
status via `self._ctx.registry.get_blackboard_service()`, not via a
Worker-base method — but it is exactly the method CLI file-mode
monkeypatches to a no-op, which matters directly for D2 below: any
extraction that moves `_mark_findings` off the `ViolationRemediator`
instance and into the extracted service removes the very attribute
file-mode currently patches. A poster covering only
`post_report`/`post_finding`/`post_observation` is not sufficient; the
injected surface has to cover the mark/fail operations too, or file-mode
has nothing left to inject a no-op into.

`_check_atomic_action_coverage` (`blackboard.py:117`, called from
`_execute_file`) is pure read logic against `self._ctx` — no posting, no
marking, moves cleanly with no injection needed.

Today's posting/marking identity is solved by substitution, at
`ViolationRemediator.__init__`:

```python
if caller_uuid is not None:
    self._worker_uuid = caller_uuid
# ViolationRemediator is not registered in worker_registry in this mode —
# its own UUID would cause an FK violation.
```

A whole `Worker` is instantiated purely to run the ceremony, and it
overwrites its own identity with the caller's so its blackboard posts
don't FK-violate against a `worker_registry` it was never entered into.
This is attribution by impersonation, not attribution by construction —
worth calling out precisely because attribution is itself a constitutional
concern in this system (commit-authorship integrity, ADR-101 D1;
consequence-chain evidence, ADR-148), not a cosmetic detail.

Confirmed via `_host.py` (the mixins' own typing-only host contract,
already isolating exactly the surface they depend on): `_ctx`,
`_target_rule`, `_write`, `_worker_uuid` (claim-only, stays with
`ViolationRemediator.run()` — not part of what moves), plus the full
`Worker` posting interface.

---

## Decision

### D1 — Extract the ceremony to `src/will/remediation/`, a non-workers Will subdirectory

New module, `src/will/remediation/`. Moves: `process_file`/`_process_file`/
`_plan_file`/`_execute_file` (from `worker.py`), `CeremonyMixin`
(`ceremony.py`), `ContextMixin` (`context.py`), `LLMMixin` (`llm.py`), and
the ceremony-support subset of `BlackboardMixin`
(`_mark_findings`/`_post_failed`/`_check_atomic_action_coverage` —
`_claim_open_findings` stays behind; it's `run()`-loop-only, never called
from the ceremony path). Class name: `RemediationCeremony` — matching the
domain vocabulary the code already uses throughout ("full ceremony,"
`CeremonyMixin`, "Crate/Canary ceremony").

Matches the rule's own remedy text verbatim: "utility functions shared
between workers belong in `shared/` or in a non-workers Will subdirectory."
`shared/` was considered and rejected — this is Will-layer remediation
business logic (LLM invocation, git commits), not cross-cutting substrate.

### D2 — A `RemediationBlackboard` Protocol covering posting *and* marking, not a bare poster

`RemediationCeremony`'s methods take a `blackboard` parameter typed as a
`Protocol` exposing `post_report`, `post_finding`, `post_observation`
(the Worker-base posting surface `_execute_file`/`_post_failed` need) and
`mark_findings`, `post_failed` (the operations CLI file-mode currently
monkeypatches). This is wider than a first draft's "poster" — narrowed to
posting alone — because that draft didn't yet account for file-mode's
monkeypatch of `_mark_findings`; once that method lives inside the
extracted service instead of on a `ViolationRemediator` instance, there is
nothing left on the object for `remediate.py` to patch. A capability
Protocol means `RemediationCeremony` depends on "something that can post
and record outcomes," not on a `Worker`. This continues `_host.py`'s
existing "typing-only host contract" pattern (`HostBase` is `object` at
runtime, a typed view under `TYPE_CHECKING`) rather than inventing a new
one.

`_mark_finding` (singular) is not part of the Protocol. Verified directly:
it is called only from `_mark_findings`' own non-abandon-status branch
(`blackboard.py:69`) — an internal implementation detail of the plural
method, never invoked from the ceremony surface itself. File-mode's
current monkeypatch of both is defensive redundancy, not evidence of two
call sites; the Protocol needs only `mark_findings`.

Two concrete implementations:

- **`WorkerRemediationBlackboard`** — wraps a real `Worker` instance
  (whichever one is calling: `ViolationExecutorWorker` or
  `ViolationRemediator` itself), delegating every method to the wrapped
  worker's own `post_report`/`post_finding`/`post_observation` and to the
  real blackboard service for `mark_findings`/`post_failed`. Backs paths
  1 and 2.
- **`NullRemediationBlackboard`** — every method is a true no-op:
  `mark_findings`/`post_failed` (matching today's
  `_noop_mark_findings`/`_noop_mark_finding`), **and**
  `post_report`/`post_finding`/`post_observation`. This is a deliberate
  behavior change from today, stated plainly here and in Consequences:
  today, file-mode's `remediator.start()` still runs the real `run()`
  loop underneath the monkeypatch, so `post_heartbeat()` and the
  ceremony's `post_report`/`post_observation` calls fire for real, under
  file-mode's own genuine `_worker_uuid` — only the claim/mark lifecycle
  is bypassed. Under D4, file-mode no longer instantiates
  `ViolationRemediator` or calls `start()`/`run()` at all — there is no
  Worker left to post *through*, registered or otherwise. Making
  `NullRemediationBlackboard` post as well as mark/fail a true no-op is
  the only choice consistent with that: any "real calling worker" for it
  to delegate posts to no longer exists on this path. The alternative
  (keep a minimal registered Worker alive on the file-mode path solely so
  it has something to post through) was considered and rejected — it
  would contradict D3/D4's "no worker needed for a synthetic, ad-hoc,
  single-file diagnostic run" simplification, which is the actual reason
  this path is worth extracting cleanly. Backs path 3, replacing today's
  runtime monkeypatch with a typed, reviewable implementation of a real
  interface — and retiring blackboard chatter for a mode that never had
  an autonomous consumer for it anyway.

### D3 — Attribution invariant, three paths

Every ceremony post is attributed to the claim-owner, with no identity
substitution anywhere; every mark/fail is either real (paths 1 and 2) or
an honest, typed no-op (path 3) — never a monkeypatched instance method:

1. **Executor path** — `ViolationExecutorWorker` claims (unmapped rules),
   gates on the RemediationMap, constructs `WorkerRemediationBlackboard(self)`,
   calls `RemediationCeremony`. Posts and marks land under
   `ViolationExecutorWorker`'s own, genuinely-registered identity.
2. **CLI rule-mode path** — `ViolationRemediator.run()` claims its own
   findings, constructs `WorkerRemediationBlackboard(self)`, calls the
   same `RemediationCeremony`. Posts and marks land under
   `ViolationRemediator`'s own identity — CLI-triggered, not
   daemon-scheduled, but not borrowed either.
3. **CLI file-mode path** — `remediate.py` builds synthetic findings
   directly (as it does today), constructs `RemediationCeremony` with a
   `NullRemediationBlackboard`, and calls it — no `ViolationRemediator`
   instantiation needed at all for this path, since there is no real
   claim/mark lifecycle to run through a `Worker`'s `start()`/`run()`.
   No blackboard entry of any kind is posted for this path after
   extraction — not heartbeat, not report, not observation (see D2's
   `NullRemediationBlackboard` for why this is a deliberate, stated
   behavior change, not an oversight). User-facing feedback for this CLI
   invocation is the existing console/log output `remediate.py` already
   prints, unchanged.

No path substitutes a UUID. The `caller_uuid` parameter and the
`__init__` override it drives are deleted, not replaced with an
equivalent — impersonation isn't needed once every caller either posts
through its own identity or explicitly declines to record.

### D4 — `ViolationRemediator` survives, thinner; `violation_executor.py` stops importing it; `remediate.py`'s file-mode stops instantiating it

`ViolationRemediator` (in `violation_remediator_body/worker.py`) keeps its
`run()` loop — claim, group by file, build a `WorkerRemediationBlackboard(self)`,
call `RemediationCeremony` per file, report — and shrinks by the extracted
methods. It remains a genuine `Worker`, used by CLI rule-mode exactly as
today. `violation_executor.py` stops importing
`will.workers.violation_remediator_body` entirely; it imports
`will.remediation` and calls `RemediationCeremony` directly.
`remediate.py`'s file-mode function stops instantiating
`ViolationRemediator` and monkeypatching it; it calls `RemediationCeremony`
directly with a `NullRemediationBlackboard`. Three call sites' coupling
resolves from one extraction.

`ViolationRemediatorWorker` (`will/workers/violation_remediator.py`, the
mapped-rule Proposal-creation worker) is untouched — see Context; it was
never coupled to this ceremony and consolidating it in would conflate two
deliberately separate remediation strategies.

### D5 — Remove the exclude; no replacement entry

Once D1–D4 land, `violation_executor.py` no longer imports anything under
`will.workers`/`body.workers` — its exclude entry in
`no_direct_worker_import`'s mapping is deleted outright, not migrated to
`governed_exclusions` (ADR-152). There is no ongoing debt to track; the
violation is gone, not permitted.

---

## Consequences

### Positive

- Closes the one file in #793 where the exclude's premise was false —
  the actual constitutional violation is fixed, not re-documented.
- Deletes the `caller_uuid`/UUID-substitution hack outright. Attribution
  for all three real call sites becomes structural (real identity, or an
  honest declared no-op) instead of policy-by-convention or runtime
  monkeypatching.
- `remediate.py`'s file-mode gets a typed, reviewable
  `NullRemediationBlackboard` in place of three monkeypatched instance
  methods — a real implementation of a real interface, easier to test in
  isolation than patched attributes on a live `Worker`.
- `_host.py`'s existing typing-only host contract pattern gets a second,
  broader application (`RemediationBlackboard`), reinforcing rather than
  inventing a house style.
- Corrects two naming/characterization traps on the record — the
  `ViolationRemediatorWorker`/`ViolationRemediator` name collision, and
  the nonexistent "autonomous" daemon path — so a future reader doesn't
  reach for either false assumption again.

### Negative

- Real refactor across 5 files (`worker.py`, `ceremony.py`, `context.py`,
  `llm.py`, `blackboard.py`) plus all three call sites (including
  `remediate.py`, not accounted for in the first draft) — larger than the
  other five #793 files combined and larger than first scoped. Behavior-
  preserving for two of the three paths, but "refactor of the LLM/Crate/
  Canary/commit ceremony across three real entry points, one of which
  changes behavior" warrants full test coverage before and after, not
  just a diff review.
- **Deliberate behavior change, approved (Option A):** CLI file-mode
  (`core-admin workers remediate --file`) currently posts a real
  `worker.heartbeat` and, in dry-run, a `dry_run_complete` observation to
  the blackboard, under its own genuine `_worker_uuid`. After this ADR,
  file-mode posts nothing to the blackboard at all — no worker is
  instantiated for this path, so there is nothing to post through.
  User-facing behavior (console output, dry-run/write file results) is
  unaffected; only the blackboard side-channel, which this path's
  synthetic, ad-hoc, non-blackboard-discovered findings never had an
  autonomous consumer for anyway, is dropped. This was weighed against
  keeping a minimal registered Worker alive on this path solely to have
  something to post through (Option B) and rejected — Option B would
  contradict the actual reason this path is worth extracting cleanly
  (D3/D4: no worker needed for a synthetic, single-file diagnostic run).
- `ViolationRemediator` becomes a thinner class with less to look at in
  one file — a small readability cost, offset by the ceremony now being
  independently testable without a `Worker` in the fixture, and by
  `remediate.py`'s file-mode no longer needing a `Worker` instance at all.

### Neutral

- No change to the RemediationMap gate, the circuit breaker (ADR-104 D9),
  dry-run semantics, or the Crate/Canary/commit sequence itself — this
  ADR relocates and re-parameterizes, it does not redesign the ceremony.
- `governed_exclusions` (ADR-152) is not used here — this file needed a
  real fix, not a governed exemption. Recognizing when a "candidate
  exemption" is actually a removable violation, rather than automatically
  routing it into the new exemption register, is part of using that
  infrastructure honestly.

---

## Verification

- Executor and CLI rule-mode behavior is unchanged in observable outcome
  (findings resolved/abandoned/indeterminate, blackboard posts, git
  commits) — call shape changes, outcomes don't. CLI file-mode's
  dry-run/write console output is unchanged; its blackboard posts are
  **not** — see the stated behavior change below.
- A test asserts posts from the executor path carry
  `ViolationExecutorWorker`'s `_worker_uuid`; posts from CLI rule-mode
  carry `ViolationRemediator`'s own `_worker_uuid`; CLI file-mode posts
  **nothing** to the blackboard at all — `post_report`/`post_finding`/
  `post_observation`/`mark_findings`/`post_failed` are all genuinely
  no-ops (not silently swallowed exceptions) — the three-path attribution
  invariant (D3), directly, not inferred from absence of errors.
- A before/after comparison confirms the behavior change is scoped to
  exactly file-mode: running `core-admin workers remediate --rule X`
  (CLI rule-mode) before and after this change produces the same
  blackboard rows; running the file-mode command before this change shows
  a `worker.heartbeat` row and (in dry-run) a `dry_run_complete`
  observation under the file-mode invocation's `_worker_uuid`, and after
  this change shows neither.
- `grep -rn "will.workers\|body.workers" src/will/workers/violation_executor.py src/cli/resources/workers/remediate.py`
  returns nothing after the change (the latter still imports
  `will.remediation`, which is not `will.workers`).
- `core-admin code audit -r architecture.workers.no_direct_worker_import`
  passes with the `violation_executor.py` exclude entry removed and no
  replacement `governed_exclusions` entry added for it.
- mypy clean on all touched files plus `will/remediation/`; the
  `RemediationBlackboard` Protocol verified the same way `_host.py`'s
  existing typed contract is.

---

## References

- Issue #793 — the six-file exclude this ADR resolves the architectural
  sixth of.
- `architecture.workers.no_direct_worker_import` — the rule, and its own
  remedy text this ADR follows verbatim.
- ADR-152 — the exemption-schema work whose investigation surfaced this
  file's real violation.
- ADR-104 D9 — the remediation-attempt-cap circuit breaker both live
  paths respect, unchanged by this ADR.
- ADR-101 D1 — commit-authorship integrity; the constitutional grounding
  for why attribution-by-impersonation (the `caller_uuid` hack) is a real
  concern here, not a style preference.
- `.intent/workers/violation_remediator_body.yaml` — the worker's own
  declaration, source of the "CLI-triggered, not daemon-run, status:
  paused" fact this ADR's consumer model is built on.
- `src/cli/resources/workers/remediate.py` — the previously-unaccounted-for
  third consumer (rule-mode and file-mode), verified directly.
- `src/will/workers/violation_remediator_body/_host.py` — the existing
  typing-only host contract pattern this ADR's `RemediationBlackboard`
  Protocol extends rather than replaces.
