<!-- path: .specs/decisions/ADR-017-claim-proposal-as-atomic-action.md -->

# ADR-017 — `claim.proposal` as a governed atomic action

**Status:** Active
**Date:** 2026-04-28
**Authority:** Architectural
**Supersedes (in part):** ADR-015 D3 write-path prescription
**Preserves:** ADR-015 D3 column-shape decision; ADR-015 D7 forward-only enforcement

---

## 1. Context

ADR-015 D3 prescribed `claimed_by uuid` as a column on `core.autonomous_proposals`, populated by `ProposalStateManager.mark_executing()` in the same UPDATE that sets `status='executing'` and `execution_started_at`. The column-shape decision is sound and is preserved by this ADR. The write-path prescription — "populated by `mark_executing()`" — produced an architectural problem that was not visible at D3's authoring time.

Implementation under D3's prescription surfaced a fragmentation pattern. Threading `claimed_by` from `ProposalConsumerWorker.run()` through `ProposalExecutor.execute()` through `ProposalService.mark_executing()` to `ProposalStateManager.mark_executing()` produced six call sites all carrying a parameter that none of them had a semantic stake in. The CLI `execute_proposal` command became a fifth caller with no autonomous worker_uuid available to thread, requiring an arbitrary sentinel that had no constitutional grounding when raised on its own.

The deeper issue: CORE governs state mutations via atomic actions. `mark_executing` is a method on a state-manager class — it mutates persistent state on `core.autonomous_proposals` but is not a registered atomic action. The runtime check `verify_authorization(action_id)` does not fire on `mark_executing` calls; the state mutation is not visible to the governance token mechanism. Threading the parameter through the existing call chain preserved the mutation-without-governance shape.

The principle this ADR applies: state mutation belongs in atomic actions. The minimum proportional response to #147 is to make `claim` (the state transition that records `claimed_by`) into a governed atomic action. The other state transitions on the proposal lifecycle (`complete`, `fail`, `approve`, `reject`) remain methods on `ProposalStateManager` under this ADR; they are acknowledged as governance debt with a path forward but explicitly out of scope here.

**Scope discipline.** This ADR makes the smallest constitutional move that satisfies #147's attribution requirement. A larger refactor — the full proposal lifecycle as a coordinated set of governed atomic actions, with `ProposalExecutor` retired in favor of an orchestration action — was considered (variant b2 in the design discussion of 2026-04-28) and rejected for this ADR. The case for that larger refactor will accumulate from multiple state-transition needs over time and is its own future ADR. This ADR does not preempt that timing.

---

## 2. Decisions

### D1 — `claim.proposal` as a registered atomic action

A new atomic action `claim.proposal` is introduced. It lives in `src/body/atomic/proposal_lifecycle_actions.py` (new file). The file is named for the action family even though only one action lives there at the time of this ADR; the family name leaves the door open for future `complete.proposal` / `fail.proposal` / `approve.proposal` / `reject.proposal` actions without rename. The file is imported in `src/body/atomic/__init__.py` per the established registration-by-import convention.

The action declaration uses the standard two-decorator stack:

```python
@register_action(
    action_id="claim.proposal",
    description=(
        "Atomically claim an approved proposal for execution under "
        "worker attribution"
    ),
    category=ActionCategory.STATE,
    policies=["rules/will/autonomy"],
    impact_level="safe",
    requires_db=True,
    remediates=[],
)
@atomic_action(
    action_id="claim.proposal",
    intent="Atomically claim an approved proposal under worker attribution",
    impact=ActionImpact.WRITE_DATA,
    policies=["atomic_actions"],
)
async def action_claim_proposal(
    core_context: CoreContext,
    write: bool = False,
    proposal_id: str | None = None,
    claimed_by: UUID | None = None,
) -> ActionResult:
    ...
```

**Body shape.** The action does the UPDATE that was previously inside `ProposalStateManager.mark_executing` — sets `status='executing'`, `execution_started_at=NOW()`, `claimed_by=$claimed_by`, with the existing partial unique index `autonomous_proposals_executing_once` providing single-claim atomicity. Returns `ActionResult(ok=True, data={...})` on successful claim, `ActionResult(ok=False, data={"error": "already claimed or not approved"})` on `rowcount==0`. Parameter validation (missing `proposal_id` or `claimed_by`) returns `ActionResult(ok=False, ...)`.

**Behavior change vs. `mark_executing`.** The current `mark_executing` raises `RuntimeError` on `rowcount==0` after rolling back the session. The new `claim.proposal` returns `ActionResult(ok=False, ...)` instead. Callers (`ProposalExecutor.execute` / `execute_batch`) handle the failure case explicitly — see D3 — rather than catching an exception. This is a deliberate behavior change: action contracts return `ActionResult` rather than raise.

**`ActionCategory` extension.** A fifth value is added: `ActionCategory.STATE = "state"` (in `src/body/atomic/registry.py`). Stretching the existing `SYNC` value was considered and rejected — `SYNC` semantically means "reconcile derived state to source state" (e.g., vector indexes, DB sync), not "advance a state machine." Adding `STATE` is a one-enum-value contained change. No audit check or rule currently filters actions by category, so the addition does not require coordinated changes elsewhere.

**Policy reference is transitional.** The `policies=["rules/will/autonomy"]` reference satisfies `_validate_policies` (the document exists, the policy_id resolves) but `autonomy.json` does not currently contain a rule that directly governs proposal claim attribution. A dedicated `.intent/rules/will/proposal_lifecycle.json` is the right home for such a rule. Authoring it is **out of scope for this ADR** — it is filed as a Band D follow-up. Until that document lands, `rules/will/autonomy` is the closest existing policy.

### D2 — `ProposalStateManager` is reduced, not retired

`ProposalStateManager.mark_executing` is removed. The class retains:

- `mark_completed`
- `mark_failed`
- `approve` (with the ADR-015 D6 `approval_authority` validation logic intact)
- `reject`
- `with_session` (unchanged; raises `NotImplementedError`)

The module-level `ALLOWED_APPROVAL_AUTHORITIES` constant and its docstring are preserved — they support `approve()` and have no relationship to `mark_executing`.

This decision leaves a **bounded inconsistency**: `claim` is a governed atomic action; the other four state transitions are methods on a state-manager class. The inconsistency is acknowledged here as known governance debt rather than papered over. The path forward: when accumulated state-transition work surfaces additional attribution requirements (analogous to #147 driving claim), or when a clean batch refactor opportunity arises, a follow-up ADR migrates the remaining methods to atomic actions. This ADR does not preempt that timing.

**Why not retire `ProposalStateManager` outright in this ADR.** ADR-015 D6 just landed substantial validation logic in `approve()` (NFR.5 closed-set check on `approval_authority`). Migrating that to an action body within this ADR's scope would churn just-shipped governance work and expand discovery scope substantially. Per ADR-014's "loop liveness > productivity > quality during the development phase," shipping the smallest right step now is the correct posture. The larger lifecycle-as-actions migration is its own piece of work, decided when its case accumulates.

### D3 — `ProposalExecutor.execute` and `execute_batch` invoke `claim.proposal`

Both methods gain `claimed_by: UUID` as a required positional parameter, immediately after the proposal-id parameter and before the `write: bool = False` parameter. No default value — non-omittable per ADR-015 D3 / URS Q3.F.

Inside each method, the existing `await state_manager.mark_executing(proposal.proposal_id)` call is replaced with an action invocation:

```python
claim_result = await self.action_executor.execute(
    "claim.proposal",
    proposal_id=proposal.proposal_id,
    claimed_by=claimed_by,
    write=write,
)
if not claim_result.ok:
    return {
        "ok": False,
        "error": claim_result.data.get("error", "claim failed"),
        "proposal_id": proposal.proposal_id,
        "duration_sec": time.time() - start_time,
    }
```

The existing `state_manager = ProposalStateManager(session)` instantiation that currently sits inside `if write:` is moved or its scope narrowed: it remains for the eventual `mark_completed` / `mark_failed` calls in the success/failure branches (those state transitions stay on the state manager under D2). The claim transition no longer uses it.

**`ProposalExecutor.__init__` requires no new construction.** The class already constructs `ActionExecutor` (`self.action_executor = ActionExecutor(core_context)` at the top of `__init__`), so the `self.action_executor` reference in the new code is already available.

**Threading exists at exactly one boundary.** The caller of `ProposalExecutor.execute` / `execute_batch` provides `claimed_by`. There is no further propagation — the action invocation is the terminus. The six-layer threading pattern that the implementation under D3's original wording produced is reduced to a single-parameter pass-through at one method.

**`execute_batch` retains its current shape.** The session-reuse optimization (single session for the whole batch) is preserved. Worker iteration as a substitute for `execute_batch` is **not** prescribed by this ADR; that was a b2 design proposal and is rejected here.

### D4 — CLI claimer is a sentinel UUID constant

`core-admin proposals execute` (the CLI command at `src/cli/resources/proposals/manage.py`) cannot meaningfully provide a worker_uuid because the CLI is not a worker. Three options were considered:

1. `uuid.uuid4()` per invocation — provides no queryable attribution (no second occurrence to find).
2. Operator-derived UUID (e.g., from OS user) — adds complexity and semantic gaps.
3. Sentinel UUID — single stable value identifying "claimed by CLI."

**Option 3 is selected.** A module-level constant in `src/cli/resources/proposals/manage.py`:

```python
from typing import Final
from uuid import UUID

CLI_CLAIMER_UUID: Final[UUID] = UUID("00000000-0000-0000-0000-000000000001")
```

The value is arbitrary but stable and queryable: `SELECT * FROM core.autonomous_proposals WHERE claimed_by = '00000000-0000-0000-0000-000000000001'` returns all CLI-claimed proposals.

The principle: CLI is a distinct claimer-class, declared by sentinel value rather than synthesized per-call. This mirrors the ADR-015 D6 / NFR.5 pattern, where `approval_authority='human.cli_operator'` declares CLI as a distinct approval-class. The CLI sentinel UUID is the operational analogue at the claim layer.

**A future variant** (out of scope here): a registry of named claimer-classes, with the CLI's sentinel being one entry. Until other named claimer-classes appear, the single sentinel constant is sufficient.

### D5 — Relationship to ADR-015 D3

ADR-015 D3 is preserved unchanged in its **column-shape** decision: `claimed_by uuid` exists on `core.autonomous_proposals`; no `claimed_at` column (the existing `execution_started_at` serves the timestamp role); atomicity rides on the existing `autonomous_proposals_executing_once` unique constraint. ADR-015 D7 (forward-only enforcement; pre-D3 rows stay NULL; ALCOA+ "Complete") also unchanged.

D3's **write-path prescription** is amended:

- **Original wording:** "populated by `mark_executing()` in the same UPDATE that sets `status='executing'` and `execution_started_at`."
- **Amended wording:** "populated by the `claim.proposal` atomic action body in the same UPDATE that sets `status='executing'` and `execution_started_at`."

D3's named **Change sites** also amend:

- **Original:** `src/will/autonomy/proposal_state_manager.py:48-76` (mark_executing accepts `claimed_by: UUID` and writes it).
- **Amended:** `src/body/atomic/proposal_lifecycle_actions.py` (the `claim.proposal` action body) plus `src/will/autonomy/proposal_executor.py` (the action-invocation sites in both `execute` and `execute_batch`).

The atomicity guarantee is preserved. The unique constraint operates on the database row regardless of which Python code path issues the UPDATE.

---

## 3. Consequences

### Positive

- **Claim attribution is constitutional.** The state mutation is governed by the `@atomic_action` authorization mechanism. Calling `claim.proposal`'s underlying function outside `ActionExecutor.execute` raises `GovernanceBypassError`. Mutating `core.autonomous_proposals.claimed_by` outside the governed path is no longer reachable from in-tree code.
- **CLI claimer surface is resolved cleanly.** One sentinel constant at one site, with a clear queryable semantic ("CLI-claimed proposals").
- **Threading reduced from six call sites to one boundary.** The caller of `ProposalExecutor.execute` / `execute_batch` provides `claimed_by`. No further propagation. The fragmentation pattern that the original D3 wording produced does not survive.
- **Precedent established for future migrations.** When `complete`, `fail`, `approve`, `reject` migrate to atomic actions, they follow the shape established here. The `proposal_lifecycle_actions.py` family file is already in place to receive them.

### Negative

- **Inconsistent codebase.** `claim` is an action; four other state transitions remain methods on `ProposalStateManager`. Future readers will ask "why is this one an action and the others aren't?" The honest answer is "history" — `claim` was the first transition to require attribution; the others did not need restructuring at the same moment. The inconsistency is bounded and time-limited but real.
- **Quality work, not pure liveness.** ADR-014 endorses smallest-right-step. This ADR IS the smallest right step that is constitutionally honest, but claiming it is purely a liveness move would be dishonest. It is a quality investment that ADR-014 explicitly permits but does not mandate.
- **Loose policy reference.** The `policies=["rules/will/autonomy"]` reference satisfies `_validate_policies` but the `autonomy.json` document does not contain a rule that directly governs claim attribution. The connection is loose. A dedicated `rules/will/proposal_lifecycle.json` is the right resolution and is filed as Band D follow-up.

### Neutral

- **`execute_batch` preserved unchanged in structural shape.** Session-reuse optimization unchanged. b2's "drop execute_batch, worker iterates" proposal is rejected here.
- **One orphan flagged independently.** `src/body/atomic/remediate_cognitive_role.py` defines an action but is not imported in `src/body/atomic/__init__.py`. Per the registration-by-import convention, the action is not registered at runtime. This is independent of ADR-017's scope but worth flagging as a separate hygiene issue.

---

## 4. Implementation sequence (forward-only)

Each step is verifiable independently. The system is broken-on-import between steps 6 and 9 — coordinate as one commit or restrict to a single session.

1. **Restore working tree.** `git checkout 5d9a932d^ -- src/will/autonomy/proposal_state_manager.py src/will/autonomy/proposal_service.py src/will/autonomy/proposal_executor.py`. (Working tree currently has these in a session-intermediate broken state from the rollback.)
2. **Add `STATE` to `ActionCategory`** in `src/body/atomic/registry.py`.
3. **Create `src/body/atomic/proposal_lifecycle_actions.py`** with `action_claim_proposal` per D1.
4. **Update `src/body/atomic/__init__.py`** — add `from . import proposal_lifecycle_actions` to trigger registration.
5. **Remove `mark_executing` from `ProposalStateManager`** and remove the `from uuid import UUID` import in that file (no longer needed). The other four methods (`mark_completed`, `mark_failed`, `approve`, `reject`, plus `with_session`) and `ALLOWED_APPROVAL_AUTHORITIES` are preserved.
6. **Modify `ProposalExecutor.execute`** — add `claimed_by: UUID` parameter; replace the `state_manager.mark_executing(...)` call with the action invocation per D3. Add `from uuid import UUID` if not already present.
7. **Modify `ProposalExecutor.execute_batch`** — same shape as step 6 for the second call site.
8. **Modify `ProposalConsumerWorker.run()`** — pass `self.worker_uuid` as `claimed_by` when calling `ProposalExecutor.execute` / `execute_batch`.
9. **Modify `core-admin proposals execute` CLI command** — define `CLI_CLAIMER_UUID` constant per D4; pass it as `claimed_by`.
10. **Verify:**
    - `core-admin code audit` returns `PASSED`.
    - `systemctl --user restart core-daemon` succeeds; daemon reaches steady state.
    - URS Q3.F operational: given a `proposal_id` of a post-implementation autonomous proposal, the query `SELECT claimed_by FROM core.autonomous_proposals WHERE proposal_id = $1` returns a non-NULL worker UUID.
    - URS Q3.R operational: `SELECT proposal_id FROM core.autonomous_proposals WHERE claimed_by = $1` returns claimed proposals for a given worker UUID.
    - CLI-claimed proposals queryable by sentinel: `SELECT proposal_id FROM core.autonomous_proposals WHERE claimed_by = '00000000-0000-0000-0000-000000000001'` returns CLI-claimed proposals (if any have been issued via CLI in the verification window).

The `proposal_service.py` layer (the `ProposalService.mark_executing` wrapper) does not need modification under this ADR — `mark_executing` is removed from `ProposalStateManager` (D2), so any wrapper method delegating to it must also be removed, but `ProposalService.execute_workflow` becomes the only caller of the wrapper. Implementation should remove the `ProposalService.mark_executing` wrapper method and the `execute_workflow` reference to it; `execute_workflow` is a dormant convenience method (per the 591acfdb refactor's dead-code note) and updating it symmetrically follows the established posture.

---

## 5. References

**Issues:**
- [#110](../../issues/110) — Band B epic (consequence chain)
- [#147](../../issues/147) — Edge 3, claimed_by attribution (closed by this ADR's implementation)

**ADRs:**
- ADR-014 — loop liveness > productivity > quality during dev phase (compatibility argued in D2)
- ADR-015 — consequence chain attribution (D3 column shape preserved unchanged; D6/NFR.5 patterns mirrored for CLI claimer in D4; D7 forward-only enforcement preserved)
- ADR-016 — test environment architecture (D1 model registry as schema authority; AutonomousProposal model gains `claimed_by` independently of this ADR's write-path decisions)

**Plans and requirements:**
- `.specs/planning/CORE-A3-plan.md` — G3 closure depends on Edge 3 / #147
- `.specs/requirements/URS-consequence-chain.md` §3 Q3.F / Q3.R — read path verification

**Discovery sessions (this ADR's drafting, 2026-04-28):**
- Atomic action surface: reads of `src/body/atomic/registry.py`, `src/body/atomic/executor.py`, `src/shared/atomic_action.py`, `src/body/atomic/fix_actions.py` (representative action body)
- Policy and category vocabulary: reads of `src/body/atomic/registry.py` (ActionCategory enum), `.intent/rules/will/autonomy.json`, `src/body/atomic/` directory listing
- Caller surface: grep across `context_core.txt` for `ProposalExecutor`, `mark_executing`, `executor.execute`, `executor.execute_batch`

**Follow-up issues (filed against Band D — Engine Integrity):**
- Author dedicated `.intent/rules/will/proposal_lifecycle.json` policy document; migrate `claim.proposal` policy reference from `rules/will/autonomy` to the new document.
- `src/body/atomic/remediate_cognitive_role.py` orphan: investigate whether intentional dormancy or oversight in `__init__.py`; resolve.
- (Long horizon) Migrate `complete`, `fail`, `approve`, `reject` to atomic actions when the case accumulates; retire `ProposalStateManager`. This is a separate ADR, not a #147-shaped issue.
