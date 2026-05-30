# ADR-077 — Config-driven protected-namespace access with an introspective filesystem-operation taxonomy

**Date:** 2026-05-30
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (protected-namespace access session 2026-05-30)
**Grounding paper:** `papers/CORE-Enforcement-Completeness.md` (runtime↔audit complement and completeness-against-runtime-reality principle this ADR implements); `papers/CORE-IntentGuard.md` (the runtime Gate whose reach gap motivates the audit-time check)
**Related:** ADR-066 (`_check_all_rules_mapped` completeness precedent), ADR-068 (taxonomies/ precedent — `cognitive_roles.yaml`), ADR-075 (`_check_namespace_manifest_completeness` precedent — D7), rule `architecture.intent.non_gateway_no_direct_resolution` (the rule this generalizes)

---

## Context

The trust claim CORE rests on — *operational CORE cannot mutate its own constitution* — was found to be enforced only narrowly:

- `IntentGuard` blocks writes under `.intent/` as a tier-1 invariant, but **only for writes routed through `FileHandler`**. A raw `pathlib.Path(".intent/x").write_text(...)` never reaches the guard.
- Two ast_gate checks split the audit-time backstop along orthogonal axes, and neither is namespace-aware-and-write-aware at once. `direct_intent_access` is namespace-aware (`.intent/` hardcoded) but inspects only read/traverse/parse — writes are invisible to it; `open()` is matched mode-agnostically as a read. `no_direct_writes` is write-aware but namespace-blind: it requires `FileHandler` globally, so protected namespaces are covered only as a side effect, and only as fully as that rule itself. Its baseline plus `governance_basics.yaml`'s `forbidden_additional` cover `write_text`/`write_bytes`/`open(w|a)`/`unlink`/`rmdir`/`os.{replace,rename,remove,unlink,rmdir}`/`shutil.{copyfile,copy,copy2,move,rmtree}`/`aiofiles.open`, but leaves three live bypasses that reach protected namespaces directly:
  - **Variable-receiver form** on `write_text`/`write_bytes`: matching uses `full_attr_name`, so `Path("x").write_text(...)` is caught but `p = Path("x"); p.write_text(...)` is not. `unlink`/`rmdir` already use leaf-match and catch both forms.
  - **Uncovered write calls**: `mkdir`, `makedirs`, `touch`, `symlink`, `link`, `chmod` are in neither set.
  - **Bare-import form**: `from os import replace; replace(...)` bypasses `full_attr_name` matching on the module-rooted set.
- `.specs/` has no equivalent protection at all (no guard invariant; not in `direct_intent_access`'s hardcoded namespace; covered only transitively by `no_direct_writes`, with the three bypasses above).
- The checks' protected-namespace literals and operation call-sets are **hardcoded `ClassVar` frozensets** in `intent_access_check.py` and implicit baselines in `purity_checks.py`, invisible to governance.

A full inventory of `src/` found ~340 non-gateway filesystem call sites. Of these, ~80% are already covered by an existing gateway method (pure migration); writes targeting a governance namespace number **one** (`cli/resources/intent/sync_vocabulary.py`, the vocabulary regen tool); there is **no** async filesystem usage; `src/api/` has zero direct FS calls.

The root cause is a *class* of defect, not a single miss: enforcement vocabulary that is **hardcoded, invisible, and unverified for completeness**. The original `_READ_CALLS` set leaked not because it lived in code, but because nothing asserted it was complete and nothing made it visible. Relocating it to YAML alone would reproduce the same silent-incompleteness in a more visible place.

## Decision

### 1. The access policy becomes config-driven
Protected namespaces, forbidden operation-classes, and allowed callers are read from rule params, not hardcoded:

- `protected_markers: list[str]` — namespaces under protection (e.g. `[".intent", ".specs"]`).
- `forbidden_classes: list[str]` — which operation-classes are forbidden for those namespaces.
- allowed callers — remain in the rule's `scope.excludes`, unchanged.

Adding a namespace, forbidding a new class, or sanctioning a caller becomes a governor YAML edit.

**Matching technique is declared per taxonomy entry, not by the check.** Each entry carries a `match` field selecting `leaf` (matches `n.func.attr`; catches both `Path("x").method()` and `p.method()`) or `qualified` (matches `ASTHelpers.full_attr_name(n.func)`; the dotted form, e.g. `os.replace`). `pathlib.Path` methods (`write_text`, `write_bytes`, `mkdir`, `touch`, `symlink_to`, `hardlink_to`, `chmod`, `unlink`, `rmdir`) register as `leaf` — their leaf names are unambiguous and leaf-match closes the variable-receiver bypass that today's `full_attr_name`-only matching for `write_text`/`write_bytes` leaves open on the call axis. Module-rooted families (`os.*`, `shutil.*`, `tempfile.*`, `aiofiles.*`, builtin `open`) register as `qualified` because their leaves (`replace`, `move`, `copy`) collide with non-FS methods (`str.replace`, `dict.copy`). Builtin `open` additionally carries `predicate: write_mode` so the existing `_is_write_mode` gate is preserved. Bare-import forms (`from os import replace`) bypass `qualified` matching at parse time and remain an open gap closed only by import-tracking; tracked as #488, out of scope for this ADR.

**Closing the variable-receiver bypass requires both axes.** The leaf/qualified `match` field closes the **call axis** — `p.write_text(...)` is recognized as a write. The **namespace axis** — tying that call to a `protected_markers` literal whose binding sits on a different statement — is closed by reusing `IntentAccessCheck`'s `tainted_names` propagation (`intent_access_check.py:78-86`): Pass 1 accumulates tainted bindings from `Assign`/`AnnAssign`/`AugAssign`, Pass 2 consults the set via `_expr_is_intent_related`. The new check inherits that machinery rather than reproducing it. Either axis alone leaves the bypass open — call axis without taint, namespace axis without leaf-match. The closure covers the straight assign-then-call form; textually-reordered multi-hop derivations (intermediate assignment after usage) remain open per #119 gap 4, inherited from the same machinery.

**The new check supplements `no_direct_writes`, not replaces it.** The two enforce different rules: `no_direct_writes` is mutation-surface (FileHandler required globally, namespace-blind); the new check is namespace-access (`forbidden_classes` for specific `protected_markers`). They coexist. Convergence-direction follow-up: migrate `no_direct_writes`' baseline and per-mapping `forbidden_additional` to read from the same taxonomy so the two checks share one canonical name source — that closes the variable-receiver and uncovered-calls bypasses for `no_direct_writes` as a side effect of the `leaf`/`qualified` declarations above. Out of scope for this ADR; tracked as #489.

### 2. The filesystem-operation vocabulary becomes a governed taxonomy
The mapping of `call-name → op-class` is **not** code, and **not** part of `.intent/META/vocabulary.json` (that store is a paper-canonical, sha-locked governance *glossary*; hosting FS-ops there is the `vocabulary_canonical_store` vs `enums.json` category error already on the surface ledger).

It lives as a closed-set taxonomy, mirroring the `cognitive_roles.yaml` precedent:

- store: `.intent/taxonomies/filesystem_operations.yaml`
- op-class enum: declared in `.intent/META/enums.json`, `$ref`-ed, fail-closed on empty.
- sanctioned loader: `src/shared/infrastructure/intent/filesystem_operations.py`, mirroring `vocabulary_projection.py` (returns healthy / drift / broken). No source-hash — there is no canonical paper to defend; the authority is the stdlib plus the governor's classification.
- a `regex_gate` no-direct-import rule keeps every other module out of the taxonomy file, mirroring `governance.vocabulary.no_direct_json_import`.

Op-classes:

| op-class | meaning | anchor call |
|----------|---------|-------------|
| `read` | reads file content from disk | `Path.read_text` |
| `traverse` | enumerates directory entries | `Path.glob` |
| `parse` | parses structured content from a path-typed or path-derived argument | `yaml.safe_load(path)` |
| `write` | mutates filesystem state — content, structure, or metadata | `Path.write_text` |
| `neutral` | pure construction or string operations with no filesystem effect | `Path("x")`, `os.path.join` |

`write` admits the three sub-shapes deliberately: content (`write_text`/`write_bytes`), structure (`mkdir`/`makedirs`/`unlink`/`rmdir`/`rename`/`replace`/`move`/`symlink`/`link`/`touch`), metadata (`chmod`). All three are forbidden under `forbidden_classes: [write]` without further distinction. `parse` is broader than path-typed: `_expr_is_intent_related` (`intent_access_check.py:194`) recurses through call args, so `yaml.safe_load(open(p).read())` is caught the same way as `yaml.safe_load(p)` when `p` is protected-namespace-tied.

### 3. An introspective completeness check guards the taxonomy
A module-level `_check_fs_operations_completeness` in `artifact_gate.py` (artifact_gate engine, **not** a new engine, **not** a CCC check) performs a declared-vs-discovered set-difference, the same shape as `_check_all_rules_mapped` (ADR-066) and `_check_namespace_manifest_completeness` (ADR-075 D7). The novel side is that *discovered reality* is stdlib introspection:

- **`pathlib.Path`**: every public method must be classified. A method present in the runtime but absent from the taxonomy is a finding. This makes `Path` additions auto-surface — the most likely growth surface, and the one the inventory showed dominates.
- **`os`, `shutil`, `tempfile`, builtin `open`**: a curated *watched set* in the taxonomy. The check verifies each watched name still resolves to a callable in its module (catches stdlib rename/removal) and is classified. It does **not** auto-discover new FS members here — introspection cannot separate FS from non-FS in these mixed namespaces.

Remediation for this check is `manual_review` (per the #418 mapped-rules invariant): classifying a newly surfaced call is a governance decision — is it a read or a write? — and therefore a governor interrupt, not auto-remediation.

### 4. Guarantee boundary (stated, not overclaimed)
- **Drift-proof** for `pathlib.Path`: a new method cannot pass unclassified.
- **Integrity-checked** for the curated `os`/`shutil`/`tempfile`/`open` surface: existence + classification are verified; new FS members in those modules still require a human to add them to the watched set.
- **Watched-set gaps are dual-impact.** Because the audit check reads its `forbidden_classes` from the taxonomy, a write-class call missing from the watched set has no `op_class` — and `forbidden_classes: [write]` cannot route it. The same omission is therefore both a completeness gap (the check doesn't see it) and an audit gap (the policy doesn't catch it). Today's `check_no_direct_writes` exemplifies the cost of leaving this implicit: its baseline plus `governance_basics.yaml`'s `forbidden_additional` cover `write_text`/`write_bytes`/`open(w|a)`/`unlink`/`rmdir`/`os.{replace,rename,remove,unlink,rmdir}`/`shutil.{copyfile,copy,copy2,move,rmtree}`/`aiofiles.open` — but silently miss `mkdir`, `makedirs`, `touch`, `symlink`, `link`, and `chmod`. The taxonomy must seed those six (and any others surfaced during initial classification) into the watched set on day one; the completeness check then prevents the next such omission from being silent.

### 5. Determinism
The taxonomy records the Python version its classification was authored against. A runtime `sys.version_info` mismatch is itself a finding ("re-verify against 3.X"), keeping the check deterministic given a version rather than silently version-dependent.

### 6. Enforcement rollout (two dials on one policy)
Sequencing — each step ships green before the next is promoted:

1. **Land the taxonomy** with the existing covered set plus the six known-missing write calls (`mkdir`, `makedirs`, `touch`, `symlink`, `link`, `chmod`). Auto-discovered for `pathlib.Path`; manually classified for `os`/`shutil`/`tempfile`/builtin `open`.
2. **Land the introspective completeness check** in `artifact_gate` and ship it green. This is the prerequisite for the blocking dial: until the check passes, the watched set's coverage of the live stdlib is unverified, and the blocking policy below would inherit any gap silently per §4.
3. **Promote the blocking dial.** `forbidden_classes: [write]` for `protected_markers = [".intent", ".specs"]`. Expected violation count ≈ 1 (the `sync_vocabulary` regen write), resolved by routing through the sanctioned governor path or by an authority-scoped exception.
4. **Advisory dial stays advisory.** `.specs/` read/traverse protection and any future widening of `protected_markers` toward all paths remain advisory until the gateway gains the missing read methods (`IntentRepository`/`SpecsRepository` `exists`/`is_dir`/`list_dir`) and the ~270 mechanical migrations converge. Promotion to blocking is then a config edit.

## Consequences

- Future namespace / op-class / caller changes are governor YAML edits — the "config tuning" end state.
- A new `pathlib.Path` FS method pulls the governor in to classify it (human-in-loop precisely at the governance decision; `manual_review`).
- The ~340-site migration converges separately under the advisory broad policy — the autonomous-remediation training set, not a blocker for the trust fix.
- `IntentAccessCheck` → `ProtectedNamespaceAccessCheck` and the `check_type` router-key generalization are a follow-up cleanup commit, done after behavior is proven (it ripples through the symbol index). Tracked as #490.

## Alternatives considered

- **Vocabulary in code (status quo).** The bug-hiding pattern that triggered this. Rejected.
- **Vocabulary in `.intent/META/vocabulary.json`.** Category error: glossary schema (`kind: vocabulary`, paper-canonical, sha-locked) does not fit a stdlib classification. Rejected.
- **A CCC coherence check.** Wrong subsystem: this is config↔runtime completeness producing an `AuditFinding` (rule-bound, blackboard-routed), not document↔document coherence producing a `CoherenceCandidate`. Rejected.
- **A new engine.** `artifact_gate` already hosts "validate a declared artifact against a reference"; a new engine adds cost without capability. Rejected.
- **Curated completeness list only (no introspection).** Reproduces the silent-drift defect this ADR exists to eliminate. Rejected.
