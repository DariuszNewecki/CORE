---
kind: adr
id: ADR-166
title: 'ADR-166 — Two governed write surfaces: FileHandler inside the repository, one governed external-target writer outside it'
status: accepted
---

<!-- path: .specs/decisions/ADR-166-two-governed-write-surfaces.md -->

# ADR-166 — Two governed write surfaces: FileHandler inside the repository, one governed external-target writer outside it

**Date:** 2026-10-02 (revision 5: governor chose option A — the `.intent/` line is drawn by whose law it is; promotion never overwrites; D5a argument positions; key storage via the Body writer)
**Status:** Accepted 2026-10-02 (revision 5)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-10-02, after the canary_janitor ruling)
**Grounds:** `governance.mutation_surface.filehandler_required` and `governance.logic_mutation.governed` (blocking); `architecture.execution_write.repository_containment`; `architecture.shared.no_layer_imports`; ADR-097 (single write channel); ADR-111 D3 (BYOR lane, never overwrite a constitution); ADR-119 D5 (mandatory human ratification); ADR-123 D1 (staging); ADR-126 (FileHandler in Body, Shared contract); ADR-130 D1 (the `.intent/` hard invariant is unconditional and permanent); ADR-137 (sanctuary register).
**Relates:** ADR-147 note 2026-10-02 (canary_janitor onto FileHandler); ADR-077 (filesystem-operations taxonomy); #937 (`keygen` cannot write `.intent/keys`).

### Revision 2 — what changed and why

An external review of revision 1 was checked claim by claim against the code; all five points
held. Revision 1 built its inventory from the exclusion comments and one detector, and both
were unreliable: it classified whole files where operations differ, missed the sanctuary
register (ADR-137) and a write no register mentions, repeated an exclusion's "circular"
justification without checking it, implied FileHandler could serve `.intent/keys`, and trusted
a write-mode detector that is wrong. This revision re-derives the facts from the code.

### Governor rulings (2026-10-02) incorporated in revision 3

1. **Rule amendment — agreed in principle.** FileHandler remains the sole write surface within
   the bound repository; the Body external writer covers explicitly authorised bootstrap,
   delivery and evidence operations, preserving ratification and containment guarantees;
   runtime writes to the bound repository's `.intent/` remain prohibited. The exact amendment is
   in Appendix A and is **not applied** until the governor approves the text.
2. **Tracing — action log per operation; blackboard per Worker run** (D2, "Trace").
3. **Key storage — operator-owned storage outside the Git checkout**, implemented separately
   under #937 (D4).

The ADR stays **proposed** until the governor has reviewed this text and Appendix A.

### Governor corrections (2026-10-02) incorporated in revision 4

1. **The `.intent/` line is drawn by whose law it is, not by who calls.** Revision 3 exempted
   "operator-invoked" writes by calling them non-runtime — a loophole, since by that logic a CLI
   command could rewrite CORE's own constitution. Revision 4 then staged *every* such write,
   including into an adopter's own repository. The governor chose option A (2026-10-02):
   - **CORE's own `.intent/`** — no code path writes it (ADR-130 D1: IntentGuard's block is
     unconditional). Changes are staged and applied by the governor (ADR-130 D2 pattern).
   - **An adopter's `.intent/`** — written only by the external-target writer's declared
     delivery operations (ADR-149, ADR-111 D3, ADR-119 D5), which refuse CORE's own source
     checkout. ADR-130 D1 governs CORE's protection of *its* law; delivering an adopter's own
     constitution on the adopter's explicit command is the feature ADR-149 defines, not a bypass
     of IntentGuard. This is the 2.11.0 behaviour of `adopt-pack --write`, which stands.
2. **No overwrite on stage promotion.** ADR-123 permits overwriting the *staging directory*,
   not an existing target constitution; promotion refuses when the target `.intent/` exists
   (ADR-123 D2 step 2).
3. **D5a argument positions.** `tarfile.open(name, mode, …)` takes mode second, like builtin
   `open`; only `Path.open(mode, …)` takes it first.
4. **Key storage reuses the Body writer** through a narrowly declared key-storage operation
   (#937), rather than a separate direct-write implementation.

---

## Context

The rule's statement is absolute: "All filesystem writes MUST route through FileHandler."
Three mechanisms let code bypass it today:

1. **Mapping exclusions** — 15 production files, mirrored in `mutation_surface.yaml` and
   `governance_basics.yaml` (the two lists agree on every `src/` entry).
2. **Sanctuary register** — `.intent/enforcement/sanctuaries.yaml` (ADR-137) records sites the
   detector cannot see: `action_logger.py` (append) and `cli/resources/coherence/seed.py`
   (streaming JSONL export).
3. **Detector blind spots** — sites no register mentions because the rule never fires on them.

### Inventory by operation (`main@2bc17484`)

Derived from the code, per operation, not per file. "Inside" = inside CORE's repository.

| Site | Operation(s) | Target | Notes |
|---|---|---|---|
| `cli/logic/byor.py:172–173` | mkdir, write_text | **outside** (target `.intent/`) | `deliver_external_intent_files` (adopt-pack) |
| `cli/logic/byor.py:301–302` | mkdir, copy2 | **inside** (`work/staged/`) **or outside** (target) | `initialize_repository`, stage vs direct mode (ADR-123 D1) |
| `cli/logic/byor.py:413–414` | mkdir, copy2 | **outside** (target) | `promote_staged` |
| `cli/logic/byor.py:427` | rmtree | **inside** (`work/staged/`) | stage cleanup after promote |
| `cli/logic/scout.py:242` | unlink | **outside** (target `.intent/`) | `--reset` of inducted rules |
| `cli/logic/scout.py:714` | unlink | **inside** (candidate cache) | the same cache is *written* through FileHandler (`:700`) |
| `cli/logic/scout.py:1029–1030` | mkdir, write_text | **outside** (target `.intent/`) | ratified rules (ADR-119 D5) |
| `cli/logic/project_scaffold.py:147–152` | mkdir, copy2, write_text | **outside** (new project) | `project new` |
| `cli/logic/demo/isolation.py:70–72, 215–216` | mkdir, write_text | **outside** (`CORE_DEMO_STATE_DIR`) | ADR-155 |
| `shared/infrastructure/intent/target_intent_assembly.py` (19 operations) | mkdir, write_text, copyfile, **move** | **outside** (evidence root) | execution copy; `move` keeps displaced floor files (#894) |
| `body/services/crate_processing_service.py:157–244` | rmtree, mkdir, write_text, symlink, copy2 | **inside** (`work/canary/`) | canary snapshot |
| `shared/infrastructure/git_service.py` | mkdir, rmtree | **inside** (`var/tmp` worktrees) | unreachable from shared/ |
| `shared/infrastructure/context/cache.py` | mkdir, unlink ×4 | **inside** (`work/context_cache`) | unreachable from shared/ |
| `shared/path_utils.py` | mkdir, write_bytes | caller-supplied | unreachable from shared/ |
| `shared/infrastructure/validation/ruff_linter.py` | write_text | **inside** (`var/tmp`) | unreachable from shared/ |
| `shared/infrastructure/storage/integrity_service.py` | mkdir, write_text | **inside** (`var/integrity/`) | hashes `src/`; see Finding 3 |
| `shared/action_logger.py:58` | `Path.open("a")` | **inside** (`var/logs`) | sanctuary; **detector-blind** |
| `cli/resources/coherence/seed.py:214` | `Path.open("w")` streaming | operator-chosen output path | sanctuary; **detector-blind** |
| `body/maintenance/scripts/context_export.py:137` | `tarfile.open(mode="w:gz")` | caller-supplied | **detector-blind; in no register** |
| `body/governance/key_management_service.py` | `os.chmod` | **inside** (`.intent/keys`) | the preceding write is refused by IntentGuard — `keygen` fails today (#937) |
| `will/test_generation/sandbox.py` | — | — | excluded, but no direct write: **dead exclusion** |

### Findings that shape the decisions

1. **"Outside the repository" is a property of an operation, not a file.** `byor.py` and
   `scout.py` each write both inside CORE and into a target.
2. **Most in-repo bypasses are in `shared/`, where FileHandler is unreachable by law**
   (`shared/` may not import `body/`; FileHandler is in `body/` since ADR-126).
3. **`integrity_service` has no bootstrap cycle.** Nothing in FileHandler or IntentGuard uses
   it; its callers are `will/governance/integrity_runner.py` and
   `body/maintenance/idempotency_harness.py`. The exclusion's "circular" comment is unsupported.
4. **The write-mode detector is wrong both ways.** `_is_write_mode` returns true when *any*
   string argument contains `w` or `a` (so a read of `"data.json"` would count as a write) and
   misses `x` and `r+`. It also only watches the builtin `open`, not `Path.open` or
   `tarfile.open`. Three real writes are invisible today (table rows marked detector-blind).
5. **Exclusions decay.** canary_janitor's reason was false from July (#772) to 2026-10-02;
   `sandbox.py` is excluded but writes nothing.

---

## Decisions

### D1 — Inside the bound repository, FileHandler is the only write surface

Every write whose target resolves inside the bound repository goes through FileHandler. FileHandler
itself is the only in-repository exclusion. This includes `integrity_service` (Finding 3): it
migrates through D3 unless a concrete dependency chain proving a cycle is produced, in which case
the ADR is amended with that chain — a renamed exclusion is still a bypass. No "raw mode" is added
to FileHandler.

### D2 — Outside the repository, one governed external-target writer

**Scope.** The writer never writes CORE's own `.intent/` (it refuses CORE's source checkout,
`core_source_root()`). It writes outside the bound repository and into an **adopter
repository's** `.intent/` — including when the adopter's repository is the one CORE was invoked
in, as with `adopt-pack` in a pip install. It serves only explicitly authorised operations of
these kinds:
**bootstrap** (`project new`, `project onboard` floor delivery into a target), **delivery**
(`adopt-pack` and ratified scout rules into a *target* repository, staged-constitution
promotion), **evidence** (the external-run execution copy and its manifests, demo isolation
state) and **key storage** (the #937 operation writing private keys to `KEY_STORAGE_DIR`). Each authorised operation is named in
the writer's own declaration; an operation not on that list is refused.

**Implementation in Body, contract in Shared** (consistent with ADR-126): `shared/protocols/`
declares `ExternalTargetWritePort`; a Body module implements it; callers in `cli/` receive the
implementation, and `shared/` callers (`target_intent_assembly`) receive it by injection.

It is a *governed* surface, not just a contained one. Containment (explicit target root; refuse
CORE's own checkout via `core_source_root()`, system directories, and paths escaping the root) is
necessary but does not establish permission. The writer therefore:

- **refuses to overwrite an existing target constitution**, with no exception — stage
  promotion included: promotion refuses when the target `.intent/` exists (ADR-111 D3,
  ADR-123 D2). Overwriting is permitted only for the staging directory itself (ADR-123 D1);
- **accepts ratified rule content only** for scout delivery — the caller passes the ratification
  record, and the writer refuses unratified rule files (ADR-119 D5);
- **keeps the execution-copy restrictions** of `target_intent_assembly` (#894: evidence root
  must be fresh, displaced floor files preserved, never written back to the subject);
- **records every operation and every refusal** — see *Trace* below.

**Trace.** Every external write and every refusal produces one structured **action-log** record:
caller and run identity, resolved target path, operation, and outcome (written / refused with
reason). Content is never logged — no file bodies, and never private-key or secret material.
CLI and bootstrap operations log without acquiring a database dependency for it. A Worker that
uses the writer includes a summary (counts by outcome) and a trace reference in its existing
blackboard completion report — one blackboard entry per Worker run, not per operation. A failure
to write the trace is surfaced explicitly (reported to the caller and logged at error), never
swallowed.

Each guarantee carries a refusal test; those tests, not the exclusion list, are the proof the
guarantees hold.

**Rule amendment required.** `governance.mutation_surface.filehandler_required` currently says
*all* writes. The exact amendment is in **Appendix A** (a Path A change to
`.intent/rules/architecture/mutation_surface.json`, applied only after governor approval of
the text). `governance.logic_mutation.governed` already reads "governed mutation surfaces"
(plural, `src/` only) and needs no change.

### D3 — shared/ reaches FileHandler through a write port

`shared/protocols/` declares a narrow `RepoWritePort` (write, append, ensure_dir, remove_file,
remove_tree, set_mode, streaming open for write). FileHandler implements it. `git_service`,
`context/cache`, `path_utils`, `ruff_linter`, `action_logger` and `integrity_service` receive it
by injection from their composition roots. No shared→body import is introduced.

### D4 — FileHandler closes its capability gaps without loosening a guard

FileHandler gains:
- **append** — for `action_logger`;
- **streaming write** (a context-managed handle, target-class guarded at open) — for
  `coherence/seed.py`; append alone does not migrate a streaming writer;
- **set_mode** — permission changes, subject to the same guard as writes.

**`.intent/` stays refused.** `set_mode` must not make `.intent/keys` writable; ADR-130 D1 is
unconditional. `keygen` is broken today for exactly that reason (#937).

**Whose `.intent/`.** FileHandler never writes any `.intent/`. CORE's own `.intent/` is changed
only by the governor applying staged files (ADR-130 D2, e.g. `intent sync vocabulary --write`).
An adopter's `.intent/` is changed only by the external-target writer's declared delivery
operations — so `adopt-pack --write` run inside the adopter's own repository keeps its 2.11.0
behaviour, now behind the writer's refusals and trace.

**Key storage (governor ruling, implemented under #937, not by this ADR).** Private keys live in
operator-owned persistent storage outside the Git checkout, at the configurable
`KEY_STORAGE_DIR`; a location under `.intent/` is rejected. On Unix the directory is created 0700
and private-key files 0600 from the outset (no write-then-chmod window). Overwrite is refused by
default. The governor records the public key in `.intent/` by hand. Because that storage is
outside the repository, key writes go through the **external-target writer as a narrowly
declared key-storage operation** (governor ruling): target root `KEY_STORAGE_DIR` only, refuse
any path under `.intent/`, create with 0700/0600 modes, refuse overwrite by default, and trace
the operation without its content.

### D5 — The exclusion and sanctuary lists are closed and checked

After migration, the production excludes of both mappings equal exactly {`file_handler.py`,
the external-target writer module}, and `sanctuaries.yaml` holds no entry for this rule. A
standing test asserts: (a) the two mirrored lists agree; (b) they equal that declared set;
(c) every excluded or sanctuary site still contains a direct write (catches **dead** entries).

That test does **not** prove a justification is still true — canary_janitor's exclusion was
alive and wrong. The proof that a reason holds is a boundary or refusal test owned by the
surface (D1's containment tests, D2's refusal tests). Adding an exclusion requires amending
this ADR.

### D5a — Fix the detector before trusting the inventory

1. Replace `_is_write_mode` with a parser of the actual mode argument — the **second**
   positional argument for builtin `open(file, mode, …)` and `tarfile.open(name, mode, …)`, the
   **first** for `Path.open(mode, …)`, or the `mode=` keyword in all three — treating `w`, `a`,
   `x` and `+` as writes and never inspecting the file-name argument.
2. Add `Path.open` (leaf) and `tarfile.open` (qualified) to
   `.intent/taxonomies/filesystem_operations.yaml` with that predicate.
3. Re-run the inventory; any newly visible site joins the migration.

Regression tests: `open("data.json")` is not a write; `open(p, "x")` and `open(p, "r+")` are;
`p.open("a")`, `tarfile.open(p, "w:gz")` and `tarfile.open(p, mode="w:gz")` are;
`tarfile.open(p)` is not.

### D6 — Migration in units, each removing its own exclusion

Each unit migrates one site or group, deletes its exclusion or sanctuary entry in the same change,
and shows the control (the rule fires on the old code once the entry is gone, as done for
canary_janitor). Cheapest first:

1. D5a detector fix + re-inventory; remove the dead `sandbox.py` exclusion.
2. In-repo, already in Body: `crate_processing_service`; `scout.py:714` (cache eviction — the
   cache is already written through FileHandler).
3. D4 capabilities; migrate `action_logger`, `coherence/seed.py`, `context_export.py`.
4. D3 `RepoWritePort`; migrate `git_service`, `context/cache`, `path_utils`, `ruff_linter`,
   `integrity_service`.
5. D2 external-target writer with its refusal tests; migrate the outside operations of
   `byor.py`, `scout.py`, `project_scaffold.py`, `demo/isolation.py`,
   `target_intent_assembly.py`; route `byor.py:427` (stage cleanup, inside) through FileHandler.
6. Rule amendment (D2); the D5 test switches from reporting to failing on drift.

`key_management_service` leaves the list when #937 is decided.

## Consequences

- Production bypasses go from 15 exclusions + 2 sanctuaries + 3 invisible sites to 2 declared
  surfaces.
- Every in-repo write gains IntentGuard, containment and target-class tiering; every external
  write gains one set of refusals with tests, instead of five near-copies.
- `core_source_root()` and the BYOR guards move from `cli/logic/byor.py` into the Body
  implementation (behaviour unchanged, call sites updated).
- The rule statement changes from "all writes" to "inside → FileHandler, outside → writer".

## Verification

- Per unit: the control on the old code, the unit's tests, the D5 test.
- D2: one refusal test per guarantee (overwrite, unratified rules, execution-copy rules,
  CORE checkout, system directory, root escape).
- End state: the fixed detector reports no direct write in `src/` outside the two surfaces.

## Open questions for the governor

None — revision 5 and Appendix A approved by the governor 2026-10-02; Appendix A applied.

---

## Appendix A — Exact rule amendment (applied 2026-10-02)

File: `.intent/rules/architecture/mutation_surface.json`. Only `metadata.version`,
`statement` and `rationale` change; `id`, `enforcement` (blocking), `authority` and `phase`
are unchanged.

**`metadata.version`:** `"1.0.0"` → `"1.1.0"`

**`statement`, current:**

> All filesystem writes MUST route through FileHandler. Direct calls to write_text(),
> write_bytes(), or open() in write/append mode are prohibited in production code.

**`statement`, proposed:**

> All filesystem writes MUST route through FileHandler, except the declared operations of the
> governed external-target writer (ADR-166). No code path writes CORE's own .intent/
> (ADR-130 D1): changes to it are staged and applied by the governor. The external-target writer
> writes outside the bound repository and into an adopter repository's .intent/, only for its
> declared bootstrap, delivery, evidence and key-storage operations, and refuses CORE's own
> source checkout. Direct calls to write_text(), write_bytes(), open() or Path.open() in a
> write, append or create mode, and other filesystem-mutation primitives, are prohibited in
> production code outside these two surfaces.

**`rationale`, current:**

> Direct filesystem writes bypass constitutional governance, audit trails, impact
> classification, and IntentGuard enforcement. FileHandler is the sole governed mutation surface.

**`rationale`, proposed:**

> Direct filesystem writes bypass constitutional governance, audit trails, impact
> classification, and IntentGuard enforcement. FileHandler is the governed mutation surface for
> the bound repository and refuses writes outside it by design (repository containment). The
> external-target writer is the only governed surface outside it: it serves only declared
> operations, preserves containment, mandatory ratification (ADR-119 D5), never-overwrite
> (ADR-111 D3, ADR-123 D2) and the execution-copy restrictions, and records every write and
> refusal in the action log. Neither surface writes CORE's own .intent/ (ADR-130 D1).

**Whose law, not who calls.** The statement names no caller-based exception. It distinguishes
CORE's own `.intent/` (never written by code, ADR-130 D1) from an adopter's `.intent/` (written
only by the writer's declared delivery operations, which refuse CORE's source checkout), per
the governor's option-A ruling of 2026-10-02.

---

> **Note (2026-10-02, unit 1 landed):** with the corrected detector (D5a) the re-inventory found
> two sites, not three. `body/maintenance/scripts/context_export.py:137` was **wrongly** listed
> as a detector-blind write: it is `tarfile.open(fileobj=buffer, mode="w:gz")` into an in-memory
> buffer that is then persisted through `FileHandler.write_runtime_bytes` — already governed. The
> detector treats `tarfile.open(fileobj=…)` as not a filesystem write. `cli/resources/coherence/seed.py`
> was migrated in the same change (the D4 streaming write, `FileHandler.open_text_for_write`,
> moved forward from unit 3 so the newly visible blocking finding did not land unresolved), and its
> sanctuary entry was removed. The dead `will/test_generation/sandbox.py` exclusion was removed
> from both write rules. `action_logger`'s append is now detectable; its mapping exclusion still
> covers it until unit 3.
