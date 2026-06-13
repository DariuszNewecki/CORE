---
kind: adr
id: ADR-061
title: ADR-061 — Composition-Root Sanctuary for `api/main.py` Lifespan Import
status: accepted
---

# ADR-061 — Composition-Root Sanctuary for `api/main.py` Lifespan Import

**Date:** 2026-05-19
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Constitutional Completeness
**Closes:** #157
**Related:** #111
**Codifies:** `architecture.api.no_body_bypass` sanctuary entry at
  `.intent/enforcement/mappings/architecture/layer_separation.yaml:237`
  (landed 2026-04-19, commit `f634e521`)

---

## Context

`src/api/main.py:39` imports `body.infrastructure.lifespan.core_lifespan`
and wires it into `FastAPI(lifespan=core_lifespan)` at `main.py:54`. By
the literal rule of `architecture.api.no_body_bypass` — which forbids
`src.body` / `body` imports from anything under `src/api/` — this is a
layer violation.

On 2026-04-19 (commit `f634e521`), the rule was patched to exclude
`src/api/main.py` with a "composition-root sanctuary" rationale in a
comment block at `layer_separation.yaml:232-237`. The exemption has
been in force since then and the audit has been clean against it.

What was never recorded was an ADR — the governance record codifying
*why* the sanctuary is the permanent answer, *what its scope is*, and
*what would force it to be revisited*. #157 has carried this open
question since 2026-04-25 with two named resolution paths:

1. ADR confirming the composition-root exemption is the permanent
   answer, with the sanctuary entry verified as correctly scoped.
2. Relocate `core_lifespan` out of Body and eliminate the Body import.

This ADR takes path 1.

---

## Why path 2 is not viable

`core_lifespan` is constitutionally Body-resident. Its imports
(`lifespan.py:17-22`):

| Import | Layer |
|---|---|
| `body.infrastructure.bootstrap.create_core_context` | Body |
| `body.services.service_registry.service_registry` | Body |
| `shared.infrastructure.diagnostic_service.DiagnosticService` | Shared |
| `shared.infrastructure.config_service.ConfigService` | Shared |
| `shared.config.settings` | Shared |

Its body (`lifespan.py:33-86`) runs the Body-owned ignition sequence:
diagnostic health gate, service warm-up (cognitive / auditor / qdrant),
DB session for config and cognitive initialization, and knowledge graph
load.

The two relocation destinations both fail:

- **`src/api/`** — would require `api/` to import `service_registry`,
  the cognitive service, the qdrant service, the diagnostic service,
  the bootstrap factory, and the settings module. The single sanctioned
  import becomes roughly half a dozen, each a fresh bypass. A worse
  violation, not a lesser one.
- **`src/will/`** — Will is the cognitive layer. Infrastructure
  ignition is not a Will responsibility. Placing it there is a
  semantic mismatch and contradicts
  `CORE-Mind-Body-Will-Separation.md §5`.

The lifespan module itself records its prior relocation
(`lifespan.py:6-9`): **it was moved from `shared.infrastructure` to
`body.infrastructure` as constitutional fix P2.3** precisely because
the shared layer could not import Body. Moving it again would either
re-create that same shared→Body coupling problem in a new location or
commit a worse violation in the destination. The relocation option is
off the table.

---

## Decision

### D1 — Codify the composition-root sanctuary as the permanent answer

The sanctuary entry already present in `layer_separation.yaml:237` is
ratified as the resolution to #157.

The sanctuary is bounded by a single rule:

> `src/api/main.py` is exempt from `architecture.api.no_body_bypass`
> for **exactly one import**:
> `body.infrastructure.lifespan.core_lifespan`, which FastAPI's
> `lifespan=` constructor argument requires at app creation time.

Any *additional* `body.*` import in `src/api/main.py` is a violation
and is not covered by this sanctuary. The sanctuary does not extend to
any other API file. The exclude list in Rule 11 continues to name
`src/api/main.py` as the single sanctuary file; this is a per-file
exemption, not a category exemption.

Rationale: FastAPI's `lifespan=` is constructor-time wiring. The
parameter is bound when `FastAPI(...)` is called and cannot be
deferred, lazy-loaded, or injected later without re-implementing
FastAPI's startup contract. The import lives at module top in
`api/main.py:39` because that is the scope at which it is needed.
Composition roots wire layers by design and are constitutionally
distinct from layer bypasses.

This is structurally analogous to two existing sanctuaries in the same
file:

- **`architecture.shared.no_layer_imports`** (Rule 15) excludes
  `src/shared/infrastructure/storage/file_handler.py` for an
  acknowledged transitional case.
- **`architecture.layers.no_body_to_will`** (Rule 12) excludes three
  Body files pending ADR-049 D3 closure ADRs.

The `api/main.py` sanctuary differs from those two by being
**permanent**, not transitional: there is no follow-up ADR pending and
no roadmap toward removing the import. The FastAPI lifespan contract
is stable upstream and the alternative destinations have been ruled
out above.

### D2 — Scope check for the sanctuary entry

The existing sanctuary is reviewed and found correctly scoped:

| Check | Result |
|---|---|
| Single-file scope (`src/api/main.py` only) | ✓ |
| Lives in `excludes:` of the correct rule | ✓ |
| Rationale comment present at lines 233-237 | ✓ |
| No category-level exemption (no glob, no parent dir) | ✓ |
| `applies_to` coverage `src/api/**/*.py` + `src/api/*.py` still in force | ✓ (2026-04-19 fix preserved) |

No edits to `layer_separation.yaml` are required. This ADR records
that the scope was verified at acceptance.

### D3 — Revisit triggers

The sanctuary must be revisited if any of the following changes:

1. **FastAPI's lifespan contract changes** such that `lifespan=`
   accepts a string, factory reference, or DI-resolvable handle,
   removing the constructor-time import requirement.
2. **A second Body import is needed in `api/main.py`** for any reason.
   The sanctuary covers `core_lifespan` only; a second import requires
   either a new ADR widening the sanctuary or a structural refactor.
3. **`core_lifespan`'s Body-residence is challenged** by a future
   redesign that moves ignition coordination elsewhere. Constitutional
   fix P2.3 would need to be revisited as part of any such change.

Outside these triggers, the sanctuary is stable and does not require
periodic re-ratification.

---

## State at ADR acceptance

| Item | State |
|---|---|
| Sanctuary entry in `layer_separation.yaml` | Present — line 237 |
| Sanctuary scope check | Passed — D2 |
| `api/main.py` docstring references the sanctuary | Present — lines 10-14 |
| `lifespan.py` records P2.3 relocation rationale | Present — lines 6-9 |
| Audit clean against `architecture.api.no_body_bypass` | Yes — baseline 64 findings / PASS |
| #157 | To be closed on ADR acceptance |

---

## Consequences

**Positive:**

- #157 closes with a definitive governance record. The "is this
  exemption permanent" question is no longer open.
- The composition-root pattern has explicit constitutional standing.
  Future "should X be sanctuaried" questions have a precedent to weigh
  against rather than relitigating from first principles.
- The relocation option is documented as ruled-out, with reasoning, so
  it does not resurface as a session-cold suggestion.

**Negative:**

- The sanctuary is a permanent named exception in the layer-separation
  rule. The exclude list grows by one comment block over what would
  otherwise be a pure rule. Acceptable given the alternative is a real
  violation.

---

## Verification

1. `architecture.api.no_body_bypass` lists `src/api/main.py` in its
   `excludes:` block (`layer_separation.yaml:237`).
2. `core-admin code audit` reports no findings against
   `architecture.api.no_body_bypass`.
3. `src/api/main.py` contains exactly one `body.*` import — `from
   body.infrastructure.lifespan import core_lifespan` at line 39.
4. #157 is closed referencing this ADR.

---

## References

- #157 — `api/main.py: API→Body bypass on core_lifespan import needs resolution`
- #111 — related (inherits this resolution)
- ADR-049 — Body↔Will boundary enforcement; precedent for named
  per-file sanctuaries pending closure ADRs
- `.specs/papers/CORE-Mind-Body-Will-Separation.md §5` — Mind/Body/Will
  layer responsibilities
- `.intent/enforcement/mappings/architecture/layer_separation.yaml:221-237`
  — Rule 11 (`architecture.api.no_body_bypass`) and the
  composition-root sanctuary
- `src/api/main.py:10-14, 39, 54` — site of the sanctioned import
- `src/body/infrastructure/lifespan.py:6-9, 17-22, 33-86` — body of
  `core_lifespan`, P2.3 residence note, and ignition sequence
- Commit `f634e521` (2026-04-19) — added the sanctuary entry to
  `layer_separation.yaml`
