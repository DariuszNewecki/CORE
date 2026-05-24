# ADR-071 — Action Diff Coherence Enforcement

**Date:** 2026-05-25
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Constitutional Completeness
**Closes:** None directly; closes the working-tree-race class surfaced 2026-05-24 by the b11f4dba / f78b5c64 / 81631145 incident
**Related:** ADR-021 (scoped autonomous git operations — extends D2/D3 from file-scope to content-scope), ADR-069 (claim lifecycle lease semantics — reuses the per-declaration no-runtime-fallback pattern), ADR-070 (source–projection coherence — extends the bounded-drift principle to the action-execution surface)

---

## Context

On 2026-05-24 at 10:25:45 CEST, autonomous proposal
`46654f38-8f51-4217-8fe8-a37c6712d33e` committed `b11f4dba`. The
proposal's declared intent was `fix.format` on a single scope file
(`src/will/workers/violation_executor.py`) addressing a
`workflow.ruff_format_check` finding. The resulting commit contained
116 lines of substantive blast-bound enforcement code — the human
architect's in-progress hardening work, attributed to autonomous
`fix.format` remediation. The architect documented the incident in
commit `81631145` as an "audit-trail honesty correction."

The proposal had previously yielded five consecutive times (10:21:44,
10:22:44, 10:23:44, 10:24:44, 10:25:44 minus one of those — actually
yielded at 10:21–10:24:44 and **passed** at 10:25:44) on ADR-021 D5's
pre-claim `scope_collision` check. The check correctly detected that
the human's unstaged edits to the scope file intersected the proposal's
scope and refused to claim. On the sixth cycle, between 10:24:44 and
10:25:44, the architect ran a `staged-commit-then-restore-unstaged`
sequence (mechanically: `git stash` → stage governance files →
`git commit` → `git stash pop`) for the paired hardening commits
`0ed0e72c` (10:25:30) and `f78b5c64` (10:25:53). The worker's
6th-cycle pre-claim check fell into the brief clean-tree window
between `git stash` and `git stash pop`, observed an empty
`git status --porcelain`, and proceeded. Execution and `git add` of
the scope file happened after `git stash pop` had restored the
unstaged 116 lines; `commit_paths` stages working-tree-vs-HEAD for
the declared paths, and those 116 lines were now part of that diff.

The architect stopped the daemon at 10:28:11 to halt the race. The
daemon has remained off for ~36 hours pending the governance fix.

### Why ADR-021's promise was kept and why the gap is elsewhere

ADR-021 D2/D3 promised that "both rollback and commit are
scope-bounded": `commit_proposal_changes`
(`src/will/autonomy/proposal_execution_pipeline.py:208–243`) stages
only `proposal.scope.files ∪ files_produced`, never `git add -A`.
Inspection of `b11f4dba` confirms a single-file commit on the
declared scope. **Scope-binding worked. The race did not violate it.**

The gap is at a different layer. Scope-binding bounds **which files**
the autonomous worker is permitted to touch; it does not bound
**what content within those files** the worker is permitted to
commit. The race was won because:

1. ADR-021 D5's pre-claim `_check_scope_collision`
   (`src/will/autonomy/proposal_executor.py:64–130`) is a snapshot
   guard. It reads `git status --porcelain` at time T and yields if
   the snapshot's dirty paths intersect scope.
2. Action execution and `commit_paths` happen at T + ε with no
   recheck. The snapshot is assumed to remain authoritative for the
   duration of action execution.
3. A 60-second worker cycle hitting a brief clean-tree window in a
   `git stash`/`git stash pop` dance is a small-probability event
   per cycle and a high-probability event over many retries. After
   five yields, the sixth hit the window.

The promise ADR-021 kept was about **file selection**. The promise
that was missing was about **diff content**. A file that is
legitimately in scope at pre-claim can carry contamination from any
source — human commit dance, second worker on a parallel scope,
ruff version drift, editor auto-save — between pre-claim and commit,
and the executor has no mechanism to detect that the diff it is
about to project no longer matches the action it is executing.

### The shape of the gap, stated in ADR-070's terms

ADR-070 establishes that for every (source-of-truth, derived
projection) pair, divergence must be observable through the
audit/finding/remediation channels and bounded by a constitutional
value declared in `.intent/`. The pairs inventoried in ADR-070 D2
are on-disk-source → DB/Qdrant projections.

A proposal-execution event is the same shape on a different
surface. The **source** is the proposal: scope, action,
parameters, declared intent. The **projection** is the commit:
the actual diff applied to the working tree under the proposal's
attribution. Today this pair is not in ADR-070's inventory and
has no coherence mechanism. Divergence between proposal intent
("format this file") and commit content ("116 lines of new
enforcement code") is undetected at the boundary that should
enforce it. The b11f4dba incident is the first observed instance;
the class is the gap.

### Three alternative fixes considered and rejected

1. **Working-tree lease (cognate of ADR-069).** A
   constitutionally-declared lock acquired by the architect before
   any multi-step commit sequence; workers refuse to claim while
   the lock is held. Solves the cross-actor exclusivity question
   in the abstract but depends on the architect remembering to
   acquire the lock on every commit dance. Does not address
   contamination from non-architect sources (parallel worker on a
   shared scope, editor auto-save, future automation). The lock
   is also expensive on architect ergonomics: every `git stash` or
   complex add/restore sequence becomes preceded and followed by
   lock-management ceremony, with the daemon idling whenever the
   lock is held. Defers the question rather than answering it.

2. **Pre-commit re-check of dirty-tree intersection.** Run
   `_check_scope_collision` a second time, immediately before
   `commit_paths`. Cheap, plugs *this* specific race window, but
   TOCTOU-shaped at its core — a stash dance happening during the
   re-check itself could still beat it. Reduces the race window
   without eliminating it. Useful as defense-in-depth, insufficient
   as primary defense.

3. **Stash isolation.** Worker stashes everything not in
   `scope.files`, runs action against a known-clean baseline,
   commits, pops the stash. Strongest isolation; highest
   implementation cost; risk of stash/pop conflicts with
   architect-side stash use; introduces a hidden state that
   debug tooling does not expect.

The directional answer this ADR proposes — verify that the diff
the action produces is the diff the action was *authorized* to
produce — is more work than any of the three, and addresses the
class rather than the incident.

---

## Decisions

### D1 — Action diff coherence is a constitutional requirement

For every atomic action that mutates source files
(`ActionImpact.WRITE_CODE`, `ActionImpact.WRITE_METADATA`, and any
future write-bearing impact), the diff produced by the action
against each scope file MUST equal the diff the action was
authorized to produce, as defined by the action's declared
coherence predicate. A diff that fails its predicate is a
constitutional violation; the executor rolls back the action,
marks the proposal yielded with reason `diff_predicate_violation`,
and posts a finding on the
`autonomy.yielded.diff_predicate_violation` subject.

This is ADR-070's source–projection coherence principle applied
to the (proposal, commit) pair. The proposal is the source; the
commit is its projection; coherence is bounded by the action's
declared predicate; violation is observable through the
audit/finding channels.

This decision establishes the property. D2–D7 specify how it is
defined, declared, verified, and made operational.

---

### D2 — Coherence predicate vocabulary: two kinds, declared per action

A coherence predicate is a constitutional declaration of what
shape of diff an action is permitted to produce on its scope
files. Two predicate kinds are defined:

#### D2.1 — Reproducibility predicate

> For scope file F, the working-tree content of F after action
> execution MUST equal the result of applying the action's
> reference tool to F's content at the pre-execution SHA (D5).

For deterministic-tool actions, this is the strongest available
predicate. It sidesteps the trap of enumerating which
transformations the tool is permitted to make (quote
normalization, blank-line management, trailing commas, string
concatenation, etc.) — the answer is *whatever the tool
produces on the un-edited reference*. The predicate inherits
the tool's entire behaviour surface for free and remains stable
across tool version changes because the comparison is against
what the tool actually produces in this version.

Applied to the b11f4dba race: `ruff format(HEAD:violation_executor.py)`
on the un-edited HEAD content produces format-only changes.
The working-tree content at commit time was
`ruff format(HEAD:violation_executor.py + 116 unstaged lines)` —
not equal to the reproducibility reference. Predicate fails;
roll back; the contaminated commit never lands.

Actions adopting this predicate at the time of the migration:

| Action | Reference tool | Reference invocation |
|---|---|---|
| `fix.format` | `ruff format` | `ruff format --stdin-filename=<F>` against HEAD content |
| `fix.imports` | `ruff check --select I --fix` | Same shape, isort rules only |
| `fix.headers` | `header_service.fix_headers_internal` | Pure-function call on HEAD content |
| `fix.docstrings` | `docstring_service` (deterministic codemod) | Pure-function call on HEAD content |
| `fix.purge_legacy_tags` | tag-purge codemod | Pure-function call on HEAD content |
| `fix.policy_ids` | policy-id codemod | Pure-function call on HEAD content |

#### D2.2 — Structural predicate

> For scope file F, the diff between the pre-execution SHA's
> content of F and the working-tree content of F after action
> execution MUST consist exclusively of changes matching the
> action's declared structural shape.

For actions whose output is correct-by-construction but not
deterministic (UUID insertion, timestamp insertion), reproducibility
cannot be tested by byte equality. The structural predicate
specifies the allowed diff shape in AST/regex terms.

Actions adopting this predicate at the time of the migration:

| Action | Structural shape |
|---|---|
| `fix.ids` | Diff consists only of insertions of lines matching `^(\s*)# ID: [0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$`, each immediately preceding a line matching the canonical class-or-def line regex |
| `fix.duplicate_ids` | Same shape as `fix.ids` but on *replacement* lines: existing `# ID: <uuid>` comments where the UUID is one of the duplicate set, replaced with a fresh UUID-v4 |
| `fix.capability_tagging` | Diff consists only of insertions/modifications of `# capability:` decorator lines from the constitutional capability vocabulary |

Structural predicates are stricter to author than reproducibility
predicates and accept a higher false-positive risk against edge
cases the regex does not anticipate. They are used only where
reproducibility is genuinely not available. Reproducibility is
the default; structural is the exception.

#### D2.3 — Out of scope for this ADR

Actions with `ActionImpact.WRITE_DATA` (DB writes), `WRITE_CONFIG`
(config-only writes), and infrastructure actions
(`sync.db`, `sync.vectors.*`, `claim.proposal`) are out of scope.
This ADR addresses source-file mutation only. Coherence at the DB
and vector layers is ADR-070's remit; this ADR is the
proposal-execution surface specifically.

A third predicate kind (**tool-attested**: "the tool produces a
verification token alongside its output, and the executor checks
the token") is considered and deferred. No current `fix.*` action
emits such a token, and the surface for adopting one would require
tool-side cooperation; reproducibility and structural together
cover the migration set.

---

### D3 — Per-action declaration; no runtime fallback

Every action registered via `@register_action` and bearing
`ActionImpact.WRITE_CODE` or `ActionImpact.WRITE_METADATA` MUST
declare a `coherence_predicate` field. The field is required;
there is no runtime fallback.

```python
@register_action(
    action_id="fix.format",
    description="Format code with ruff format and ruff check",
    category=ActionCategory.FIX,
    policies=["rules/code/purity"],
    remediates=["style.formatter_required"],
    coherence_predicate=ReproducibilityPredicate(
        reference_tool="ruff_format",
    ),
)
```

Missing declaration on a write-bearing action MUST cause the
action registry to refuse to register the action at daemon
startup. This is cognate with ADR-069 D3's `lease_seconds`
no-runtime-fallback rule and ADR-070 D8's
`files_per_cycle_max` rule: the predicate is a governance
decision belonging to the action declaration, not a code-level
default. Each action explicitly considers its own coherence
bound rather than inheriting an unexamined global.

The registry's existing constitutional-compliance check
(`src/body/atomic/registry.py`) is extended to verify
predicate-presence at registration. The check runs once at
daemon startup and once at `core-admin check atomic-actions`
invocation.

`ActionCategory.READ`-impact actions and infrastructure actions
listed in D2.3 declare `coherence_predicate=None` explicitly.
The registry accepts the explicit None; what it refuses is
absence of the field on write-bearing actions.

---

### D4 — Verification placement: after action, before commit

The coherence check runs in `ProposalExecutor.execute`
(`src/will/autonomy/proposal_executor.py:133`) between the
action-result handling block (currently ending at line 314) and
the `commit_proposal_changes` invocation (currently line 330).

```python
# After action execution, before commit:
if write and all_ok:
    coherence_result = await verify_action_coherence(
        scope_files=proposal.scope.files,
        action_results=action_results,
        pre_execution_sha=pre_execution_sha,
        git_service=self.core_context.git_service,
    )
    if not coherence_result.ok:
        # Roll back the working tree to pre_execution_sha for scope files
        rollback_proposal(
            git_service=self.core_context.git_service,
            proposal_id=proposal.proposal_id,
            scope_files=proposal.scope.files,
            pre_sha=pre_execution_sha,
        )
        await state_manager.mark_yielded(
            proposal.proposal_id,
            yield_reason="diff_predicate_violation",
            details=coherence_result.violations,
        )
        return {
            "ok": False,
            "yielded": True,
            "yield_reason": "diff_predicate_violation",
            "violations": coherence_result.violations,
            ...
        }
    # only now:
    commit_proposal_changes(...)
```

The verification function lives in
`src/will/autonomy/proposal_execution_pipeline.py` as
`verify_action_coherence`, alongside the other pipeline-stage
helpers. The function reads each scope file's pre-execution
content via `git show <pre_sha>:<path>` (D5), invokes the
declared predicate for each action in `action_results`, and
returns a structured result with the per-file verdict and
violations.

**The check is the gate, not the action.** Actions execute as
they do today; they are not modified to self-verify. The
executor is the boundary that refuses to project an incoherent
diff. This keeps actions ignorant of the predicate framework
and concentrates the enforcement at the single point where it
matters — the moment before the commit lands.

---

### D5 — Reference-input source: pre-execution SHA, not HEAD

The reference input for both predicate kinds is the file's
content at the `pre_execution_sha` captured by
`capture_git_sha(phase="pre")`
(`src/will/autonomy/proposal_execution_pipeline.py:29`), not
the current HEAD.

`pre_execution_sha` is captured immediately before any action
runs (`src/will/autonomy/proposal_executor.py:220`) and is
already used by the rollback path to restore the working tree
on action failure. Using the same SHA as the predicate
reference makes the "what was the action authorized to
modify" question and the "what does the executor roll back to
on failure" question share a single answer.

Using HEAD instead would fail in the (rare but real) case
where HEAD advances between proposal creation and execution —
e.g., the architect commits an unrelated file while the
proposal is in the approved queue. In that scenario, HEAD's
version of the scope file may already differ from what the
proposal was created against, and the predicate would compare
against an unintended baseline. `pre_execution_sha` is HEAD
at the moment the executor took over — the executor's
view of "the starting state of this execution" — and is the
correct reference.

This decision implies that proposals do not need to carry their
own `created_at_sha`. The executor's pre-execution SHA is
authoritative for the duration of the execution. Proposals
that have been approved but not yet executed do not promise a
coherence baseline against any specific SHA; they promise
coherence against whatever SHA the executor sees when it
begins.

---

### D6 — Edge cases: idempotence, encoding, multi-action proposals

#### D6.1 — Tool idempotence is a declared invariant

The reproducibility predicate assumes
`tool(tool(X)) == tool(X)` — the tool is idempotent on its own
output. Ruff documents this; most deterministic formatters do.
If a tool ever produces a different output on a second pass,
the predicate will false-positive on the action's *own* legitimate
output the second time the action runs against the same content.

The ADR declares idempotence as a required invariant for any tool
adopted as a reproducibility reference. Verification of the
invariant runs at `core-admin check atomic-actions` invocation,
not at daemon startup. The CLI command runs the reference tool
against an action-specific corpus committed under
`tests/coherence_corpora/<action_id>/` and asserts
`tool(tool(X)) == tool(X)` after the canonical normalization of
D6.2 for each corpus file. A failed corpus check exits non-zero
so CI gates can refuse to deploy.

Verification is deliberately not run at registry load time.
Reference tools (e.g., `ruff`) are runtime dependencies that may
legitimately be absent during early bootstrap, container
construction, or the brief window between coordinated dependency
upgrades. A registration-time corpus check would conflate "tool
not installed" with "tool produces non-idempotent output" — two
genuinely different failure modes — and would make daemon
startup brittle on a check whose constitutional purpose is
satisfied earlier in the pipeline. Daemon startup logs a single
INFO line per reproducibility-bearing action indicating that the
predicate is declared and corpus verification is deferred to the
CLI gate.

The constitutional guarantee — that no non-idempotent tool is used
as a reproducibility reference — is preserved by the CI contract:
the deployment pipeline runs `core-admin check atomic-actions`
before any release shipping changes to atomic actions or their
reference tools. Production deployments that bypass the gate are
themselves a constitutional violation tracked elsewhere (out of
scope for this ADR).

If a reference tool is discovered to be non-idempotent in
production (e.g., a future ruff version regresses), the action
transitions to DEGRADED state until the tool is fixed or the
predicate is re-evaluated. Adding a DEGRADED-action mechanism is
out of scope for this ADR; the CLI gate plus CI contract is
sufficient for the current toolchain.

#### D6.2 — Encoding normalization

Byte equality is sensitive to line endings, BOM, and trailing
newline policy. The predicate normalizes both sides before
comparison:

- Line endings: convert all `\r\n` and `\r` to `\n` before
  comparison.
- BOM: strip leading `﻿` if present.
- Trailing newline: require exactly one trailing `\n` on both
  sides; add or strip as needed to canonicalize.

This normalization mirrors what ruff itself does and what the
file_handler write path produces. The ADR declares these as the
canonical normalization; predicate authors do not get to pick
their own.

#### D6.3 — Multi-action proposals

Today's `fix.*` proposals contain a single action. The ADR
specifies the single-action case fully. For multi-action
proposals (e.g., `fix.imports` then `fix.format` on the same
file), each action's reference input is the *output of the
previous action*, not `pre_execution_sha`. The verification
function processes actions in `order`, threading the post-action
content through as the next action's reference input.

The b11f4dba race involved a single-action proposal; the
multi-action case is not load-bearing for closing this incident
but the ADR specifies it for completeness so future composite
proposals do not introduce a coherence regression.

---

### D7 — Failure semantics: yield, do not fail

A coherence-predicate violation is a **yield** outcome, not a
**failure** outcome. The distinction matters because:

- A failed proposal is a proposal whose actions did what they were
  asked to do, and the result is wrong. The audit trail records the
  action's failure mode and the proposal is closed as
  `failed`/`rejected`. Re-running it without changes will fail
  again.
- A yielded proposal is a proposal that *could not run safely* in
  the current world-state but is not itself broken. The proposal
  remains `approved`; the next worker cycle will retry; if the
  contaminating condition has cleared, the next attempt may
  succeed.

A coherence violation is the second case: the proposal's intent
is sound and the action ran successfully in isolation; the working
tree contained content the action was not authorized to commit.
Re-running after the contamination clears (architect commits or
discards the contaminating edits) is the right response.

`ProposalStateManager` gains a `mark_yielded` method analogous to
the existing scope-collision yield path
(`src/will/workers/proposal_consumer_worker.py:132–149`). The new
yield reason `diff_predicate_violation` joins the existing
`scope_collision` and `any_dirty` reasons in the consumer worker's
post-handler.

A `autonomy.yielded.diff_predicate_violation::<proposal_id>`
finding is posted to the blackboard with payload:

```yaml
proposal_id: <uuid>
yield_reason: diff_predicate_violation
violations:
  - scope_file: src/will/workers/violation_executor.py
    predicate_kind: reproducibility
    reference_tool: ruff_format
    expected_diff_lines: 4
    actual_diff_lines: 120
    unexpected_lines_sample: [...]  # bounded sample for operator inspection
```

The sample is bounded by `_UNEXPECTED_LINES_SAMPLE_SIZE = 20`
(payload-shaping constant, same pattern as ADR-070 D8's
`_REAP_SAMPLE_SIZE`). The finding is single-instance per proposal —
the duplicate-suppression pattern at
`src/will/workers/proposal_consumer_effects.py:151` extends to
the new subject.

The architect's response options on a `diff_predicate_violation`
finding are:

1. Commit or discard the contaminating edits, then wait for the
   next worker cycle to retry. (Expected response in 90%+ of cases.)
2. Manually inspect the finding's `unexpected_lines_sample`, decide
   whether the diff was actually contamination or a tool bug,
   and either fix the tool / predicate or reject the proposal
   with appropriate audit trail.

---

### D8 — Implementation order

The migration is one unit, applied in this order:

1. **Predicate framework** in `src/shared/coherence/predicates.py`
   (new module): `CoherencePredicate` base, `ReproducibilityPredicate`,
   `StructuralPredicate`, the verification entrypoint.
2. **Registry extension** in `src/body/atomic/registry.py`:
   `register_action` accepts `coherence_predicate`; daemon-startup
   constitutional-compliance check verifies presence on write-bearing
   actions.
3. **Per-action declarations** added to every existing
   `WRITE_CODE` / `WRITE_METADATA` action in
   `src/body/atomic/fix_actions.py` and adjacent modules per D2's
   adoption table.
4. **Coherence corpora** committed under
   `tests/coherence_corpora/<action_id>/` (D6.1 idempotence
   verification).
5. **Verification gate** in `src/will/autonomy/proposal_executor.py`
   and `proposal_execution_pipeline.py` per D4.
6. **Yield surface** in `ProposalStateManager`,
   `proposal_consumer_worker`, `proposal_consumer_effects` per D7.
7. **`META/atomic_action.schema.json`** extended to require
   `coherence_predicate` on write-bearing actions; `intent_validator`
   enforces presence on next daemon startup.

Steps 1–4 can land without affecting runtime behaviour (registry
accepts predicates, but the executor does not yet consult them).
Step 5 is the cutover; the daemon must be restarted to pick it up.
Steps 6–7 are observability and validation tightening; they can
land in the same change-set as 5 or follow.

The daemon stays off until step 5 lands. The b11f4dba race remains
possible — at vanishing probability under normal use — until then.

---

## State at ADR acceptance

At the time this ADR is accepted, the following is the live state:

- The b11f4dba commit is in the audit trail. The 81631145
  postmortem records the attribution race. No corrective amend
  or revert is proposed; the audit trail captures the truth.
- The core-daemon has been stopped since 2026-05-24 10:28:11
  CEST. The pause is the architect's response to the race; the
  daemon stays off until the ADR-071 enforcement gate (step 5
  above) lands.
- ADR-021 D5's pre-claim collision check continues to operate
  as-is. ADR-071 does not modify it; the pre-claim check is
  retained as defense-in-depth (reduces predicate-violation
  yield rate by catching the easy cases earlier).
- No action declares a `coherence_predicate`. The
  `@register_action` decorator does not accept the parameter.
  The registry does not check for it.
- `verify_action_coherence` does not exist.
- `ProposalStateManager.mark_yielded` does not exist; today's
  scope-collision yields go through the consumer worker's direct
  post-handler, not through a state-manager method.
- The two declared-only rules from the 2026-05-24 ADR-070 D8
  work (`coherence.repo_artifacts.drift`,
  `coherence.violation_executor.blast_bound`) remain unmapped
  per ADR-066. They are unrelated to this ADR but worth noting
  as adjacent governance debt to clear in the same hardening
  pass.

---

## Consequences

**Positive:**

- The b11f4dba race class is closed at the constitutional layer.
  No future race window (between pre-claim check and commit) can
  result in an autonomous commit containing unauthorized content,
  regardless of the contamination source.
- ADR-021 D5's pre-claim check graduates from "the defense" to
  "the early-yield optimization." Predicate violations become
  rare (only when the working tree is contaminated *during*
  action execution itself); scope-collision yields become the
  normal liveness-preserving response to architect activity.
- The (proposal, commit) pair joins ADR-070's coherence
  inventory. The pattern of "source declares intent, projection
  is verified to match" extends from the on-disk-source layer
  to the action-execution layer with consistent vocabulary
  (predicate, verification, yield).
- Action authors gain a small but real local check: their
  registered predicate documents what shape of diff their action
  is supposed to produce. Newcomers reading
  `fix_actions.py` can see the action's purpose declared
  alongside its impact and policies.
- Future action additions inherit the gate for free. A new
  `fix.foo` registered without a predicate fails to register —
  the constitutional gap is impossible to introduce.
- Audit-trail integrity is strengthened. Every commit landed by
  the executor carries an implicit guarantee that its diff
  satisfied the declared predicate at landing time. GxP / EU
  AI Act traceability gains a constitutional bound on what an
  autonomous attribution can include.

**Negative:**

- Every existing write-bearing `fix.*` action must be touched in
  the migration to add a `coherence_predicate` declaration. The
  count is small (~10 actions) but the change is in code that
  has been stable for some time; the migration commit is broad.
- Reproducibility verification adds a per-scope-file overhead at
  commit time. For `fix.format` the overhead is one in-process
  ruff invocation against HEAD content per file — measured in
  tens of milliseconds. Negligible at current proposal volumes;
  worth measuring at scale.
- The idempotence corpus (D6.1) is a new artifact class that
  requires maintenance. Drift between corpus content and
  real-world inputs could leave a non-idempotent tool regression
  undetected. The corpora are small and the verification fast,
  so the maintenance cost is bounded — but real.
- Predicate authoring is a new skill the project must develop.
  Adopting reproducibility for an action is mechanical; adopting
  structural for a new non-deterministic action is design work
  that ADR-071 does not pre-solve.
- Tool-version dependency becomes a constitutional dependency.
  A ruff release that changes formatting output is no longer
  just an aesthetic change — it shifts the reference point of
  every `ReproducibilityPredicate` using ruff. The ADR does
  not require pinning ruff to a specific version, but it does
  imply that tool-version updates need to be considered as
  governance events.

---

## Verification

Deferred to implementation. At implementation, verification is:

1. `src/shared/coherence/predicates.py` exists, exporting
   `CoherencePredicate`, `ReproducibilityPredicate`,
   `StructuralPredicate`. Each predicate class exposes a
   `verify(scope_file: str, reference_content: str,
   working_content: str) -> CoherenceVerdict` method.
2. `@register_action` accepts a `coherence_predicate: CoherencePredicate
   | None` parameter. The registry stores the value alongside
   the existing action metadata.
3. Daemon startup constitutional-compliance check refuses to
   register any `WRITE_CODE` or `WRITE_METADATA` action whose
   `coherence_predicate` is unset. Verified by removing the
   predicate from one such action in a smoke test and
   confirming registration failure.
4. Every existing write-bearing action in
   `src/body/atomic/fix_actions.py` declares a
   `coherence_predicate`. The adoption matches D2.1 / D2.2's
   table. Grep for `@register_action` with `ActionImpact.WRITE_*`
   and confirm a corresponding `coherence_predicate=` line.
5. `tests/coherence_corpora/<action_id>/` exists for every
   reproducibility-predicate action; each contains at least one
   representative input file. Registry load runs each tool
   against each corpus file and asserts `tool(tool(X)) == tool(X)`
   (after the canonical normalization of D6.2).
6. `verify_action_coherence` in `proposal_execution_pipeline.py`
   exists, accepts `(scope_files, action_results,
   pre_execution_sha, git_service)`, and returns a structured
   `CoherenceResult` with per-file verdicts.
7. `ProposalExecutor.execute` calls `verify_action_coherence`
   between the action loop and `commit_proposal_changes`. On
   failure, it calls `rollback_proposal` and `mark_yielded`
   with `yield_reason="diff_predicate_violation"`; the commit
   never runs.
8. `ProposalStateManager.mark_yielded` exists and updates the
   proposal's status to yield-state with the given
   `yield_reason` and details payload.
9. `proposal_consumer_worker` recognizes `diff_predicate_violation`
   as a yield reason alongside the existing `scope_collision`
   and `any_dirty` reasons; `proposal_consumer_effects` posts
   the finding on
   `autonomy.yielded.diff_predicate_violation::<proposal_id>`
   with the schema specified in D7.
10. `META/atomic_action.schema.json` marks
    `coherence_predicate` required for write-bearing actions;
    `intent_validator` refuses any action manifest that omits it.
11. Unit test for `verify_action_coherence` exercising the b11f4dba
    race shape. Inputs constructed in the test, not derived from a
    running proposal:
    a. `scope_files=['src/will/workers/violation_executor.py']`.
    b. `action_results` populated with a single `fix.format` entry
       (`ok=True`, `data={'formatted': True, 'write': True}`).
    c. A temp git repository whose HEAD blob for the scope file is
       a small known-unformatted Python snippet (committed in the
       test fixture).
    d. A working-tree blob for the scope file containing the
       ruff-formatted version of the HEAD snippet plus ~50 lines of
       unrelated substantive Python (the analogue of the 116-line
       architect edit).
    e. Assert: `verify_action_coherence(...)` returns
       `CoherenceResult(ok=False)`; the violation cites
       `predicate_kind='reproducibility'` and `reference_tool='ruff_format'`;
       the named scope file matches; the actual-diff line-count
       materially exceeds the ruff-formatted-reference-diff line-count.

    This test exercises the gate in isolation. End-to-end coverage
    of `ProposalExecutor.execute` calling the gate is added to the
    existing executor integration-test module; no new test
    infrastructure is required for the unit test.
12. Existing `fix.format` happy-path test continues to pass —
    a clean working tree with a legitimately format-broken scope
    file results in a commit identical to today's behaviour,
    because the predicate is satisfied.
13. Issue tracking the implementation work exists and is closed
    by the implementing commit. ADR-071 status updated from
    `Proposed` to `Accepted` at acceptance time; updated to a
    third state (`Implemented`?) when step 5 of D8 lands and
    the daemon resumes.

---

## References

- ADR-021 — Scoped Autonomous Git Operations: D2/D3 establish the
  file-scope binding that this ADR extends to content-scope; D5
  establishes the pre-claim collision check that this ADR retains
  as defense-in-depth.
- ADR-069 — Claim Lifecycle Lease Semantics: cognate pattern; D3's
  "no runtime fallback, declaration is the single source of truth"
  rule is reused for `coherence_predicate` in this ADR's D3.
- ADR-070 — Source–Projection Coherence as Bounded Drift: the
  parent principle. This ADR is its application to the
  action-execution surface; the (proposal, commit) pair is the
  same shape as ADR-070 D2's on-disk-source → projection pairs.
- ADR-066 — Unmapped Rules Invariant: every active rule has an
  auto-remediation mapping. The new `diff_predicate_violation`
  yield reason posts a finding; if a future rule is added for this
  subject it will inherit the invariant.
- ADR-016 — Confidence Floor Enforcement: cognate posture (governance
  bounded in the model, not asserted by surveillance).
- `src/will/autonomy/proposal_executor.py:64–130` —
  `_check_scope_collision`, the pre-claim ADR-021 D5 check that this
  ADR retains and complements.
- `src/will/autonomy/proposal_executor.py:133–404` —
  `ProposalExecutor.execute`, the orchestrator into which D4's
  verification gate is inserted.
- `src/will/autonomy/proposal_execution_pipeline.py:208–243` —
  `commit_proposal_changes`, the projection step whose coherence
  this ADR enforces.
- `src/will/autonomy/proposal_execution_pipeline.py:175–204` —
  `rollback_proposal`, reused as the failure path for predicate
  violations.
- `src/will/autonomy/proposal_execution_pipeline.py:29–60` —
  `capture_git_sha`, source of the `pre_execution_sha` that D5
  designates as the reference baseline.
- `src/body/atomic/fix_actions.py` — the action registrations that
  D8 step 3 amends to declare predicates.
- `src/body/atomic/registry.py` — `@register_action` and the
  constitutional-compliance check that D8 step 2 extends.
- `.intent/enforcement/config/autonomy_dirty_tree.yaml` — the
  policy file whose `intersection_only` mode was active during
  the b11f4dba race. Mode is not changed by this ADR; the
  pre-claim check it governs continues to operate as today.
- Commit `b11f4dba1f4f4254be37371d5004c30db611ca85` (2026-05-24
  10:25:45 CEST) — the autonomous commit that landed 116 lines
  of substantive code under `fix.format` attribution. Primary
  evidence for the gap.
- Commit `81631145` (2026-05-24 10:28:43 CEST) — the architect's
  postmortem "audit-trail honesty correction." Primary narrative
  source.
- Commit `f78b5c64` (2026-05-24 10:25:53 CEST) — the intended
  hardening commit whose unstaged content was absorbed by the
  race.
- Commit `0ed0e72c` (2026-05-24 10:25:30 CEST) — the staged
  governance commit whose `git stash`/`git stash pop` envelope
  created the clean-tree window the race exploited.
- 21 CFR Part 11 §11.50 — electronic signature meaning. An
  autonomous commit's attribution implies the system claims the
  diff is the action's authorized output. Without the coherence
  predicate, that claim is unverifiable; with it, the claim is
  bounded by the declared predicate. Strengthens §11.50
  interpretability for autonomous-attribution commits.
- EU AI Act Article 17(1)(m) — accountability framework. The
  predicate makes the boundary of an autonomous action's
  permitted output explicit in the action declaration, satisfying
  the framework's requirement that accountability bounds be
  declared in the system's own governance artifacts.
