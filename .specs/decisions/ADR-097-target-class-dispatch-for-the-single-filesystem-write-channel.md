<!-- path: .specs/decisions/ADR-097-target-class-dispatch-for-the-single-filesystem-write-channel.md -->

# ADR-097 — Target-class dispatch for the single filesystem write channel

**Date:** 2026-06-08
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-08, after shadow_materializer.py prototype landed and produced a 510-row/24h abandoned-pile bleed against `governance.mutation_surface.filehandler_required`. Initial frame was "two surfaces" — a sibling chokepoint for ephemeral writes alongside FileHandler. Governor reframed in concept-mode: *one channel, target/non-target doesn't matter*, with the future move of `.intent`/`.specs` via API already prepared by the single-channel shape. The reframe collapsed two parallel chokepoints into one path-aware chokepoint and made `shadow_materializer.py` the forcing function rather than the exception.)
**Grounding paper:** `papers/CORE-Capability-Scoped-Filesystem-Authority.md` §4 ("there is one door, and the door is the only way out"). This ADR is the target-class dimension of §4 — orthogonal to ADR-079's capability dimension and ADR-080's op-class dimension on the same chokepoint.
**Related:**
- ADR-079 (Chokepoint implementation; D1: FileHandler is the chokepoint, extended in place — this ADR keeps that decision and adds a third input to the decision tuple).
- ADR-080 (FS op-class vocabulary split; this ADR's target-class dispatch composes with op-class to form the full `(capability, op-class, target-class, mode)` decision).
- ADR-096 (Shadow KG sensation primitive; D3 named `shadow_materializer.py` as the materialization surface but deferred the question of how its `mkdir` + `write_text` calls reconcile with the FileHandler-required blocking rule. This ADR resolves that question by routing the materializer through the channel rather than around it).
- ADR-071 D2.2 (worktree sandbox propagation; `write_validated_bytes` is the same problem shape as shadow materialization — a write whose validation set differs from the repo-source default. This ADR generalizes that one-off bypass into a principled target class).
- Issue #593 (exclude logic glob bug; orthogonal but landed in the same session — the exclude-side fix is necessary regardless of this ADR; this ADR removes the *reason* to keep adding excludes for legitimate ephemeral writes).

---

## Context

ADR-079 established that **FileHandler is the single write chokepoint**, with capability-keyed authorization (D1). ADR-080 established the **op-class vocabulary** (write/read; create/modify/delete). With both in place, paper §4's "one door" property is structurally enforceable: every write passes through one place, the place knows who is writing and what op-class the write is, and the policy decision is data-driven.

But the *behavior* the chokepoint applies after the policy passes is not yet target-aware. Specifically:

- `write_runtime_text` runs `ast.parse(content)` on `.py` files and injects `# ID:` anchors when the substring `"src/"` appears in the path.
- `write_runtime_bytes` and `write_runtime_json` skip the syntax check but still go through `_guard_paths`.
- `write_validated_bytes` skips IntentGuard entirely (ADR-071 D2.2 sandbox-propagation carveout) — the comment says "NOT a general write surface — actions must use write_runtime_text / _bytes."
- `ensure_dir`, `remove_file`, `remove_tree`, `copy_tree`, `copy_repo_snapshot` route through `_guard_paths` and apply op-class-appropriate behavior, but the *target* of each operation is not classified.

The behavior set is correct for the **repo-source** target class (`src/foo.py` is mutated → syntax must parse, ID must anchor, IntentGuard must clear). It is **wrong for every other target class**, and that wrongness has produced four observable symptoms:

1. **`shadow_materializer.py` (ADR-096 D3) does direct `mkdir` and `write_text` into `var/tmp/core-shadow-<uuid>/`.** It must, because `FileHandler.write_runtime_text` would run `ast.parse` on every materialized `.py` file (correct for `src/` mutation, wrong for shadow projection — crate content might be mid-generation) and inject ID anchors into paths matching `*src/*` (catastrophically wrong: the materialization path contains `src/` as a sub-segment, so every crate file under `shadow/src/` would get re-anchored mid-flight). The materializer's only escape today is to bypass FileHandler entirely. Two blocking rules fire on it (`governance.mutation_surface.filehandler_required`, `governance.logic_mutation.governed`). The autonomous remediator can't fix structural sanctuary cases; it abandons each finding; the sensor re-emits next cycle; **the file produced 510 abandoned rows in 24 hours from a single legitimate use site**.

2. **`src/will/test_generation/sandbox.py` (PytestSandboxRunner)** has the same shape: `tempfile.TemporaryDirectory(dir=var/tmp)` → `dst.mkdir(...)` → `dst.write_text(...)`. Same legitimate use (hermetic test materialization), same blocked-by-default classification, same exclude-or-refactor dilemma.

3. **`src/will/self_healing/remediation_evidence_writer.py`** already migrated to `file_handler.write_runtime_json` for the JSON write, but `file_handler.ensure_dir` for the directory create — and at the time the abandoned-pile signal was created on 2026-05-31, the file still had a raw `remediation_dir.mkdir(...)`. The blackboard row from before the refactor lingered as `indeterminate` for a week; the audit sensor doesn't sweep its own history on file fix. The session 2026-06-08 stale-row sweep cleared it manually.

4. **`write_validated_bytes`** is the in-tree precedent: ADR-071 D2.2 already accepted that "some writes legitimately skip the repo-source validation set." It is currently a *named exception*, not a target class. The exception works for sandbox propagation specifically because the content was governance-validated upstream in the worktree; the same logic doesn't generalize without invoking the target class explicitly.

The pattern across all four: the channel knows the call site's op-class but not the target's role in the repo. **Repo-source mutation, runtime-output emission, ephemeral materialization, and governed-artifact authoring are four different jobs that happen to share a write primitive.** Conflating them under the repo-source default leaks structurally — by `Path.write_text` bypass (shadow_materializer, sandbox), by named exceptions (write_validated_bytes), and by per-file `.intent/` excludes that accumulate (the session pattern).

### The future move this ADR prepares for

`.intent/` and `.specs/` are filesystem-direct today, with the confirmation gate as a procedural shield. The architectural direction (governor's stated trajectory) is API-mediated access: a governance API endpoint that validates artifacts against META schema, records the write in an audit trail, performs the actual filesystem write — through FileHandler.

If FileHandler is target-class-aware, this API is a *caller* with stricter pre-checks. The chokepoint never multiplies. If FileHandler is target-class-unaware, the API has to invent its own parallel write path for `.intent`/`.specs/`, or be glued onto the substring-based src/-detection logic. The single-channel property is either preserved by construction or sacrificed by accretion. This ADR preserves it.

### Constraints inherited

- **Paper §4 / ADR-079 D1.** One door. No parallel chokepoint. This ADR extends the door; it does not duplicate it.
- **ADR-079 D2.** Capability identity reaches the chokepoint through `_executor_token`. Target-class dispatch composes; it does not replace this input.
- **ADR-079 D3.** Op-class is derived from the FileHandler method invoked, internally. Target-class is the new, orthogonal input — derived from the target path, also internally.
- **ADR-080.** The op-class vocabulary is the live taxonomy; target-class is a *sibling* taxonomy on a different axis (where the write lands), not a refinement of op-class.
- **ADR-071 D2.2.** `write_validated_bytes` exists for a real reason; this ADR generalizes the reason rather than removing it.

---

## Decisions

### D1 — A single filesystem write channel; the channel dispatches on target class

`FileHandler` remains the sole filesystem write chokepoint for all CORE code (production, infrastructure, tests, prototypes, governance tooling). No parallel write surface is introduced — not for ephemeral materialization, not for sandbox propagation, not for governed-artifact authoring. The chokepoint's decision input grows from `(capability, op-class, target-path, mode)` to `(capability, op-class, target-path, target-class, mode)`. **`target-class` is derived internally from `target-path`; callers do not pass it.**

This is paper §4's "one door" property generalized one step further: not only does every write pass through one place — the *behavior* applied after the policy passes is also one decision tree, parameterized on what the write is for. The four current write methods (`write_runtime_text`, `write_runtime_bytes`, `write_runtime_json`, `write_validated_bytes`) become internal dispatch outcomes of the channel, not separate public surfaces. The public surface collapses to a unified entry point (D4).

**Why one channel, not two.** A parallel channel for "ephemeral writes" was the first-draft framing of this work. It fails on three counts: (i) it multiplies the chokepoint and requires the `governance.mutation_surface.filehandler_required` rule to enumerate both — exactly the bypassable-by-construction shape paper §4 forecloses; (ii) it forces every consumer to choose channels at the call site, re-introducing the discipline-not-structure failure mode ADR-079 D1 calls out; (iii) it doesn't generalize to the `.intent`/`.specs/` API future move without inventing a third channel. One channel with target-class dispatch is strictly stronger and structurally simpler.

### D2 — Target-class taxonomy

The channel resolves each target path into exactly one target class. The initial classes:

| Class | Identity | Examples | Lifetime |
|---|---|---|---|
| `repo-source` | Path resolves under `src/`, `tests/`, or top-level repo source dirs | `src/foo.py`, `tests/test_bar.py`, `pyproject.toml` | Permanent (commit-bearing) |
| `runtime-output` | Path resolves under `reports/`, `var/cache/`, or other non-ephemeral runtime dirs | `reports/audit/<ts>.json`, `var/cache/embeddings/...` | Persistent (operational, not commit-bearing) |
| `ephemeral-scratch` | Path resolves under `var/tmp/` | `var/tmp/core-shadow-xxx/src/foo.py`, `var/tmp/sandbox_xxx/test_y.py` | Transient (auto-cleaned, never committed) |
| `governed-artifact` | Path resolves under `.intent/` or `.specs/` | `.intent/rules/...`, `.specs/decisions/...` | Permanent (governance-bearing) |

Classification rules:

- **Resolution is path-based, not substring-based.** The path is resolved (`_resolve_repo_path`), then the resolved repo-relative form is matched against the class boundaries in declared order. `var/tmp/foo/src/bar.py` is `ephemeral-scratch` because `var/tmp/` matches first; the embedded `src/` substring is not consulted. This is the fix for the `_ensure_id_anchors` substring bug at the same time.
- **Boundaries are exhaustive and disjoint.** Every repo-relative path classifies into exactly one class. A path that classifies into none (e.g. a top-level file not enumerated) defaults to `repo-source` — fail-safe toward the strictest validation set.
- **The taxonomy is data-driven, in `.intent/`.** A new artifact `target_class_boundaries.yaml` enumerates the class prefixes. This avoids hardcoding paths in `src/` and lets governance amend the taxonomy without code changes. (Loader pattern follows ADR-077 / ADR-078; META schema lives at `.intent/META/target_class_boundaries.schema.json`.)

### D3 — Per-class behavior matrix

For each `(target-class, op-class)` cell, the channel applies a fixed behavior set. The full matrix:

| Target class \ Op-class | `create` / `modify` | `delete` |
|---|---|---|
| `repo-source` | Syntax check (.py); `# ID:` anchor inject for new public defs; IntentGuard repo-source tier; atomic write | IntentGuard repo-source tier; atomic delete |
| `runtime-output` | No source-shape transforms; IntentGuard runtime tier; atomic write | IntentGuard runtime tier; atomic delete |
| `ephemeral-scratch` | No source-shape transforms; IntentGuard ephemeral tier (capability-checked but no schema/syntax gates); atomic write | IntentGuard ephemeral tier; atomic delete |
| `governed-artifact` | META-schema validation; confirmation-gate / API authorization tier; atomic write | API authorization tier (no direct delete from code) |

**Three invariants the matrix preserves.**

(i) `repo-source` behavior is exactly today's `write_runtime_text` semantics when path is under `src/`. No production write becomes *less* validated under this ADR.

(ii) `ephemeral-scratch` permits the writes shadow_materializer and sandbox.py do today, but they pass *through* the chokepoint — so IntentGuard's capability check still runs, the audit trail still stamps, and the rule `governance.mutation_surface.filehandler_required` is satisfied structurally rather than excluded.

(iii) `governed-artifact` reserves a slot for the future `.intent`/`.specs/` API. Today, writes to those paths from `src/` continue to be denied (paper §6 default-on-uncertainty, plus the existing IntentGuard hard invariant on `.intent/`); the matrix cell exists so the API move drops in without a new chokepoint.

### D4 — Public surface: one entry point, target-aware

The FileHandler public write surface collapses to:

```python
def write(self, rel_path: str, content: str | bytes, *, impact: str | None = None) -> FileOpResult:
    """Single-channel filesystem write. Target class is derived from rel_path;
    op-class is derived from existence + content type; behavior follows D3."""
```

`write(rel_path, content)` resolves the target class internally and applies the D3 behavior set. JSON convenience is preserved via a thin wrapper (`write_json(rel_path, payload)` calls `write` with serialized content). `bytes` content skips the syntax check regardless of target class — the syntax check is text-only.

**Deprecation path for the existing method surface.** `write_runtime_text`, `write_runtime_bytes`, `write_runtime_json`, `write_validated_bytes`, `add_pending_write`, `ensure_dir`, `remove_file`, `remove_tree`, `copy_tree`, `copy_repo_snapshot` remain as call sites in `src/` until migration completes; each becomes a thin wrapper over the unified `write` / `delete` / `ensure_dir` triad with target-class derived from the path. `write_validated_bytes` specifically retires: its semantics (skip-validation for sandbox-propagated content) become `ephemeral-scratch` target-class behavior under the new dispatch, with no caller-side opt-in needed. ADR-071 D2.2's named exception dissolves into the matrix.

**`FileService` (`src/body/services/file_service.py`)** today re-exposes FileHandler's surface with leak-through naming (`write_file`, `write_runtime_bytes`, `write_runtime_json`, `ensure_dir`). That layer narrows to a path-aware thin wrapper around the unified channel — same behavioral semantics, fewer methods. Per-target-class wrappers, if needed, live as FileService convenience helpers, never as parallel write paths.

### D5 — Migration: shadow_materializer, sandbox, FileService consumers

Three call sites listed in Context migrate as the canonical proof-of-shape:

- **`src/shared/infrastructure/context/shadow_materializer.py`** — `mkdir` and `write_text` calls inside `materialize_workspace_for_audit` switch to `self._fh.write(rel_path, content)`. Target paths resolve under `var/tmp/core-shadow-<uuid>/` → `ephemeral-scratch` target class → no source-shape transforms, no ID-anchor injection on the crate-overlaid `src/` files. The 510-row/24h abandoned-pile bleed stops because the underlying writes now pass the `governance.mutation_surface.filehandler_required` blocking rule by construction.
- **`src/will/test_generation/sandbox.py`** — `dst.mkdir` and `dst.write_text` / `test_file_path.write_text` switch to `self._fh.write(rel_path, content)`. Same target class, same behavior set. The 3 indeterminate findings on this file resolve structurally.
- **`src/will/self_healing/remediation_evidence_writer.py`** — already uses `file_handler.write_runtime_json` and `file_handler.ensure_dir`. Under D4, these call sites narrow to `file_handler.write` / `file_handler.ensure_dir` with no behavior change (target paths resolve under `reports/` → `runtime-output` target class, which retains the current runtime-tier IntentGuard behavior).

The migration is **explicit and per-file**, not implicit. Each consumer's behavior change (or lack of one, in case 3) is verified in the change-set by a smoke test of the materialization / sandbox / evidence-writer path and a re-audit confirming no new findings.

### D6 — Future-proofing for `.intent`/`.specs` API mediation

When `.intent/` and `.specs/` move to API-mediated access (the trajectory the governor has named), the API becomes a *caller* of `FileHandler.write` with the target class resolving to `governed-artifact`. The matrix cell (D3) reserves the behavior:

- META-schema validation runs in the API layer before the write call.
- The API supplies the authorization context (governor identity, confirmation-gate state) that the `governed-artifact` IntentGuard tier consumes.
- The write itself routes through the same chokepoint as every other write — same audit trail, same atomic-write guarantee, same `_executor_token` propagation.

This ADR does not specify the API itself; it specifies that **the chokepoint will not have to change to accommodate it**. The migration cost of the API move is bounded to (i) the API endpoint, (ii) META schema validation, (iii) `governed-artifact` IntentGuard tier policy. Nothing in the channel multiplies.

The corollary: until the API ships, direct writes to `.intent/` and `.specs/` from `src/` code continue to be denied at the IntentGuard hard-invariant tier (paper §6, ADR-079 D1 inherited). The confirmation gate in CLAUDE.md governs human-driven edits; this ADR does not relax it.

---

## Migration

Sequencing (each step verifiable independently, no all-or-nothing change-set):

1. **Land `target_class_boundaries.yaml` + loader + META schema.** Data-only change in `.intent/`. Loader exposes `resolve_target_class(rel_path) -> TargetClass`. No `src/` consumer yet; the function is dormant until step 2.
2. **Extend `IntentGuard` with `target-class` input and the D3 behavior matrix.** New tiers (`runtime`, `ephemeral`, `governed-artifact`) added alongside the existing repo-source tier; current callers continue to hit repo-source tier by default. Per ADR-079 D1, no method-signature breaking changes at the public surface; the target class is read internally from the resolved path.
3. **Add the unified `FileHandler.write` entry point** with target-class dispatch. Existing methods (`write_runtime_text` etc.) become thin wrappers; their behavior is unchanged this step (still hardcoded repo-source-tier defaults).
4. **Flip the dispatch.** Each existing method derives target class from the resolved path and routes through the unified dispatch. The substring-based `if "src/" in rel_path` check at `write_runtime_text:120` is removed and replaced by the resolved-path classification. **Verification: audit pass on the full repo shows zero behavior regression on `repo-source` writes** (the dominant case in production code).
5. **Migrate the three forcing-function consumers** (D5): shadow_materializer, sandbox, evidence_writer. The 510-row/24h bleed stops; the indeterminate findings on these files clear; the abandoned pile drains by 1020+ findings (510 × 2 rules on shadow_materializer alone).
6. **Retire `write_validated_bytes`** as a named method; its callers (ADR-071 D2.2 sandbox propagation) shift to the unified `write` with `ephemeral-scratch` target class. The ADR-071 D2.2 carveout-comment in `file_handler.py` is removed and the principled-shape note appended to ADR-071's history.
7. **Narrow `FileService`** to the unified surface (D4). External callers (Will-tier consumers per `[[will-tier-file-ops-use-fileservice]]`) update import + call patterns; the migration is mechanical.

Steps 1–4 are landing-order-coupled. Steps 5–7 land independently after step 4 lands and bakes one audit cycle.

## Verification

- **Behavioral regression check:** every existing FileHandler call site in `src/` is exercised by the existing test suite. Step 4's "flip the dispatch" must not change observable behavior for any path that resolves to `repo-source` target class. The smoke verification is a clean test pass + a re-audit producing the same finding set on a known-stable commit.
- **Forcing-function check:** post-step-5, the audit dashboard's "Autonomous Reach" panel drops from 1109 abandoned to ≤90 (the 89 abandoned on `intent_pattern_validators.py × modularity.unix_philosophy` remain; that's a separate concern). The Governor Inbox indeterminate count drops by the ~80 findings tied to the three forcing-function files.
- **Future-move check:** a deliberately-incomplete `governed-artifact` IntentGuard tier (one rejecting all `.intent/` writes from `src/` capabilities) is added as the placeholder. Writes from `src/` to `.intent/foo.yaml` are denied with a "governed-artifact: API-mediated only" reason. This is observable today via a single unit test and verifies the API move's hook is present before the API itself ships.
- **No-regression check on parallel chokepoints:** post-migration, the `governance.mutation_surface.filehandler_required` blocking rule fires on zero `src/` files (modulo the autonomous-test-gen prototypes which are a separate quarantine). Any new finding on this rule indicates a regression — either a new bypass site introduced, or a target-class derivation defect.

## Out of scope

- The `.intent`/`.specs/` API itself. This ADR reserves the matrix cell; the API needs its own ADR specifying endpoint shape, auth model, META validation policy, and the governance-confirmation-gate replacement.
- The `intent_pattern_validators.py × modularity.unix_philosophy` 89-row abandoned cluster. Different rule, different concern — file is too large, not bypassing the channel. Tracked separately.
- The `cli.standard_verbs` sensor-emission path-duplication bug (75 indeterminate findings inflated to 17 distinct files). Orthogonal sensor fix; filed separately.
- Refinement of the `repo-source` boundary to distinguish `src/` from `tests/`. Both currently classify as `repo-source` with identical behavior; a future ADR can split if test-side semantics diverge.

## References

- `papers/CORE-Capability-Scoped-Filesystem-Authority.md` §4 (one door), §5 (least authority), §6 (default-on-uncertainty), §7 (capability identity), §8 (block-tier reshape).
- ADR-079 — Chokepoint implementation; D1 (FileHandler is the chokepoint), D2 (capability via `_executor_token`), D3 (op-class derivation, internal).
- ADR-080 — FS op-class vocabulary split (write/read axes; create/modify/delete sub-axes).
- ADR-071 D2.2 — Worktree sandbox propagation; `write_validated_bytes` precedent generalized here.
- ADR-077 §6 — Protected-namespace access blocking-dial sequencing.
- ADR-078 — Operational-capability taxonomy; `fs_profile` per-capability authorization data.
- ADR-096 D3 — Shadow KG materialization; the call site forcing this ADR.
- Issue #593 — Exclude-logic glob bug; landed in the same session, orthogonal but reinforcing: that fix stops the *historical-orphan* re-emission; this ADR stops the *legitimate-write* re-emission.
- Memory: `[[two-surface-requires-two-structures]]` — the principle this ADR deliberately rejects when applied to writes (target classes share one structure with parameterized behavior, not two parallel structures).
- Memory: `[[sanctuary-before-exclude]]` — the principle this ADR satisfies structurally; ephemeral writes are routed through sanctuary (the channel) rather than excluded from the rule.

---

## Notes

### Note 2026-06-08 (post-acceptance, step 1 implementation) — META-schema vs enum-extension correction

D2's text says: *"A new artifact `target_class_boundaries.yaml` enumerates the class prefixes. ... Loader pattern follows ADR-077 / ADR-078; META schema lives at `.intent/META/target_class_boundaries.schema.json`."*

Step 1 reconnaissance against the sibling pattern (ADR-077's `filesystem_operations.yaml`, ADR-078's `operational_capabilities.yaml`) showed those two halves of D2 don't agree. The "Loader pattern follows ADR-077 / ADR-078" line is correct; the "META schema lives at `.intent/META/target_class_boundaries.schema.json`" line was wrong. The siblings do not have individual META schema files — they extend `.intent/META/enums.json` with their op-class enum, and validation lives in the loader (fail-closed per ADR-068 pattern).

Step 1 followed the sibling pattern as actually used in ADR-077 / ADR-078:

- `.intent/META/enums.json` extended with a new `target_class` definition (enum: `repo-source`, `runtime-output`, `ephemeral-scratch`, `governed-artifact`). Authority cite in the definition's description: ADR-097 D2.
- `.intent/taxonomies/target_class_boundaries.yaml` declares ordered `boundaries:` (prefix → target_class) + a `default:` fallback. The YAML ordering invariant (var/tmp/ before src/, .intent/ + .specs/ before src/) is what structurally forecloses the substring bug.
- `src/shared/infrastructure/intent/target_class.py` is the sole sanctioned reader. Public surface: `load_target_class_boundaries(repo_root=None)`, `resolve_target_class(rel_path, repo_root=None)`, `reset_target_class_cache()` (test-only). Fail-closed on every structural deviation (`TargetClassBoundariesError`).
- `tests/shared/infrastructure/intent/test_target_class.py` — 30 tests covering live classification, the substring-bug structural guard, and fail-closed semantics. All green.

D2's original text is preserved as-written per [[append-only-amendments-under-review]] — readers consulting future drafters should follow this Note for the realized shape. No new `.intent/META/target_class_boundaries.schema.json` file exists; the enum-extension in `enums.json` is the contract.

Subsequent steps (2–7) of the Migration section remain as drafted.

### Note 2026-06-08 (post-acceptance, step 6 implementation) — target-class framing of `write_validated_bytes` retirement was wrong

D4 (Deprecation path) and Migration step 6 both say: *"`write_validated_bytes` specifically retires: its semantics (skip-validation for sandbox-propagated content) become `ephemeral-scratch` target-class behavior under the new dispatch, with no caller-side opt-in needed."*

Step 6 reconnaissance against the realized D2 dispatch showed this framing was wrong. D2 (as realized in `resolve_target_class` and pinned in `intent_guard.check_transaction`) classifies target class by the *resolved repo-relative path*, not by the call's semantic intent. The sandbox propagation target is the *production tree* (`src/foo.py`, `tests/test_bar.py`) — it classifies as `repo-source`, never as `ephemeral-scratch`. The ADR's step-6 wording confused the *origin* of the bytes (a worktree sandbox under `var/tmp/`) with the *destination* of the write (the main tree's `src/`).

The retirement is still correct, but the mechanism is different:

- `write_validated_bytes` was an *optimization* — it skipped duplicate IntentGuard validation that the sandboxed action had already passed — not a *semantic requirement*. The validation rules are AST/glob/regex on path + content; on bytes-identical re-application against the same `.intent/` state, they pass again.
- The migration is therefore: `sandbox_lifecycle.py` calls `file_handler.write(rel, src.read_bytes())` directly. The unified `write` resolves the target as `repo-source`, skips source-shape transforms (bytes content takes the bytes branch — `ast.parse` and `_ensure_id_anchors` are str-only), and runs IntentGuard at the repo-source tier. The second IntentGuard pass is idempotent and adds bounded latency (O(modified files) per execute()), not a behavioral change.
- The named exception named in ADR-071 D2.2 dissolves not into `ephemeral-scratch` but into "we accept idempotent re-validation at the repo-source tier for sandbox propagation." The single-channel property holds; no new target class or caller-side opt-in is needed.

D4 and step-6 original text are preserved as-written per [[append-only-amendments-under-review]] — readers should follow this Note for the realized shape.

Carry-on items (not landed in step 6, surfaced for follow-up):

- ADR-079 D8 ("Keep `write_validated_bytes` as the sanctioned bypass") and the planned audit rule `governance.chokepoint.write_validated_bytes_sole_caller` are superseded by this retirement. ADR-079's D8 text and audit-rule references need either an append-only supersession Note or, if D8 is the only block on a fuller ADR-079 closure, a closure marker. Filed for the next session's `.specs/` sweep.
- The latency cost of the second IntentGuard pass on sandbox propagation has not been measured. Action propagation runs are typically O(1–10) files; the pass is path/content-based with no LLM hop. The cost is expected to be sub-second; no benchmark filed.
