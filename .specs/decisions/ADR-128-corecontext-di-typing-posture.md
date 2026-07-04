---
kind: adr
id: ADR-128
title: ADR-128 — CoreContext DI typing posture (three-tier model)
status: accepted
---

<!-- path: .specs/decisions/ADR-128-corecontext-di-typing-posture.md -->

# ADR-128 — CoreContext DI typing posture (three-tier model)

**Date:** 2026-06-28
**Governing paper:** `.specs/papers/CORE-Mind-Body-Will-Separation.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-28 — drafted under governor direction)
**Closes:** #643
**Relates to:** #602 (quality.type_safety drain — largest single cluster),
ADR-097 (file_handler/file_service mandatory fields — D4), ADR-049 D1/D3
(shared boundary excludes)

---

## Context

`CoreContext` (`src/shared/context.py`) is the explicit DI carrier passed
through every CLI command and API handler. Prior to this ADR, six service
slots were declared `Any | None = None` and two post-construction attributes
(`path_resolver`, `action_executor`) were assigned outside the dataclass
entirely. Together these produced ~194 of the 756 `quality.type_safety` errors
tracked in #602, with 113 of those on `.repo_path` alone (accessed on
`git_service: Any | None`).

The root causes split into three classes:

1. **Always-wired services typed as Optional.** `git_service`,
   `knowledge_service`, `file_handler`, `file_service` are provided by every
   production construction path (bootstrap, daemon, alignment persistence) and
   are assumed non-None by all call sites. Declaring them `Any | None` forced
   callers to carry a nominal None risk that never manifests.

2. **Post-construction attributes not declared on the dataclass.** Bootstrap
   assigns `core_context.path_resolver` and `core_context.action_executor`
   after construction (`body/infrastructure/bootstrap.py:129–130`). Because
   these fields are not declared in the dataclass, mypy emits `attr-defined`
   at every access site.

3. **Genuinely-degradable services typed as `Any | None`.** `cognitive_service`,
   `auditor_context`, `qdrant_service`, `planner_config` are legitimately
   Optional — the daemon wires them in `try/except` blocks because the
   underlying resources (LLM, Qdrant, audit engine) may be unavailable at
   startup. Typing them `Any | None` suppresses mypy's attribute-existence check
   on the `Any` branch while still producing union-attr errors on the `None`
   branch.

### Why Option B (mandatory injection) was preferred for always-wired services

Option A (typed `require_x()` accessors) would preserve the `Optional` type
and add a fail-fast assertion at call time. It does not change the construction
signature. Option B (non-Optional mandatory constructor fields) encodes the
guarantee at the type level: a construction site that omits a field fails at
`TypeError` rather than at the first attribute access. Since all three production
construction paths already provided all four services, the cost of Option B was
zero additional runtime calls; the benefit is ~113 fewer mypy errors and a
machine-checkable construction contract.

### Why cross-layer TYPE_CHECKING imports are permitted in `shared/context.py`

`architecture.shared.no_layer_imports` prohibits runtime imports from
`src/mind/`, `src/body/`, `src/will/` in shared code. `src/shared/context.py`
already carries an existing exemption (tracked under ADR-049 D1/D3's eight
pending closure excludes) for `FileHandler` (body) and `FileService` (body)
under `TYPE_CHECKING`. Because `from __future__ import annotations` is active,
all annotations are evaluated as strings at runtime — the imports are
annotation-only and trigger no runtime boundary crossing. This ADR extends the
same exemption to `CognitiveService` (will) and `AuditorContext` (mind).

---

## Decision

### D1 — Always-wired services: mandatory positional fields

`git_service`, `knowledge_service`, `file_handler`, `file_service` are declared
without a default value. A `CoreContext()` call that omits any of them raises
`TypeError` at construction time. All three production construction paths
(bootstrap, daemon, alignment persistence) are updated to pass all four.

This is the implementation of Option B from the #643 options analysis.

### D2 — Post-construction infrastructure: typed Optional fields, set immediately

`path_resolver: PathResolver | None = field(default=None)` and
`action_executor: ActionExecutorProtocol | None = field(default=None)` are
declared as dataclass fields with `None` defaults. Bootstrap sets them
immediately after `CoreContext(...)`:

```python
core_context.path_resolver = PathResolver.from_repo(...)
core_context.action_executor = ActionExecutor(core_context)
```

Daemon and alignment persistence paths that do not set these fields continue to
produce a CoreContext where both are None. Callers in bootstrap-wired contexts
(Will phases, CLI commands) access these without a None guard; the typing is
Optional but the None-at-runtime risk is confined to non-bootstrap paths that
would fail anyway if these were called.

Workers that need `action_executor` and cannot assume a bootstrap context
(e.g. `ViolationExecutorWorker`, `CallSiteRewriterWorker`) continue their
existing pattern of lazy-creating `ActionExecutor(ctx)` if `ctx.action_executor
is None`.

### D3 — Genuinely-degradable services: typed Optional (not `Any | None`)

`cognitive_service`, `auditor_context`, `qdrant_service`, `planner_config` are
typed with their concrete Optional type rather than `Any | None`:

| Field | Type |
|---|---|
| `cognitive_service` | `CognitiveService \| None` |
| `auditor_context` | `AuditorContext \| None` |
| `qdrant_service` | `QdrantService \| None` |
| `planner_config` | `PlannerConfig \| None` |

This preserves the Optional semantics required by the daemon's graceful-degradation
`try/except` wiring while replacing `Any` with the real type. Callers that
access these services are now required (by mypy) to guard with
`if ctx.cognitive_service is not None` — making the conditional access
machine-checkable rather than invisible.

### D4 — TYPE_CHECKING exemption for `shared/context.py` cross-layer annotations

The shared-layer types (`GitService`, `KnowledgeService`, `PathResolver`,
`QdrantService`, `PlannerConfig`, `ActionExecutorProtocol`) are imported under
`TYPE_CHECKING` to be consistent with the file's existing pattern and to avoid
circular-import risk at module load time.

The two cross-layer types (`CognitiveService` from will, `AuditorContext` from
mind) are imported under `TYPE_CHECKING` only, extending the existing exemption
for `FileHandler` and `FileService` (both from body). The exemption is limited
to annotation use in `shared/context.py`; no other shared file acquires a
cross-layer TYPE_CHECKING import under this ADR.

---

## Consequences

**Positive:**

- The ~194-error cluster in #602 is structurally resolved. The four always-wired
  service accesses (113 errors on `.repo_path` alone) are now typed non-Optional.
  The four Optional services now produce real attribute errors (not union-attr
  errors silenced by `Any`) when accessed without a guard.
- `path_resolver` and `action_executor` are declared on the dataclass; mypy
  can resolve their types at every access site.
- Construction failures are immediate: a missing mandatory service raises
  `TypeError` at `CoreContext(...)`, not an `AttributeError` five call frames
  later.

**Negative:**

- `CognitiveService` and `AuditorContext` are now named in `shared/context.py`
  under `TYPE_CHECKING`. This is a mild coupling — renaming either class requires
  updating the import here. This cost is accepted because it is strictly
  annotation-only and follows an established exemption.
- Callers that access `path_resolver` or `action_executor` without a None guard
  in non-bootstrap contexts will surface mypy warnings. These are genuine typing
  gaps; the warnings are correct signals.

**Neutral:**

- `registry: Any` remains untyped. The registry is a heterogeneous service
  locator whose typing posture is a separate concern (not in scope for this ADR).
- No schema, no migration, no runtime behaviour change — this ADR records a
  type annotation decision and the construction-guarantee it implies.

---

## References

- #643 — original issue; options A/B analysis
- #602 — quality.type_safety systematic drain; this is its largest cluster
- ADR-097 — established `file_handler` / `file_service` as mandatory fields (D4)
- ADR-049 D1/D3 — shared boundary excludes; eight pending closure items; this
  ADR adds `CognitiveService` and `AuditorContext` to the exempted set for
  `shared/context.py` TYPE_CHECKING imports
