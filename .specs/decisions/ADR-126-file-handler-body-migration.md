---
kind: adr
id: ADR-126
title: ADR-126 — Migrate FileHandler to Body and close the shared/ excludes entry
status: accepted
---

<!-- path: .specs/decisions/ADR-126-file-handler-body-migration.md -->

# ADR-126 — Migrate FileHandler to Body and close the shared/ excludes entry

**Status:** Accepted
**Date:** 2026-06-26
**Authors:** Darek (Dariusz Newecki)
**Deadline:** 2026-09-12 (inherits ADR-051 deadline)
**Supersedes:** ADR-051 (file_handler.py shared/ excludes closure)
**Closes:** Final `architecture.shared.no_layer_imports` exclude entry
**Relates to:** ADR-049 D1/D3 (doctrine-rule parity; closure ADR + deadline
requirement), ADR-051 (the closure ADR this supersedes), ADR-079 (chokepoint
capability scoping), ADR-097 (unified write channel)

---

## Context

ADR-051 deferred the structural resolution of `file_handler.py`'s Body and Mind
imports to one of two paths: Path X (sanction FileHandler as a composition root)
or Path Y (extract `MutationGuardProtocol` + relocate `ConstitutionalViolationError`
to `shared/exceptions/`). ADR-051's own framing noted the question was
"unresolved" and that neither path had been pre-judged.

A 2026-06-26 investigation against the live codebase read all three Shared files
that instantiate or reference FileHandler (`serializers.py`, `test_runner.py`,
`shadow_materializer.py`), traced the full call chains, and examined
`file_handler.py` and `file_service.py` in full. The findings change the
architectural framing materially.

### Evidence

**`shadow_materializer.py` — already correct.**
`src/shared/infrastructure/context/shadow_materializer.py` imports FileHandler
under `TYPE_CHECKING` only (line 45) and receives it as an injected constructor
parameter (`file_handler: FileHandler`). No module-load-time Body import. This
file is not a violation; it is the template for the correct pattern.

**`serializers.py` — operational service logic in Shared.**
`src/shared/infrastructure/context/serializers.py` instantiates
`FileHandler(str(settings.REPO_PATH))` at call time inside `to_yaml` to write
context cache packets to `var/`. The write is initiated by
`src/shared/infrastructure/context/cache.py` (also in Shared), which calls
`ContextSerializer.to_yaml`. The call chain from `cache.py` through
`serializers.py` to `FileHandler` is entirely operational I/O — writing runtime
artifacts, not substrate logic. It is in `shared/infrastructure/` for
accessibility, not because it satisfies Shared's admission criteria.

**`test_runner.py` — execution-tier service in Shared.**
`src/shared/infrastructure/validation/test_runner.py` executes subprocess pytest,
persists results to the DB (`get_session`), and writes operational logs to
`var/logs/tests.jsonl` and `var/reports/test_failures.json` via two FileHandler
instantiations. Its callers are Body, Will, and API. The file logging calls are
best-effort (each is wrapped in `except Exception: logger.debug(...)`). This file
has no substrate properties — it is an execution-tier service that ended up in
Shared because multiple layers call it.

**`FileService` — Body-layer thin wrapper, unchanged.**
`src/body/services/file_service.py` is a thin pass-through over `FileHandler`
that exists so Will-tier consumers and other Body components do not import
FileHandler directly. It adds no logic. FileService is correctly placed and its
role is unchanged by this ADR.

**`FileHandler` — governance-enforcement write gate.**
`src/shared/infrastructure/storage/file_handler.py` calls `get_intent_guard()`
from `body.governance.intent_guard` at construction time to build `self._guard`,
and raises `ConstitutionalViolationError` from `mind.governance.violation_report`
when `_guard.check_transaction()` rejects a write. Enforcing constitutional rules
on every file mutation is an execution-layer concern — it is not substrate logic.
FileHandler belongs in Body; it is in Shared because its Shared callers (the
context cluster and test runner) needed it there.

### Why ADR-051's paths were the wrong frame

ADR-051 accepted the wrong premise: that FileHandler belongs in Shared and the
problem is how to make its Body/Mind imports compliant. The investigation shows
the reverse is true. The Shared callers are the misfit:

- Path X (composition-root exemption) would ratify the misplacement with a new
  exemption category that would justify future violations of the same shape.
- Path Y (extract `MutationGuardProtocol`) would surgically fix `file_handler.py`
  to stay in Shared while leaving the operational service cluster in the wrong
  layer — fixing the symptom, not the cause.

The correct frame: FileHandler is a Body-tier governance-enforcement component.
It is in Shared as a consequence of Shared hosting operational service code
(the context cluster and test runner) that escaped the substrate contract. The
closure must remove FileHandler from Shared's scope, not re-justify its presence
there.

This finding is consistent with ADR-049's stated long-horizon direction:
"contraction of `shared/` to pure contracts: interfaces, data types, constants,
and nothing that depends on a layer."

---

## Decision

### D1 — FileHandler migrates to `body/infrastructure/storage/`

`src/shared/infrastructure/storage/file_handler.py` moves to
`src/body/infrastructure/storage/file_handler.py`. The Body import of
`body.governance.intent_guard` and the Mind import of
`mind.governance.violation_report.ConstitutionalViolationError` are natural at
that location: Body may import from Mind; the violation report exception is the
correct raised type for a governance rejection.

### D2 — Stage 1: inject FileHandler into the two Shared instantiators

Before the physical move, the two Shared files that instantiate FileHandler
must stop doing so. Both switch to the pattern already demonstrated by
`shadow_materializer.py`: `TYPE_CHECKING` import + injected parameter.

**`test_runner.py`:** Add an optional `file_handler` parameter to `run_tests`
and thread it into `_log_test_result_to_file` and `_store_failure_artifact`. When
the parameter is `None`, the file-write sub-steps are skipped (they are already
best-effort; the `except Exception` handlers make `None` semantically equivalent
to a failed write). Callers that want file logging pass their `FileHandler`
instance; callers that do not pass `None`. The import of `FileHandler` moves to
`TYPE_CHECKING`.

**`serializers.py` + `cache.py`:** Add a `file_handler` parameter to
`ContextSerializer.to_yaml`. Propagate it from `cache.py`'s `save` method and
from `context/service.py`, which already uses injected services via
`BrainServicesProvider` (the established pattern for this cluster). The import
of `FileHandler` in `serializers.py` moves to `TYPE_CHECKING`. `cache.py`
receives `FileHandler` from its caller; `serializers.py` receives it from
`cache.py`. No Shared file instantiates FileHandler after Stage 1.

### D3 — Stage 2: physical move of FileHandler

Once Stage 1 is complete and no Shared file instantiates FileHandler:

1. Move `src/shared/infrastructure/storage/file_handler.py` to
   `src/body/infrastructure/storage/file_handler.py`.
2. Add a re-export shim at the old path during migration to keep callers green:
   `from body.infrastructure.storage.file_handler import FileHandler, FileOpResult`.
   The shim is removed once all callers have been updated (D4).
3. Update `FileService` to import from the new path.
4. Update `shadow_materializer.py`'s `TYPE_CHECKING` import to the new path.
5. Remove the `src/shared/infrastructure/storage/file_handler.py` entry from
   `architecture.shared.no_layer_imports` `excludes:` in
   `.intent/enforcement/mappings/architecture/layer_separation.yaml`.

### D4 — Caller migration

Update the 27 direct import sites to use the new Body-layer path. Prioritised
order: Body (14 sites) first, then CLI (6 sites), then Will (direct imports, if
any remain after FileService consolidation). The shim from D3 step 2 is removed
once the import count at the old path reaches zero.

FileService remains in Body as the sanctioned Will-tier surface. Will components
that already use FileService require no change.

### D5 — `shared/infrastructure/context/` long-horizon note

The context cluster (`service.py`, `builder.py`, `cache.py`, `serializers.py`)
is operational service logic in Shared. Its full migration to Body is a separate
architectural question — it involves Body/Will/CLI call chains that are outside
this ADR's scope. That migration is named here as a known direction consistent
with ADR-049's long-horizon trajectory; it requires its own ADR before any files
move.

---

## Migration sequence

```
Stage 1 — DI injection (no file moves, no callers broken)
  1a. test_runner.py: optional file_handler param; import → TYPE_CHECKING
  1b. serializers.py: file_handler param on to_yaml; import → TYPE_CHECKING
  1c. cache.py: propagate file_handler from callers into to_yaml
  1d. context/service.py: pass file_handler into cache calls

Stage 2 — Physical move
  2a. Move file_handler.py to body/infrastructure/storage/
  2b. Add re-export shim at old path
  2c. Update FileService import
  2d. Update shadow_materializer.py TYPE_CHECKING import
  2e. Remove excludes entry from layer_separation.yaml

Stage 3 — Caller cleanup
  3a. Update 27 call sites to new import path
  3b. Remove re-export shim
```

Stage 1 has no external blast radius — all changes are additive (new optional
parameter on test_runner; new required parameter on to_yaml propagated through
the context cluster). Stage 2 requires the shim to hold callers harmless. Stage 3
is mechanical substitution.

---

## Consequences

### Positive

- **The rule violation is eliminated, not ratified.** FileHandler reaches Body
  where it belongs; the `architecture.shared.no_layer_imports` exclude entry is
  removed rather than annotated.
- **No new exemption category.** Path X's "composition root" would have admitted
  any richly-wired runtime service as a Shared component. This path forecloses
  that drift vector.
- **Shared contracts tighten.** The context cluster's write-side and the test
  runner transition to DI injection, which is consistent with ADR-049's
  long-horizon direction and with every prior #315 closure (all of which used
  extraction, not exemption).
- **shadow_materializer.py is the template.** The existing correct pattern is
  already in the codebase; Stage 1 is an application of a proven precedent, not
  a novel design.
- **FileService is unchanged.** The Will-tier sanctioned surface is unaffected.

### Negative

- **Stage 1 requires propagating `file_handler` through the context cluster.**
  `context/service.py` already injects services via `BrainServicesProvider`; this
  adds one more. The change is additive but touches multiple files in the cluster.
- **Stage 3 is 27 import-path substitutions.** Mechanical but requires attention
  to avoid missing callers. The re-export shim provides a safety net: missed
  callers remain green until the shim is removed.
- **`shared/infrastructure/context/` retains operational service logic** until a
  separate ADR governs its Body migration. The cluster is cleaner (no
  self-instantiating FileHandler) but still not pure substrate.

### Neutral

- The re-export shim at the old path means Stage 2 is zero-downtime. The shim
  carries an ADR-126 reference comment and is removed in Stage 3.
- `FileOpResult` (the dataclass returned by all FileHandler write methods) moves
  with `file_handler.py`. The shim re-exports it as well; callers that import
  `FileOpResult` from the old path require no change until Stage 3.

---

## Verification

This ADR is verified when, on or before 2026-09-12:

1. `src/shared/infrastructure/storage/file_handler.py` no longer exists
   (or, if the shim is still in place, it contains only re-export lines with an
   ADR-126 reference comment and no module-level Body or Mind imports).
2. `src/body/infrastructure/storage/file_handler.py` exists and contains the
   full FileHandler implementation including `body.governance.intent_guard` and
   `mind.governance.violation_report` imports at the module level.
3. The `src/shared/infrastructure/storage/file_handler.py` entry is absent from
   the `excludes:` block of `architecture.shared.no_layer_imports` in
   `.intent/enforcement/mappings/architecture/layer_separation.yaml`.
4. `src/shared/infrastructure/context/serializers.py` and
   `src/shared/infrastructure/validation/test_runner.py` import `FileHandler`
   under `TYPE_CHECKING` only (or not at all).
5. A full audit run reports zero findings for `architecture.shared.no_layer_imports`
   against `src/shared/infrastructure/storage/file_handler.py`.

---

## References

- ADR-049 D1/D3 — doctrine-rule parity; establishes the closure ADR + deadline
  requirement that this document satisfies; names Shared contraction as long-horizon
  direction.
- ADR-051 — the closure ADR this supersedes; contains the Path X / Path Y
  framing and the 2026-09-12 deadline that this ADR inherits.
- ADR-079 — chokepoint capability scoping; governs the `current_capability()` /
  `current_mode()` calls in FileHandler's `_guard_paths`.
- ADR-097 — unified write channel; governs the target-class dispatch and the
  `write` entry consolidation that FileHandler implements.
- `src/shared/infrastructure/storage/file_handler.py:17–18` — the Body + Mind
  imports that constitute the rule violation.
- `src/shared/infrastructure/context/shadow_materializer.py:43–45` — the
  correct DI pattern that Stage 1 replicates.
- `src/shared/infrastructure/context/serializers.py:40` — FileHandler
  instantiation that Stage 1 eliminates.
- `src/shared/infrastructure/validation/test_runner.py:171,181` — FileHandler
  instantiations that Stage 1 eliminates.
- `src/body/services/file_service.py` — the Will-tier sanctioned surface;
  unchanged by this ADR.
- `.intent/enforcement/mappings/architecture/layer_separation.yaml` —
  `architecture.shared.no_layer_imports` `excludes:` entry to be removed in
  Stage 2.
- CORE-Mind-Body-Will-Separation.md §7.2 Admission Test 1 — the shared-layer
  admission test (`no_layer_imports`) that this ADR satisfies by elimination.
