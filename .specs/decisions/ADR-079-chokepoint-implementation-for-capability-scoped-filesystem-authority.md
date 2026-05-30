<!-- path: .specs/decisions/ADR-079-chokepoint-implementation-for-capability-scoped-filesystem-authority.md -->

# ADR-079 — Chokepoint Implementation for Capability-Scoped Filesystem Authority

**Date:** 2026-05-30
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (chokepoint-implementation session 2026-05-30)
**Grounding paper:** `papers/CORE-Capability-Scoped-Filesystem-Authority.md` §4 (chokepoint), §5 (capability-scoped least authority), §6 (mode dimension), §7 (capability identity at the chokepoint), §9 bullets 5 & 6 (the identity-propagation implementation and migration deferrals this ADR fulfills)
**Related:** ADR-077 (config-driven protected-namespace access; declares `filesystem_operations.yaml`, the call-name → op-class surface this ADR's chokepoint consumes for op-class derivation); ADR-078 (operational-capability taxonomy schema — D3, D4, D8, D10; declares `operational_capabilities.yaml`, the per-capability fs-profile surface this ADR's chokepoint consumes for authorization); Issue #492 (mode-provenance ADR — separate §9 deferral whose consumer contract this ADR specifies); Issue #495 (5 phantoms in `operational_capabilities.yaml` — this ADR specifies the resolution policy); Issue #494 (dead `is_metadata` variable at `intent_guard.py:368` — adjacent, out of scope here)

---

## Context

`papers/CORE-Capability-Scoped-Filesystem-Authority.md` (landed 2026-05-30, commit `8ed705a8`) defers six items to follow-on ADRs in §9. ADR-078 closed bullet 2 (the schema). This ADR closes bullets 5 and 6 — **the chokepoint's identity-propagation implementation and the migration path from today's `scope.excludes`-based perimeter to capability-keyed authorization**.

Three items remain explicitly deferred: the mode-flag startup mechanism and its provenance guarantees (#492 — this ADR specifies the consumer contract but not the source); the governor-token machinery that authorizes development-mode privileged writes (separate ADR); the full operational migration execution plan beyond the framing in D10 (issue-tracked, not ADR-resolved).

### Runtime surface inherited

Four pieces of infrastructure already exist and shape the design space:

- **`FileHandler` (`shared/infrastructure/storage/file_handler.py`)** is the de-facto write surface today. It is *nearly* singular but not strictly so — it carries 10 mutation methods (`write_runtime_text`, `write_runtime_bytes`, `write_validated_bytes`, `write_runtime_json`, `add_pending_write`, `ensure_dir`, `remove_file`, `remove_tree`, `copy_tree`, `copy_repo_snapshot`), one of which (`write_validated_bytes`) is an intentional IntentGuard bypass for ADR-071 D2.2 sandbox propagation. The mutation methods all route through `_guard_paths`, with the exception just noted. Outside `FileHandler`, ADR-077 has inventoried ~340 non-gateway filesystem call sites in `src/`; ADR-077 §6 governs their convergence under an advisory-then-blocking dial. This ADR assumes the ADR-077 convergence sequencing is the perimeter-completeness path; it does not relitigate it.

- **`IntentGuard` (`body/governance/intent_guard.py`)** is the policy-evaluation half. Today it takes `(proposed_paths, impact)` and returns a `ConstitutionalValidationResult`. It does **not** receive the calling capability — `impact` is the only piece of caller context, and the dead `is_metadata` variable at line 368 (#494) confirms that even `impact` has no live consumer in the rule evaluation path. The guard's three enforcement tiers (hard `.intent/` invariant, constitutional-authority rule denial, policy-authority advisory) are orthogonal to capability authorization; capability authorization is a new dimension on top, not a replacement for them.

- **`@atomic_action` (`shared/atomic_action.py`)** and **`shared.governance_token._executor_token`** already implement process-scoped action-identity propagation. `ActionExecutor.execute` wraps each dispatched action in `with authorize_execution(action_id):`, which sets `_executor_token` (a `contextvars.ContextVar[str | None]`) to the dispatched action's id. The token reflects the *dispatched* capability, not the dispatcher: when `action.execute` invokes `fix.format`, `_executor_token` holds `"fix.format"` for the duration of `fix.format`'s body. The `verify_authorization` companion at the atomic_action decoration boundary already enforces "no atomic action runs without a token, with the single root-authority exemption for `action.execute` itself."

  This is exactly the surface paper §7 calls for. The chokepoint identity-propagation implementation deferred in §9 bullet 5 is the *consumer* of `_executor_token`, not a parallel new mechanism. No new `ContextVar` is required.

- **`operational_capabilities.yaml` + loader (ADR-078)** provides the per-capability `fs_profile` data and a fail-closed loader at `shared/infrastructure/intent/operational_capabilities.py`. **`filesystem_operations.yaml` + loader (ADR-077)** provides the call-name → op-class mapping. The two together form the data-side of the chokepoint's decision; both exist or are scheduled to exist before this ADR's implementation begins.

### What is missing

The chokepoint today renders a decision on `(target_path)` plus a global hard invariant on `.intent/`. Paper §4 requires `(calling_capability, operation, target_path, current_mode)`. Three of the four inputs are not currently consulted:

- **calling_capability**: available in `_executor_token` at the moment of the write, never read.
- **operation**: implicit in the `FileHandler` method invoked; not exposed to the guard.
- **current_mode**: no accessor exists; no policy code reads a mode flag today.

The implementation gap is therefore three reads and a decision-rule extension — not new infrastructure. The migration's load is the policy semantics, the floor-block reshape (paper §8 amendment to `IntentGuard.md` §4 — the `.intent/` block becomes capability-mediated in dev), and the phantom-resolution change-set forced by ADR-078's "every YAML entry must be chokepoint-addressable" implication (#495).

### Constraints from prior decisions

Five existing decisions narrow the choice space:

- **Paper §7 deny-on-no-context.** A write with no capability identity is structurally a bypass and the chokepoint denies it. This forecloses any "default to permissive when token is None" relaxation, including for legacy call sites mid-migration.
- **Paper §6 default-on-uncertainty is live.** A missing or malformed mode signal collapses authority to live-mode-only entries. This forecloses any "best-effort dev mode" inference.
- **ADR-078 D8.** `file.*` primitives are the chokepoint itself, not capabilities, and the loader rejects any `^file\.` capability id. The chokepoint does not authorize itself against itself.
- **ADR-078 D9.** The taxonomy is the live-authorization surface, not the complete `@atomic_action` registry. A capability absent from the taxonomy is denied (it does not exist for authorization purposes); dormant-capability handling stays at the YAML edit boundary.
- **ADR-077 §6 sequencing.** The protected-namespace blocking dial is promoted only after the introspective completeness check ships green. This ADR's capability-mediated `.intent/` and `.specs/` writes inherit that gating: the chokepoint cannot grant a dev-mode `.intent/` write to a permitted capability while the audit-time backstop's coverage of the watched-set is unverified.

## Decisions

### D1 — Location: the chokepoint is `FileHandler.IntentGuard`, extended in place

The chokepoint is not a new class. It is the existing `FileHandler` write surface plus the `IntentGuard.check_transaction` policy method, extended with three new inputs (calling capability, op-class, mode) and one new decision tier.

**Why not a new class.** Paper §4: "there is one door, and the door is the only way out." The door already exists. ADR-077's ~340-site perimeter convergence is the property that makes the door singular; building a parallel class adds a second door before the perimeter closes the first.

**Surface shape after extension.** `FileHandler` mutation methods continue to call `_guard_paths(rel_paths, impact)`. `_guard_paths` is extended to also pass the op-class (derived per D3) and to read the calling capability from `_executor_token` (D2) and the current mode from the mode accessor (D4). `IntentGuard.check_transaction` gains a capability-tier evaluation between today's hard-invariant tier and constitutional-rule tier.

**No method-signature breaking changes** at the FileHandler public surface — `write_runtime_text(rel_path, content, impact)` retains its signature. The added inputs are read internally from context, not passed by callers. This is deliberate: requiring callers to pass capability identity would defeat the point of `_executor_token` propagation and re-introduce the discipline-not-structure failure mode paper §5 warns against.

### D2 — Capability identity propagation: reuse `_executor_token`

The chokepoint reads `shared.governance_token._executor_token` via a new public accessor:

```python
def current_capability() -> str | None:
    """Return the capability_id currently authorized by ActionExecutor, or None."""
```

This accessor lives in `shared/governance_token.py` next to `authorize_execution` and `verify_authorization`. No new `ContextVar`, no new push/pop semantics, no separate "capability context" parallel to the existing token context — the token *is* the capability identity from the moment ADR-078's taxonomy becomes the source of truth for what an `action_id` means.

The propagation semantics are unchanged from today:
- Nested `authorize_execution` calls produce a stack — the innermost-active capability is what `current_capability()` returns. This matches the dispatcher → dispatched semantics already exercised by `action.execute` calling `fix.format`.
- The `action.execute` root-authority exemption in `verify_authorization` is **not** mirrored in `current_capability()`. If the chokepoint reads `"action.execute"` as the calling capability, the policy-decision-table's lookup proceeds normally — `action.execute`'s `fs_profile` in `operational_capabilities.yaml` is currently empty for all four op-classes (the taxonomy as of 2026-05-30), so every write attributed to `action.execute` is denied. This is the correct behavior: a meta-dispatcher writing under its own identity, rather than the dispatched capability's, indicates a propagation bug.

A read of `None` from `current_capability()` is the §7 "no provenance" case. The chokepoint denies the write without consulting the taxonomy. The denial reason cites "no calling capability in context" rather than a specific rule violation; this is a distinct denial class from "capability X does not have authority on path Y" and surfaces propagation defects loudly rather than as silent misclassification.

### D3 — Operation-class derivation: FileHandler-method → op-class mapping, internal

The chokepoint needs an op-class for each path under decision. Three sources are possible: (a) infer from the FileHandler method name, (b) require callers to pass it, (c) read from `filesystem_operations.yaml`.

Decision: **(a), with internal mapping.** Each FileHandler mutation method has a stable, narrow op-class:

| FileHandler method | op-class |
|---|---|
| `write_runtime_text`, `write_runtime_bytes`, `write_runtime_json` | `modify` (or `create` if target absent) |
| `write_validated_bytes` | `modify` (or `create`) — but routed per D8 |
| `add_pending_write` | `create` (the pending-write file) |
| `ensure_dir` | `create` |
| `remove_file`, `remove_tree` | `delete` |
| `copy_tree`, `copy_repo_snapshot` | `create` (the destination) — source is a read, handled separately |

The mapping lives in `_guard_paths` as a small dispatch — not in `filesystem_operations.yaml`. **Rationale**: `filesystem_operations.yaml` (ADR-077) governs the *stdlib* call-name → op-class vocabulary for the audit-time perimeter check; the FileHandler methods are CORE's *internal* gateway and have no need to be governed as a public stdlib-shaped surface. Inlining the gateway mapping at the chokepoint avoids round-tripping every internal write through a YAML lookup for a method whose semantics are stable across the gateway's lifetime.

**The create-vs-modify distinction is resolved by filesystem existence at the moment of the call.** If the target path exists, the op-class is `modify`; if not, `create`. This is a stat call per path in the transaction, and it happens before the policy decision. The cost is acceptable (transactions are short-list, single-digit paths in practice; stat is cheap) and the alternative — requiring callers to declare intent — re-introduces discipline-not-structure.

**Delete + create-of-replacement is two op-classes**, not one. `remove_file` followed by `write_runtime_text` on the same path is two transactions, each independently authorized. The chokepoint does not collapse them.

**TOCTOU caveat on create-vs-modify resolution.** The stat-before-decide is a time-of-check/time-of-use race in principle: the file could be created or deleted between the stat and the write. Under CORE's current threat model — all writes originate from `@atomic_action`-decorated, in-process Python under one trust boundary — the race is benign. The op-class result swaps between `create` and `modify`; if a capability authorizes one but not the other on the same path, the misclassification could permit a write the policy intended to deny. No live capability in the 2026-05-30 taxonomy declares asymmetric create-vs-modify authority on overlapping patterns; the gap is theoretical until one does. A multi-tenant or external-write-source threat model would require revisiting this — either by collapsing `create`/`modify` to a single `write` op-class at the chokepoint, or by stat-after-acquire under a path lock.

### D4 — Mode-flag consumer contract (provenance deferred to #492)

The chokepoint reads the current mode via a single accessor:

```python
def current_mode() -> Literal["dev", "live"]:
    """Return the current operational mode. Defaults to 'live' on uncertainty (paper §6)."""
```

This accessor lives at `src/shared/infrastructure/intent/operational_mode.py`. Its implementation in this ADR's change-set is a **minimal placeholder**:

- Reads an environment variable `CORE_OPERATIONAL_MODE`.
- Accepts only the exact strings `"dev"` and `"live"`.
- Any other value (missing, empty, mistyped) returns `"live"` per paper §6's "default on uncertainty is *live*."
- Logs at INFO on first call with the resolved value and the source consulted (env var name or "default").

**The placeholder is explicitly inadequate for live deployment.** #492 is the ADR that will replace it with provenance-guaranteed source resolution (signed manifest, bootstrap config, conflict-resolution rules). This ADR's chokepoint depends on **the accessor's interface, not its implementation** — when #492 lands, the accessor's body changes and the chokepoint is unaffected. The placeholder is sufficient for the dev-mode-only operating premise the paper records in §3 and which #492 documents as the trigger condition.

**Mode is read once per `check_transaction` call**, not once per path. A transaction is mode-coherent — its paths are evaluated under one mode — and reading once preserves that property cheaply.

### D5 — The policy decision table

**Authorization scope: writes only.** This chokepoint authorizes mutation operations exclusively. The producible op-class set is `{create, modify, delete}`. The fourth op-class declared in ADR-078's `fs_operation_class` enum — `read` — is not produced by D3's FileHandler-method mapping (FileHandler has no generic read methods to guard), is not evaluated in this ADR's decision table, and is not blocked at runtime by this chokepoint. The `read:` lists carried by every entry in `operational_capabilities.yaml` are therefore forward-declarations of read authority that no runtime mechanism in this ADR enforces. They remain in the YAML for two reasons: ADR-078 D4 requires all four `fs_operation_class.values` as `fs_profile` keys (forcing absence to be a positive declaration), and a future read-authorization chokepoint will consume them without a schema migration. Read authorization of protected namespaces remains covered by ADR-077's audit-time `direct_intent_access` / protected-namespace-access check (advisory then blocking per ADR-077 §6) for the `.intent/` and `.specs/` namespaces. Read authorization of arbitrary paths is unenforced at runtime; that gap is recognized and accepted.

For each path in a transaction, the chokepoint executes the following decision sequence. The first matching branch yields the verdict:

1. **Repo-boundary check** (existing, unchanged). Path resolution that escapes the repo root → `DENY` (path-traversal violation). `FileHandler._resolve_repo_path` already enforces this; the chokepoint inherits it.

2. **Floor blocks** (existing, unchanged except `.intent/` per D7). `var/keys/`, `var/cache/`, absolute paths outside repo → `DENY`. These hold regardless of capability or mode (paper §8: "floor-level blocks that hold regardless of capability or mode").

3. **No capability in context.** `current_capability()` returns `None` → `DENY` with reason `chokepoint.no_capability_context` (paper §7).

4. **Unknown capability.** `current_capability()` returns a value not present in `operational_capabilities.yaml` → `DENY` with reason `chokepoint.unknown_capability`. The capability either was retired without removing the decoration, or was never declared.

5. **Operation-class not declared.** The capability is known, the op-class (D3) is one of `{create, modify, delete}`, and the capability's `fs_profile[op_class]` list is empty → `DENY` with reason `chokepoint.operation_not_authorized` and the rejected op-class in the message.

6. **No matching path pattern.** The `fs_profile[op_class]` list is non-empty but no entry's `path_pattern` matches the target path → `DENY` with reason `chokepoint.path_not_authorized`. The list of declared patterns is included in the message for debuggability.

7. **Mode-excluded pattern.** A pattern matches the path, but the entry's `modes` list does not include `current_mode()` → `DENY` with reason `chokepoint.mode_not_authorized`. The denied mode is named.

8. **Permit.** A pattern matches the path, and the entry's `modes` list includes `current_mode()` → `PERMIT`. The chokepoint proceeds to the next path (or returns success if this was the last).

**Multi-path semantics.** All paths must reach branch 8 for the transaction to permit. Any branch 1–7 hit denies the whole transaction. The denial reasons for each failing path are collected into the `ConstitutionalValidationResult.violations` list — preserving today's IntentGuard contract that a transaction's full failure surface is reported, not just the first miss.

**Path-pattern matching uses `shared.utils.glob_match.matches_glob`** — the same matcher IntentGuard uses today for its rule-pattern check. No new matcher. The taxonomy's `path_pattern` field shares syntax with `scope.excludes` patterns elsewhere in `.intent/` (ADR-078 D4).

**Constitutional-rule and policy-rule evaluation runs in parallel, not as an exclusive alternative.** A capability-permitted path may still trigger a constitutional-rule denial (e.g., a write that matches a vocabulary-protection rule). The two tiers stack: capability authorization is *necessary*, the existing rule evaluation is *also necessary*. A path is permitted only if both grant.

### D6 — Floor blocks preserved; capability tier inserted between hard-invariant and rule-eval tiers

`IntentGuard.check_transaction`'s tier order becomes:

1. Repo-boundary + DEGRADED pre-check (existing).
2. Floor blocks: `var/keys/`, `var/cache/`, etc. (existing — unchanged from IntentGuard.md §4 except `.intent/` per D7).
3. **NEW: Capability authorization** (D5 branches 3–8).
4. Constitutional-rule denial (existing tier 2).
5. Policy-rule denial, strict-mode-gated (existing tier 3).

Tiers 4 and 5 evaluate against today's rule set. Their decisions are independent of the capability tier — a capability-permitted write that violates a constitutional rule still fails (e.g., capability `fix.format` permits modifying `src/**/*.py`, but a vocabulary-projection rule may still reject specific content patterns). Convergence of the older `scope.excludes`-based rules into capability-keyed authority is a per-rule retirement decision, governed by D10's migration sequencing.

### D7 — `.intent/` and `.specs/` chokepoint behavior (paper §8 amendment realized)

Paper §8 already amends `CORE-IntentGuard.md` §4 to make the `.intent/` floor block mode-conditional. This ADR specifies the runtime behavior:

- **Live mode.** `.intent/` and `.specs/` are floor-blocked. No capability can write to them. The chokepoint evaluates D5's floor-block tier (branch 2) against an extended floor-set that includes `.intent/` and `.specs/` when `current_mode() == "live"`. This matches the paper's "absolute" framing for live mode.

- **Dev mode.** `.intent/` and `.specs/` are *not* in the floor set. The decision falls through to the capability tier (D5 branches 3–8). A capability with `.intent/**` or `.specs/**` in its `fs_profile[modify]` and `dev` in the entry's `modes` permits the write; everything else denies it. This is the path by which CORE amends itself through itself.

The floor-set computation is one branch on `current_mode()` at the start of `check_transaction`, not a per-path check. Mode is read once (D4) and the floor set is selected before path iteration begins.

**The existing `_READ_ONLY_RULE_ID` hard invariant on `.intent/` is retired** — but only at stage 4 of D10's migration, atomically with the capability tier becoming blocking for `.intent/`-writing capabilities. It is replaced by the floor-set extension above. The retirement and the replacement land in the same change-set: leaving both in place would produce a double-decision with conflicting semantics, and retiring the old one before the new one is enforcing would open a fail-open window. The atomic swap is the property that makes the migration safe.

**`.specs/` enters the chokepoint's scope here for the first time.** Today `.specs/` has no IntentGuard protection at all (covered only transitively by ADR-077's `no_direct_writes` once it promotes to blocking). The capability-tier evaluation in dev mode is the *only* sanctioned write path; the floor block in live mode is the *only* live-mode treatment. This is the extension paper §8 records.

### D8 — Sandbox propagation surface: `write_validated_bytes` is preserved as the sanctioned bypass

`FileHandler.write_validated_bytes` is today the explicit IntentGuard bypass used by `ActionExecutor._propagate_sandbox_changes` (ADR-071 D2.2). It does not call `_guard_paths`.

Two options were considered:

- **(a) Route propagation through the chokepoint** by re-establishing the dispatched action's `_executor_token` in the propagation step and routing the bytes through `write_runtime_bytes`. Clean conceptually, but the sandbox already validated under correct identity; re-validating in main is redundant and adds a second decision surface where the first one already passed.
- **(b) Keep `write_validated_bytes` as the sanctioned bypass**, documented as the chokepoint's single legitimate bypass, with the invariant that it is reachable only from `ActionExecutor._propagate_sandbox_changes`.

Decision: **(b)**, with two reinforcements landing in this ADR's change-set:

- A `regex_gate`-or-equivalent audit rule (`governance.chokepoint.write_validated_bytes_sole_caller`) verifies that the only call site of `write_validated_bytes` in `src/` is `body/atomic/executor.py:_propagate_sandbox_changes`. Any other call site is a finding.
- The method's docstring is updated to declare it as the **only** sanctioned IntentGuard bypass and to cite this ADR's invariant.

**Rationale for (b) over (a).** Option (a) requires re-establishing capability identity inside the propagation step, which means the propagation logic must capture and replay the dispatched action's identity — adding state and a re-entry into the token machinery, both of which are non-trivial to verify correct under nested-dispatch (e.g., `action.execute` invoking a chained action). The sandbox-validation already established the right identity inside the worktree; the propagation is byte-for-byte copy of already-validated content. The bypass is honest about that: the validation already happened, this step is just plumbing.

**Audit-time vs call-time enforcement caveat.** `write_validated_bytes` remains a public method on `FileHandler` after this change. The `governance.chokepoint.write_validated_bytes_sole_caller` rule is an *audit-time* backstop, not a call-time gate — one rogue call to it would execute its single byte-write before the audit cycle next runs and surfaces the finding. Under CORE's current threat model (governed `@atomic_action` callers, single trust boundary) the audit-time enforcement is sufficient: a non-sandbox-propagation call site would land in `src/` as a diff the governor reviews, and the audit fires on the same load cycle as the diff lands. Hardening to call-time would require either a private name (`_write_validated_bytes` plus stack-frame inspection) or a separate token check at the bypass — both add machinery for a threat shape that does not currently exist. The limitation is recognized; the chokepoint perimeter has one legitimate hole, audit-time-bounded.

### D9 — Phantom-resolution policy: every YAML entry must be chokepoint-addressable

The chokepoint's decision tree (D5 branches 3 and 4) requires that `current_capability()` return a value present in `operational_capabilities.yaml`. The five phantoms documented in #495 violate this in two distinct shapes:

**Shape 1: CLI-only capabilities (`secrets.set`, `secrets.get`, `secrets.list`, `secrets.delete`).** These are invoked via `@core_command`, which does not route through `ActionExecutor.execute` and therefore never sets `_executor_token`. They are DB-only — none of them invokes `FileHandler` at any point. **Resolution: strip from `operational_capabilities.yaml`.** They are not capabilities under the chokepoint model. Their risk classifications in `action_risk.yaml` remain unchanged (risk classification is a separate concern from chokepoint authorization). The fact that they cannot reach the chokepoint is the correct property — re-introducing them under #495 path (a) (decorate underlying functions) would add `@atomic_action` to functions that have no FS authority needs, just to silence a phantom-detection check.

**Shape 2: `test.execute`.** This shape's resolution is **not** simply decorating `run_tests` with `@atomic_action(action_id="test.execute")`. Per D2's mechanism, the capability identity token is set by `ActionExecutor.execute`'s `authorize_execution(action_id)`, **not** by the `@atomic_action` decorator — the decorator only *verifies* a token exists, it does not push the decorated function's `action_id` onto the stack. Today `test_system` (decorated `test.system`) reaches `run_tests` via a direct Python `await` (`audit.py:93`), not via the executor. Adding `@atomic_action(action_id="test.execute")` to `run_tests` would make it require a token — which it would have, set to `"test.system"` by the outer dispatch — but the token's *value* would stay `"test.system"` throughout `run_tests`' body. The chokepoint would still see `test.system` (empty fs_profile) as the calling capability and deny the writes. The phantom would remain.

**The correct resolution is a re-route through the executor.** Three changes land together:

1. `run_tests` (or a thin wrapper) is registered with `@register_action(action_id="test.execute")` so the executor's registry can dispatch it, decorated with `@atomic_action(action_id="test.execute")` per the dual-decorator convention, and its signature is extended to accept `**kwargs` (required by the atomic_action decoration-time check per issue #448 / ADR-070 D8 — `_prepare_params` forwards `write` and other executor-managed kwargs that `run_tests` does not currently accept).
2. `test_system`'s body changes from `return await run_tests()` to `return await core_context.action_executor.execute("test.execute")` (with `core_context` injected via `_prepare_params` per the existing executor convention).
3. The dispatch sets `_executor_token` to `"test.execute"` via `authorize_execution` for the duration of `run_tests`' body, producing the `[test.system → test.execute]` stack D2 assumes. `current_capability()` correctly returns `"test.execute"` to the chokepoint when FileHandler is invoked from inside `run_tests`.

Without all three, the phantom is not closed — decoration alone is insufficient because the decorator's contract is verification, not stacking. This is the load-bearing mechanism distinction that the inventory's "phantom" framing obscured.

**Standing invariant.** Going forward, the chokepoint requires that every capability id in `operational_capabilities.yaml` be backed by exactly one `@atomic_action` decoration in `src/`. The AST-walk sweep that found the #495 phantoms is promoted to an audit-time check (`governance.taxonomy.operational_capabilities_decorator_backing`) that fails on any YAML entry without a matching decorator. Adding a YAML entry without a matching decoration is therefore a load-time-detected, fail-closed defect rather than a silent runtime gap.

This invariant is the structural counterweight to ADR-078 D9's "dormant capabilities excluded": both directions are policed. A capability may be in the registry without being in the YAML (dormancy is tracked elsewhere), but a capability may **not** be in the YAML without being in the registry (the phantom case #495 documents).

### D10 — Migration rollout sequencing

The migration from today's `scope.excludes`-based perimeter to capability-keyed authorization is sequenced in five stages. Each ships green before the next is promoted. **The `.intent/` hard invariant is retired only in the same change-set that promotes the capability tier to blocking for `.intent/`-writing capabilities — there is no intermediate state in which dev-mode `.intent/` is structurally unprotected.**

1. **Plumbing.** Introduce `current_capability()` and `current_mode()` accessors. Extend `_guard_paths` to read both and pass them to `check_transaction`. Extend `check_transaction` with the capability tier in *advisory* mode — log decisions, do not block. The phantom-decoration invariant ships as a load-time check immediately (D9). At this stage the only behavioral change is logging; the perimeter is unchanged. The `_READ_ONLY_RULE_ID` hard `.intent/` invariant stays live; `.specs/` remains unprotected (its today-state).

2. **Phantom resolution.** Strip the four `secrets.*` entries from `operational_capabilities.yaml`. Re-route `test_system` through `ActionExecutor.execute("test.execute")` per D9 Shape 2's three-change recipe. Promote the decorator-backing AST check from advisory to blocking. The YAML is now consistent with the runtime decoration surface. Hard `.intent/` invariant still live.

3. **Per-capability promotion of non-`.intent/`-writing capabilities.** Promote the capability tier from advisory to blocking on a per-capability allowlist, **restricted to capabilities that do not authorize writes to `.intent/` or `.specs/`**. The first capabilities to flip are read-only (`admin.meta`, `check.*`) and DB-only (`cleanup.*`, `claim.proposal`, `manage.define_symbols`). Each flip is a YAML edit; the chokepoint reads it on the next load. Each capability earns its blocking status by surfacing zero advisory denials over a representative sample of autonomous runs. Hard `.intent/` invariant still live throughout this stage. No `.intent/`-writing capability is promoted yet.

4. **Atomic `.intent/` and `.specs/` swap.** In a single change-set: (a) the capability tier is promoted to blocking for the set of capabilities whose fs_profile authorizes writes to `.intent/` or `.specs/`; (b) `_READ_ONLY_RULE_ID` is retired from `IntentGuard`; (c) the floor-set is extended to make `.intent/` and `.specs/` mode-conditional per D7. The three changes land together. At the point this change-set merges: in live mode, `.intent/` and `.specs/` are floor-blocked (equivalent to today's behavior on `.intent/` plus new coverage of `.specs/`); in dev mode, they are subject to the capability tier, which is unconditionally blocking. There is no instant at which dev-mode `.intent/` is structurally unprotected — the old block is live until the new block is enforcing, and the swap is atomic. Today's taxonomy declares no capability with `.intent/**` or `.specs/**` in any mutation op-class, so the set the capability tier is promoted-for in (a) is empty as of stage 4's merge — stage 4 retires the hard invariant against an empty enforcement target, which is the property that makes it risk-free for current state. The first capability that wants `.intent/` or `.specs/` write authority is added in a separate, governor-reviewed change-set after stage 4 lands; at that point the chokepoint authorizes it under dev mode with no further migration work.

5. **Full promotion + `scope.excludes` retirement.** Promote the capability tier to blocking for every remaining capability not yet flipped. Retire `scope.excludes` entries on rules whose authorization has been subsumed by the capability tier. The retirement is per-rule, each documented in the rule's `.intent/` file's revision history.

**No big-bang flip.** The sequencing exists precisely because a single flip from advisory to blocking on a system this size carries a defect cost (any missing fs_profile entry becomes a hard block). The per-capability promotion in stage 3 surfaces gaps as advisory denials before they become operational denials for the safe subset; the stage-4 atomic swap preserves `.intent/` protection across the changeover. ADR-077 §6's two-dial pattern is the precedent this borrows from; the atomic-swap addition is this ADR's contribution.

**Sequencing intersection with ADR-077.** ADR-077 §6's `forbidden_classes: [write]` promotion for `protected_markers = [".intent", ".specs"]` is the *audit-time* backstop that closes the perimeter; this ADR's stage 4 is the *runtime* block that closes the chokepoint. Both must hold for paper §4's "the door is the only way out" to be a runtime guarantee. The promotions are sequenced such that ADR-077's audit-time block does not fire on capability-permitted dev-mode writes — i.e., the audit-time block's `allowed callers` set must include the FileHandler call sites that mediate authorized writes. The intersection is a stage-4 verification item per below.

### D11 — Audit invariant: chokepoint decisions are logged with full context

Every chokepoint decision — permit or deny — logs (at appropriate level):

- the calling capability (`None` if unset)
- the op-class
- the target path(s)
- the current mode
- the decision and, for denials, the reason code (one of the seven from D5)
- whether the decision was advisory (stage 1–4) or blocking (stage 5)

Permits log at DEBUG; denials log at WARNING; advisory denials in stages 1–4 log at INFO with a distinct marker (`chokepoint.advisory.would-deny`) so the operational signal can be filtered. The log line is structured (one log call, structured fields), suitable for the daemon-side metrics pipeline to attribute denials to capabilities.

The audit log line is not the same as the existing `IntentGuard.check_transaction` violation list. The violation list is the *result* surface; the audit log is the *decision* surface. Both are produced.

### D12 — Out-of-scope reaffirmation

This ADR does not specify:

- **The mode-flag source-of-truth or provenance guarantees** (#492). The placeholder env-var implementation in D4 is explicitly inadequate for any live deployment and is replaced wholesale when #492 lands.
- **The governor-token machinery for dev-mode privileged writes.** Paper §6 describes governor-token-mediated `.intent/` writes; the machinery is a separate ADR. This ADR's dev-mode chokepoint behavior does not depend on the token's specific shape — a capability-permitted dev-mode `.intent/` write happens whether or not the token machinery is present.
- **The full migration execution plan.** D10 specifies sequencing principles; the actual execution (per-capability promotion schedule, retirement dates for `scope.excludes` entries, rule-by-rule audit-time backstop sequencing) is issue-tracked, not ADR-fixed.
- **Read authorization at runtime.** Per D5's leading paragraph, this chokepoint authorizes mutations only. A future ADR may declare a read-authorization chokepoint that consumes the `read:` lists in `operational_capabilities.yaml` — until then those lists are forward-declarations. Audit-time read protection of `.intent/` and `.specs/` remains ADR-077's concern.
- **`#494`'s dead `is_metadata` variable.** Adjacent but a separate cleanup; cited in references for context.
- **Convergence of the ~340 non-gateway filesystem call sites in `src/`.** That is ADR-077's perimeter-completeness concern; this ADR depends on its completion but does not redo it.

## State at ADR acceptance

| Item | State |
|---|---|
| Chokepoint location declared | D1 |
| Capability identity propagation declared | D2 — reuses existing `_executor_token` |
| Op-class derivation declared | D3 — TOCTOU caveat named |
| Mode-flag consumer contract declared | D4 — provenance deferred to #492 |
| Authorization scope: writes only declared | D5 leading paragraph — read deferred per D12 |
| Policy decision table declared | D5 |
| Tier-order extension declared | D6 |
| `.intent/` and `.specs/` chokepoint behavior declared | D7 |
| Sandbox propagation surface decision declared | D8 — audit-time enforcement caveat named |
| Phantom-resolution policy declared | D9 — Shape 1 strip, Shape 2 three-change re-route |
| Migration rollout sequencing declared | D10 — atomic swap eliminates fail-open window |
| Audit invariant declared | D11 |
| `current_capability()` accessor in `shared/governance_token.py` | **Not yet authored** |
| `current_mode()` placeholder accessor at `shared/infrastructure/intent/operational_mode.py` | **Not yet authored** |
| Extension of `_guard_paths` + `check_transaction` for capability tier | **Not yet authored** |
| `secrets.*` entries stripped from `operational_capabilities.yaml` | **Not yet applied — stage 2** |
| `test_system` re-route + `run_tests` register/decorate/`**kwargs` extension | **Not yet applied — stage 2** |
| `governance.taxonomy.operational_capabilities_decorator_backing` audit rule | **Not yet authored** |
| Per-capability promotion of non-`.intent/`-writing capabilities | **Not yet applied — stage 3** |
| `_READ_ONLY_RULE_ID` hard-invariant retirement (atomic with capability-tier promotion) | **Not yet applied — stage 4** |
| Floor-set reshape (D7) | **Not yet applied — stage 4** |
| `governance.chokepoint.write_validated_bytes_sole_caller` audit rule | **Not yet authored** |
| Mode-source-of-truth replacement | **Deferred to #492** |
| Governor-token machinery | **Deferred to separate ADR** |
| Per-capability allowlist promotion schedule | **Deferred to issue-tracking** |

The decision exists. The chokepoint is not yet runtime-keyed on capability; the migration's stage 1 is the first implementation step.

## Consequences

**Positive:**

- Paper §9 bullets 5 and 6 are closed. The §9 list contracts from six items to three (mode-provenance, governor-token, full migration execution).
- The §7 "no provenance" requirement becomes a structural property: the chokepoint denies writes with no capability identity, no exception, no per-call override.
- The §6 mode dimension acquires a runtime consumer. Paper §3's "same code, two modes, two answers" is observable behavior, not just specification text.
- Paper §8's amendment to `IntentGuard.md` §4 — the `.intent/` floor block becoming mode-conditional — is realized in code, not just acknowledged in a Note marker.
- Zero new propagation infrastructure: the chokepoint consumes `_executor_token`, which already exists for governance-token enforcement. This collapses what could have been a parallel mechanism with its own bugs into a single context-var with one consumer pattern.
- The phantom class (#495) is resolved structurally: the YAML and the decoration surface become mutually-required, and the audit rule prevents the next phantom from being silent.
- The per-capability rollout in D10 stage 3 surfaces fs_profile gaps as advisory denials before they become operational denials. The migration is incremental and reversible at each stage.
- The capability-tier sequencing in D10 is fail-closed across the changeover: `.intent/` protection moves from one structural form to another without an advisory-only window. Paper §5's "structural property, not a discipline" claim holds across the migration, not just at its endpoints.
- The dead `is_metadata` variable (#494) becomes a separately-clearable line: this ADR neither uses it nor relies on it. Its removal can be a one-line PR independent of this work.

**Negative:**

- The chokepoint's decision adds 1 stat call per path (D3 create-vs-modify resolution). For transactions of ~10 paths this is ~10 stat calls per write; acceptable, but a measurable hot-path addition. Mitigation: stat is cheap and cached at the OS level; if profiling later shows it as a hotspot, the resolution can be moved into the FileHandler method (each method already knows whether it's creating or modifying in many cases).
- The placeholder `current_mode()` in D4 is a forward-looking liability: it is correct for dev-mode-only operation today, but a live deployment that ships before #492 lands gets only env-var-grade provenance. Mitigation: the placeholder's "default on uncertainty is live" semantics fail closed — a forged dev signal requires the attacker to *successfully* set the env var, not merely to be in the absence of provenance. The forward-looking risk is documented in #492's trigger condition.
- The advisory-period logging (D10 stages 1–3) produces a non-trivial INFO-level log volume during the migration window. Mitigation: the structured marker `chokepoint.advisory.would-deny` makes the volume filterable; the period is bounded by stage 5 promotion.
- The dual-tier evaluation in D6 (capability + rule) means some rules are subsumed by capability authorization mid-migration but cannot be retired until D10 stage 5. During stages 1–4, a capability-permitted write may still hit a rule that has been "logically retired" but not yet "yaml-retired." This is the expected migration cost; rule retirement is the final stage precisely because the in-flight period is acceptable for a per-rule retirement decision.
- The `write_validated_bytes` bypass (D8) remains a single legitimate hole in the chokepoint perimeter. The new audit rule (`governance.chokepoint.write_validated_bytes_sole_caller`) constrains its blast radius to one call site, but enforcement is audit-time rather than call-time. The hole exists, narrowly, by design; the limitation is recognized.
- D9's phantom-resolution forces a YAML edit (strip secrets.*) and a code change (re-route `test_system` through the executor + register/decorate/`**kwargs` extension on `run_tests`) into the same change-set as the chokepoint plumbing. Mitigation: the change-set is bounded (4 YAML entries removed, 1 register + 1 decorator + 1 signature extension + 1 dispatch site rewritten + 1 sole-caller audit rule added) and unit-test-verifiable.
- Read authorization is not addressed by this ADR. The `read:` lists in `operational_capabilities.yaml` carry forward-declared authority that no runtime mechanism in CORE enforces today. Mitigation: ADR-077's audit-time check covers `.intent/` and `.specs/` reads; arbitrary-path read authorization is acknowledged as an open gap, deferred. The loader's requirement that all four `fs_profile` keys be present (ADR-078 D4) keeps the forward-declarations consistent and ready for a future read-authorization ADR to consume without a schema migration.
- D9 Shape 2's three-change recipe (`@register_action` + `@atomic_action` + executor re-route + `**kwargs`) replaces what the inventory and #495 framed as "decorate the underlying function." The framing was incomplete; the substantive change is the re-route. The implementation cost is one additional indirection in the `test_system` body and one additional registry entry — small, but worth naming because the inventory-level summary obscured it.
- The chokepoint's reliance on `_executor_token` means that any future code path that needs to write outside `ActionExecutor.execute`'s dispatch (e.g., a future bootstrap step that runs before the executor is initialized) cannot reach the chokepoint as currently designed. This is the §7 deny-on-no-context property by another name — bootstrap-time writes need a separate, declared mechanism (likely a "bootstrap" mode flag or a dedicated capability with its own token). The cost is forward-looking, not current; no existing path is broken.

## Verification

Deferred to implementation. At implementation (per migration stage):

**Stage 1 verification:**

1. `current_capability()` exists in `shared/governance_token.py` and returns `_executor_token.get()` verbatim.
2. `current_mode()` exists at `shared/infrastructure/intent/operational_mode.py`, reads `CORE_OPERATIONAL_MODE` env var, returns `"live"` for any value other than the exact strings `"dev"` and `"live"`.
3. `IntentGuard.check_transaction` accepts an optional capability tier evaluation; the path through the new tier is reachable but does not change permit/deny outcomes (advisory).
4. A `chokepoint.advisory.would-deny` log line is emitted for each path that the new tier would deny.
5. Unit tests cover: `_executor_token` unset → tier reports would-deny with reason `no_capability_context`; unknown capability → would-deny with reason `unknown_capability`; etc., for each D5 branch.

**Stage 2 verification:**

6. `operational_capabilities.yaml` does not contain `secrets.set`, `secrets.get`, `secrets.list`, or `secrets.delete`.
7. `mind/enforcement/audit.py:test_system` invokes `core_context.action_executor.execute("test.execute")` rather than calling `run_tests()` directly. `run_tests` (or its wrapper) carries both `@atomic_action(action_id="test.execute")` and `@register_action(action_id="test.execute")`. The executor's registry returns a definition for `test.execute`.
8. `run_tests`' parameters are satisfiable through `ActionExecutor._prepare_params`. Specifically: `run_tests`' signature is extended to include `**kwargs` (mandatory — `atomic_action.py:74-82` raises `TypeError` at decoration time without it, per the issue #448 / ADR-070 D8 invariant). `_prepare_params` will pass `write=True` and any caller-supplied kwargs; the `**kwargs` absorbs `write` (which `run_tests` ignores), and `suppress_logging` defaults to `True` if unspecified. A unit test dispatches `test.execute` through the executor and asserts no `TypeError` on parameter binding. This verifies the param-compatibility path that decoration alone would have masked until first runtime call.
9. Under instrumented dispatch (a unit test that wraps `current_capability()`), a FileHandler call from inside `run_tests` returns `"test.execute"` as the calling capability — confirming the `[test.system → test.execute]` stack assumed by D9 Shape 2.
10. The `governance.taxonomy.operational_capabilities_decorator_backing` audit rule exists, is blocking, and produces zero findings on the post-stage-2 tree.

**Stage 3 verification:**

11. Per-capability promotion of non-`.intent/`-writing capabilities: each capability flipped from advisory to blocking has zero `chokepoint.advisory.would-deny` log lines attributed to it over the preceding representative-sample window.
12. `_READ_ONLY_RULE_ID` is still live; dev-mode `.intent/` writes still hit the tier-1 hard invariant (the migration's `.intent/` protection is unchanged across stages 1–3).

**Stage 4 verification:**

13. Stage 4 lands as a single change-set: `_READ_ONLY_RULE_ID` removal, floor-set extension, and capability-tier blocking promotion for the (currently empty) set of `.intent/`/`.specs/`-writing capabilities are all in one commit. A bisect-test verifies no commit in main's history between the merge of stage 3 and the merge of stage 4 has dev-mode `.intent/` advisory-only.
14. In live mode, a write to `.intent/foo` produces a floor-block denial; in dev mode, the same write falls through to the capability tier (which is unconditionally blocking; with the empty set of authorized `.intent/`-writing capabilities at stage-4 merge, the write is denied). The same behavior holds for `.specs/`.
15. ADR-077's protected-namespace audit-time check does not fire on capability-permitted dev-mode writes — i.e., the `allowed callers` set in ADR-077's `forbidden_classes: [write]` rule includes the FileHandler call sites that mediate authorized writes.

**Stage 5 verification:**

16. The capability tier is unconditionally blocking for every capability; no advisory bypass remains.
17. `scope.excludes` entries are retired only for rules whose authorization has been subsumed by the capability tier; per-rule retirement is documented in the rule's `.intent/` revision history.
18. `core-admin code audit` produces no findings related to chokepoint-tier coverage.

**Standing verification (post-migration):**

19. `governance.chokepoint.write_validated_bytes_sole_caller` produces zero findings — the only call site is `body/atomic/executor.py:_propagate_sandbox_changes`.
20. The phantom-decoration audit rule continues to fire on any new YAML entry without matching decoration.
21. Read authorization is not enforced at runtime by this chokepoint; the `read:` lists in `operational_capabilities.yaml` are accepted by the loader (ADR-078 D4) but not consulted by the runtime decision table. This is a deliberate scope boundary per D5 and D12, not a gap; an audit rule confirming the `read:` lists are unreferenced by the chokepoint code in `body/governance/` is optional and may be added if regression risk is a concern.

## References

- Paper: `.specs/papers/CORE-Capability-Scoped-Filesystem-Authority.md` — §4 (chokepoint), §5 (capability-scoped least authority), §6 (mode dimension), §7 (capability identity at the chokepoint), §8 (relationship to IntentGuard.md §4 amendment), §9 bullets 5 and 6 (the deferrals this ADR fulfills).
- Paper: `.specs/papers/CORE-IntentGuard.md` §4 — receives the dated Note marker for the floor-block amendment realized by D7.
- Paper: `.specs/papers/CORE-Enforcement-Completeness.md` — governs the write-perimeter property that makes the chokepoint singular. ADR-077 is its implementation; this ADR depends on its completion.
- ADR-077 — Config-driven protected-namespace access; declares `filesystem_operations.yaml` (the call-name → op-class vocabulary) and the audit-time backstop sequencing this ADR's stage 4–5 promotion intersects with.
- ADR-078 — Operational-Capability Taxonomy Schema; declares `operational_capabilities.yaml`, the per-capability `fs_profile` surface this ADR's chokepoint consumes. D3, D4, D8, D9, D10 of ADR-078 are direct prerequisites; D9 (dormant exclusion) is the structural counterweight to this ADR's D9 (phantom exclusion).
- ADR-068 — Principal Role Taxonomy; established the fail-closed loader pattern shared by the consumed YAMLs.
- ADR-070 D8 — `@atomic_action` decoration-time `**kwargs` enforcement; the invariant that the D9 Shape 2 signature extension on `run_tests` satisfies.
- ADR-071 D2.2 — Hermetic worktree sandboxing; defines `write_validated_bytes`'s sanctioned use that D8 preserves.
- ADR-008 — Action risk classification; the `action_risk.yaml` surface that remains the risk-classification source-of-truth orthogonal to chokepoint authorization.
- Issue #448 — `@atomic_action` signature `**kwargs` requirement; the prior incident the D9 Shape 2 signature extension obeys.
- Issue #492 — Mode-provenance ADR (sibling §9 deferral); the source-of-truth replacement for D4's placeholder accessor.
- Issue #494 — Dead `is_metadata` variable at `intent_guard.py:368`; adjacent cleanup, separately clearable.
- Issue #495 — Five phantoms in `operational_capabilities.yaml`; D9 resolves with per-shape decisions (strip secrets.*, re-route `test_system` through executor with `run_tests` register/decorate/`**kwargs`).
- `src/shared/governance_token.py` — `_executor_token` ContextVar and `authorize_execution` / `verify_authorization`; the existing surface D2 reuses verbatim.
- `src/body/atomic/executor.py` — `ActionExecutor.execute` and `_propagate_sandbox_changes`; D2 propagation entry point and D8 sandbox-bypass invariant respectively.
- `src/body/governance/intent_guard.py` — the IntentGuard whose `check_transaction` D5 / D6 / D7 extend.
- `src/shared/infrastructure/storage/file_handler.py` — the FileHandler whose `_guard_paths` D3 extends.
- `.intent/taxonomies/operational_capabilities.yaml` — the live capability-authorization surface; consumed by D5.
- `.intent/taxonomies/filesystem_operations.yaml` (declared by ADR-077) — the call-name → op-class vocabulary; **not** consumed by this ADR's chokepoint (D3 inlines the FileHandler-method mapping), but is the audit-time perimeter check's source per ADR-077.
