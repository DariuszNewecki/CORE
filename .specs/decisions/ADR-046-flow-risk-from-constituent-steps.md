<!-- path: .specs/decisions/ADR-046-flow-risk-from-constituent-steps.md -->

# ADR-046 — Flow risk derived from constituent steps; close the test-format heal loop

**Status:** Accepted
**Date:** 2026-05-15
**Authors:** Darek (Dariusz Newecki)
**Closes:** #290 (Should flows be invoked from the autonomous remediation
pipeline at all?)
**Relates to:** ADR-008 (action impact classification), ADR-010 (Finding/Proposal
contract), ADR-015 (consequence-chain attribution — the blast-radius framing
behind #290), ADR-033 (parameter routing safe default — closed the original
flow TypeError that surfaced #290), ADR-035 (one finding, one proposal),
ADR-037 (flow-scope exception to ADR-035), CORE-Flow.md §6–§7,
CORE-TestGovernance.md §3

---

## Context

`core-admin dev sync` halts in its fix phase when `tests/**/*.py` carries
formatting drift. 13 of the 16 currently drifting files are
`test_generated.py` — outputs of the autonomous test-generation loop. The
audit produces zero `style.formatter_required` findings against these files
(the rule's scope excludes `tests/**`), so no remediation proposal is ever
created, and the drift accumulates silently until the next manual `dev sync`
trips on it.

The declared autonomy story for these findings is intact end-to-end *except
for one link*:

1. **Map** (`.intent/enforcement/remediation/auto_remediation.yaml:195–204`)
   declares `test.missing` / `test.failure` → `flow: flow.build_tests`.
2. **Flow** (`.intent/flows/flow.build_tests.yaml:26–49`) declares four
   steps in order: `build.tests` (required) → `fix.imports`, `fix.headers`,
   `fix.format` (each optional, auto-heal).
3. **Action** (`src/body/atomic/build_tests_action.py:7–9`) docstring is
   explicit: "Auto-heal (fix.imports, fix.headers, fix.format) runs as
   subsequent steps of `flow.build_tests`, not inside this AtomicAction —
   composing other AtomicActions is a Flow concern, not an Atomic one."
4. **Worker** (`src/will/workers/test_remediator/_operations.py:28,169–178`)
   hardcodes `_TARGET_ACTION_ID = "build.tests"` and creates a
   `ProposalAction(action_id=...)` — a bare-action proposal, not a
   flow-kind proposal.
5. **Executor** (`src/will/autonomy/proposal_executor.py:256–268`) branches
   on `ProposalAction.ref_kind`. The TestRemediator proposal always takes
   the `action` branch and dispatches through `ActionExecutor`. `FlowExecutor`
   is never invoked. Steps 2–4 of `flow.build_tests` never run.

The audit can't see the resulting drift (rule scope), the workers can't
heal it (flow not dispatched), and `dev sync` is the only path that
detects it (wider target than the audit, `src` + `tests`).

### Why the naïve fix doesn't work alone

Changing TestRemediator to emit `flow_id="flow.build_tests"` routes
proposals through `FlowExecutor`. But the risk classifier
(`src/will/autonomy/proposal.py:305–308`) hardcodes every flow as
`moderate`:

```python
elif action.flow_id is not None:
    # Flows are composed of multiple actions — treat as moderate risk
    # until FlowRegistry exposes per-flow impact computation.
    action_risks[action.flow_id] = "moderate"
```

`RiskAssessment.requires_approval()` returns `True` for `moderate` |
`dangerous` (`proposal.py:98–100`). So a flow-kind TestRemediator proposal
becomes draft-awaiting-approval — landing in the governor inbox at the rate
the test-generation loop produces them.

This contradicts the data. The four constituent steps of `flow.build_tests`
are all classified `safe` in
`.intent/enforcement/config/action_risk.yaml`:

```yaml
build.tests:  safe
fix.imports:  safe
fix.headers:  safe
fix.format:   safe
```

The correct risk for `flow.build_tests` is `safe`. The classifier just
doesn't look. The hardcoded `"moderate"` is a placeholder explicitly
documented as such (its comment says "until FlowRegistry exposes per-flow
impact computation").

### Why the rule-scope fix is the wrong altitude

An alternative — remove `excludes: tests/**/*.py` from
`style.formatter_required` so the audit catches the drift — would work
once but treats the symptom. The test files arrive unformatted because the
flow that was designed to format them never runs. Healing them after the
fact via the audit/remediation pipeline is a longer path than running the
auto-heal step the flow already declares. It also leaves the broader
declaration/implementation divergence unaddressed: any future flow
authored under the assumption that risk comes from constituent steps will
encounter the same hardcoded `moderate` and the same draft pileup.

The right level is the risk classifier, because the classifier
mis-classifying every flow is the load-bearing defect — `flow.build_tests`
is one instance.

---

## Options considered

**Option A — Recalibrate `compute_risk()` to inspect flow contents.**
Resolve a flow's risk by walking its declared steps, looking each step up
in `action_registry` (or recursively for nested flows), and taking the
max. Pair with the TestRemediator switch to `flow_id`. Both changes land
together. Generalises beyond `flow.build_tests` — every future flow gets
a correct classification with no per-flow overrides.

**Option B — Per-flow override in `action_risk.yaml`.**
Add `flow.build_tests: safe` and have `compute_risk()` check the same map
for flows that it already checks for actions. Minimal change; works for
the immediate problem. But every new flow needs an explicit risk row,
and the classifier still cannot answer "what is the risk of this flow?"
from the flow's own declaration. Pushes the truth out of `.intent/flows/`
into `.intent/enforcement/config/action_risk.yaml` and asks authors to
keep two artifacts coherent.

**Option C — Keep TestRemediator on the bare action; inline the auto-heal
steps inside `build.tests`.**
Reverts the design declared in `CORE-Flow.md §7` and contradicts the
build_tests_action docstring that defers composition to the Flow layer.
Short-term, breaks the design contract that
"composing AtomicActions is a Flow concern."

**Option D — Drop `excludes: tests/**` from `style.formatter_required`.**
Discussed above. Symptom-level. Loads more files onto the audit's
`workflow_gate` (cheap, near-zero cost) but does not address the
classifier defect that mis-routes every flow proposal.

### Relation to #290

Issue #290 framed three options for whether flows should be
auto-remediated at all: (1) status quo, (2) strip flow refs from
`auto_remediation.yaml` entirely, (3) per-flow `auto_remediable` flag.
The issue's underlying concern was blast radius — `flow.fix_code` runs
nine fixers across all of `src/` and could be triggered by a single
finding, ambiguating ADR-015's consequence-chain attribution.

Option A above is effectively a fourth answer not enumerated in #290:
flows remain auto-remediable, but their risk is computed from constituent
steps. Blast-radius control then comes from the existing approval gate
rather than a per-flow flag. `flow.fix_code` (contains `fix.modularity`,
which is `moderate`) classifies `moderate` → `approval_required = True`
→ governor reviews before dispatch. `flow.build_tests` (all-safe steps)
classifies `safe` → auto-executes. No new metadata is required, no
opt-in flag, no second source of truth: the risk emerges from the flow
declaration itself, and the boundary moves automatically as flow
contents change. The blast-radius concern is preserved; the autonomy
on safe flows is unlocked.

---

## Decision

Two coordinated sub-decisions, landing together.

### D1 — Risk for a flow is computed from its constituent steps

`Proposal.compute_risk()` (`src/will/autonomy/proposal.py:287–348`) is
extended so that when a `ProposalAction` carries `flow_id`, the classifier
resolves the flow through `flow_registry.get(flow_id)` and computes the
flow's risk as the **maximum** of its steps' impact levels. Action steps
resolve via `action_registry`; nested flow steps recurse through the same
function. The hardcoded `"moderate"` literal at `proposal.py:307` is
replaced by this computation.

When the flow cannot be resolved (registry miss, malformed declaration),
the classifier falls back to `"moderate"` — the existing conservative
default — and logs at WARNING. This preserves the current behaviour for
the failure mode while removing the false-classification for the success
mode.

The implementation is local to `proposal.py` and a small helper in or
adjacent to `body/flows/registry.py`. No changes to existing flow YAML
or action YAML are required.

### D2 — TestRemediatorWorker emits a flow-kind proposal

`src/will/workers/test_remediator/_operations.py` switches from
`_TARGET_ACTION_ID = "build.tests"` to `_TARGET_FLOW_ID =
"flow.build_tests"`, and constructs the proposal as
`ProposalAction(flow_id=_TARGET_FLOW_ID, parameters={...}, order=0)`.
`compute_risk()` (post-D1) classifies the proposal as `safe` because
each step in `flow.build_tests` is `safe`. The existing auto-approval
path (`_operations.py:208–220`) promotes the proposal to APPROVED.
`ProposalConsumerWorker` (`approval_required: false`) picks it up. The
executor branches on `ref_kind == "flow"` and dispatches via
`FlowExecutor`. All four declared steps run with `write=True`. The
generated test file arrives formatted.

### D3 — Optional-step failure must be discoverable, not log-only

`FlowExecutor._execute_step` (`src/body/flows/executor.py:123–128`)
currently logs at WARNING when an optional step fails and continues. For
auto-heal steps inside `flow.build_tests`, this is the difference between
"file landed unformatted and we know" and "file landed unformatted and
nobody knows."

The per-step data needed already exists end-to-end:
`FlowResult.data["steps"]` (`src/body/flows/result.py:79–101`) carries
`ref_id, kind, required, ok, duration_sec` per step;
`ProposalExecutor._execute_actions` (`src/will/autonomy/proposal_executor.py:272–278`)
wraps each action/flow outcome into `action_results[ref_id:order]` with
that data intact. Two consumers downstream receive this:
`apply_success_effects()` in
`src/will/workers/proposal_consumer_effects.py:32–105` (per-proposal
side-effects — forwards `finding_to_post` and emits `test.run_required`),
and the `proposal_consumer_worker.run.complete` report assembled directly
in `src/will/workers/proposal_consumer_worker.py:214–227` (per-tick
aggregate — coarse counts only). The information reaches both
observability surfaces; neither currently extracts it.

Two implementation sites are viable:

**D3a — Per-step finding from `apply_success_effects()`.** Add a third
emission loop to `proposal_consumer_effects.py:32` that walks
`action_results` for entries with `kind == "flow"`, drills into
`data["steps"]`, and for each step with `ok == False and required ==
False` posts a finding under a new subject family, e.g.
`flow.optional_step_failed::<flow_id>::<step_ref>::<file_path>`. Pros:
constitutional grain ("everything is a finding"); per-step granularity;
downstream consumers (audit, remediation, dashboard) can subscribe via
existing blackboard mechanisms; opens a path for self-healing of the
auto-heal itself. Cons: new subject family — needs vocabulary discipline
(documented in `CORE-Vocabulary.md` / `vocabulary_canonical_store`) and
a clear consumer story; risks subject-noise if many flows fail optional
steps for the same reason.

**D3b — Enriched `run.complete` payload.** Extend the per-proposal entry
appended to `results` in `proposal_consumer_worker.py:178–189` with a
`flow_step_failures: list[dict]` field, populated by inspecting
`action_results` for flow-kind entries. Pros: minimal new surface — the
report already lands on the blackboard and feeds the Observer's
snapshot; no new subject family; coarser-grained, fits if the goal is
"someone reading the recent reports can see what auto-healed and what
didn't." Cons: not addressable per-step (downstream consumers must parse
the report payload); not actionable as a finding; coarser correlation
with file paths.

This ADR adopts **D3a** for these reasons: (a) the test-format-heal loop
is exactly the case where a downstream consumer wanting to *re-fire*
`fix.format` on a specific file is a plausible future need, and only the
finding surface supports that; (b) the run.complete report's audience is
the dashboard/Observer, where a coarse per-tick summary already serves
its purpose; (c) the constitutional grain weighs in this direction.
D3b remains a fallback if vocabulary discipline cannot be lined up in
the same change-set — in that case, ship D3b first and convert to D3a
when the subject family is registered.

Audit-side and dashboard surfacing of `flow.optional_step_failed`
findings is out of scope for this ADR.

---

## Consequences

### Positive

- `test_generated.py` files arrive constitutionally clean from the
  autonomous loop. `dev sync` stops finding format drift in `tests/` that
  no autonomous path could have prevented.
- Flow risk classification becomes a property of the flow declaration,
  not a per-flow override in a separate config artifact. New flows
  composed of safe steps auto-approve; new flows that include a moderate
  or dangerous step require approval — both decisions traced to a
  declared step risk, not to the existence-or-not of a row in
  `action_risk.yaml`.
- The placeholder comment at `proposal.py:307` retires. The
  classifier's behaviour matches its own stated intent.
- Optional-step failures inside auto-heal flows become observable
  through the existing blackboard surface rather than silently lost to
  the log.

### Negative

- The classifier acquires a dependency on `flow_registry`. The registry
  is already loaded at proposal-construction time elsewhere
  (proposal_executor.py:257), but `compute_risk()` is currently
  registry-free. The new dependency must be import-safe in the
  serialisation paths that call `compute_risk()` outside the executor
  (notably `proposal_mapper.py` round-trips).
- One class of past proposals — created before this ADR with
  `flow_id="flow.build_tests"` and marked `moderate` — would, on
  re-evaluation, be `safe`. None are observed in the live state today
  (TestRemediator has always emitted bare actions). The ADR does not
  prescribe back-fill; new proposals get the new classification, old
  ones keep theirs.
- `build.tests` overwrites the destination test file unconditionally.
  The chain is `action_build_tests` → `action_create_file`
  (`file_ops.py:72`, no existence check) →
  `FileHandler.write_runtime_text` (`file_handler.py:125`, no existence
  check) → `_atomic_write_text` (`file_handler.py:260–264`,
  `tmp.replace(abs_path)` is unconditional). No hash check, no backup,
  no "skip if user-edited" guard. The action is named `file.create` but
  its semantics are upsert. If a human has manually edited the
  previously-generated test, those edits are silently lost on
  regeneration. The plausible re-trigger path is `test.failure`: a
  human-edited test that fails causes `TestRunnerSensor` to post
  `test.failure`, `TestRemediator` claims it, `build.tests` regenerates
  from scratch. `TestRemediator._get_active_build_tests_source_files`
  (`_operations.py:98–133`) dedupes against *in-flight* proposals —
  this prevents double-firing on the same source file, but does not
  prevent overwriting prior human edits on a later re-trigger. This
  risk is *not new* — it existed under the bare-action path too — but
  D2 makes the auto-heal more thorough, which makes the failure mode
  more visible (a previously-human-edited file is regenerated *and*
  reformatted). Mitigation — a hash-stamp on generated tests, a
  refusal-to-overwrite-if-divergent guard, or relocating the
  human-edit boundary to a different file altogether — belongs to a
  separate decision about `build.tests`'s overwrite contract; flagged
  here, not solved.

### Neutral

- Action-kind proposals (the vast majority) are unaffected by D1; the
  flow branch of `compute_risk()` is only entered when `flow_id` is set.
- TestRemediator's existing dedup/circuit-breaker logic
  (`_operations.py:178+`) continues to function — both action_id and
  flow_id flow through the same `(ref_id, file_path)` keying.
- `style.formatter_required`'s `excludes: tests/**/*.py` is unchanged.
  The audit doctrine — "test contents are a human surface, not an
  enforced one" — stays in force. The autonomous heal at generation
  time is the right altitude for this concern; the audit catching it
  later would be redundant.

---

## Verification

This ADR is verified when, after D1+D2+D3 land:

1. A fresh TestRemediator-produced proposal carries
   `flow_id="flow.build_tests"`, `risk.overall_risk = "safe"`,
   `approval_required = False`, and reaches APPROVED through the
   existing auto-approval path.
2. `ProposalConsumerWorker` executes the proposal via `FlowExecutor` and
   the resulting FlowResult shows all four declared steps attempted,
   with `build.tests` required-and-passing. `fix.format` either passes,
   or — if it fails — `apply_success_effects()` posts a
   `flow.optional_step_failed::flow.build_tests::fix.format::<file_path>`
   finding to the blackboard (per D3a).
3. A `test_generated.py` file produced by this path passes
   `poetry run ruff format --check tests/...` immediately after commit.
4. `core-admin dev sync` against a tree containing only such generated
   tests proceeds past the fix phase without halting.

A single end-to-end demonstration against one source file with no
existing test satisfies all four.

---

## References

- `.intent/enforcement/remediation/auto_remediation.yaml:195–204` —
  declared map: test.missing/test.failure → `flow.build_tests`.
- `.intent/flows/flow.build_tests.yaml:26–49` — four-step flow
  declaration.
- `.intent/enforcement/config/action_risk.yaml:22,33,34,36` —
  constituent steps all classified `safe`.
- `.intent/enforcement/mappings/code/style.yaml:19–29` —
  `style.formatter_required` scope excludes `tests/**`.
- `src/body/atomic/build_tests_action.py:7–9, 145–146` — auto-heal
  explicitly deferred to flow.
- `src/will/workers/test_remediator/_operations.py:28, 164–186, 208–220`
  — bare-action proposal construction and auto-approval path.
- `src/will/autonomy/proposal.py:98–100, 287–348` — classifier today.
- `src/will/autonomy/proposal_executor.py:251–268` — flow-vs-action
  dispatch.
- `src/body/flows/executor.py:103–145` — step-loop and optional-failure
  log-only behaviour (D3 motivation — the silent-failure source).
- `src/body/flows/result.py:79–101` — `FlowResult.data["steps"]` already
  carries per-step `ref_id, kind, required, ok` (D3 input data).
- `src/will/autonomy/proposal_executor.py:272–278` — `action_results`
  wraps each action/flow outcome with `data, kind` intact (D3 transport).
- `src/will/workers/proposal_consumer_effects.py:32–105` — per-proposal
  side-effects; the third emission loop in D3a lives here.
- `src/will/workers/proposal_consumer_worker.py:178–189, 214–227` —
  per-tick `run.complete` report payload (D3b fallback site).
- CORE-Flow.md §6–§7 — composition is a Flow concern, not an Atomic
  one.
- CORE-TestGovernance.md §1, §3 — what the test pipeline governs and
  what it does not.
- ADR-008 — action impact classification (the source of truth this ADR
  extends to flows).
- ADR-010 §7 — Finding/Proposal contract; remediation map authoring.
