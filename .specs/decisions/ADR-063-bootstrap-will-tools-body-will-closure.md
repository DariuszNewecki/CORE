---
kind: adr
id: ADR-063
title: ADR-063 — bootstrap.py will.tools body→will closure
status: accepted
---

<!-- path: .specs/decisions/ADR-063-bootstrap-will-tools-body-will-closure.md -->

# ADR-063 — bootstrap.py will.tools body→will closure

**Status:** Accepted
**Date:** 2026-05-19
**Authors:** Darek (Dariusz Newecki)
**Deadline:** 2026-09-16 (120 days)
**Closes:** Second/third/fourth bullets of #313 (bootstrap.py exclude)
**Relates to:** ADR-049 D3 (closure ADR + deadline requirement),
CORE-Mind-Body-Will-Separation.md §5.4 Body→Will prohibition

---

## Context

`src/body/infrastructure/bootstrap.py:60–64` contains three lazy
(function-scoped) imports inside the `_factory()` closure of the
context-builder factory:

```python
def _factory():
    from will.tools.architectural_context_builder import (
        ArchitecturalContextBuilder,
    )
    from will.tools.module_anchor_generator import ModuleAnchorGenerator
    from will.tools.policy_vectorizer import PolicyVectorizer
    ...
```

All three violate `architecture.layers.no_body_to_will`
(`layer_separation.yaml` RULE 12) under the expanded bare-prefix
`forbidden:` list that landed in commit `6edec08d` (ADR-049 D1).

The imports are lazy because:

- They are only needed when `_factory()` is invoked to construct the
  context-builder lazy singleton — i.e. when a CLI command requests
  the build-tests path or when the daemon's pre-warm sequence runs.
- The factory captures `core_context.cognitive_service` and
  `core_context.qdrant_service` at invocation time; both must be
  populated, which only happens after Body's lifespan ignition.
- Module-level imports would force every consumer of `bootstrap` to
  pay the Will-tool import cost regardless of whether they exercise
  the context-builder path.

The three tools themselves:

- `ArchitecturalContextBuilder` — composes architectural context from
  the knowledge graph for a code-generation request.
- `ModuleAnchorGenerator` — generates anchor symbols (entry-point
  hints) for context retrieval.
- `PolicyVectorizer` — converts policy documents into vector form for
  semantic retrieval.

All three are stateless builders that operate on the
`cognitive_service` + `qdrant_service` pair from `core_context`. They
are Will-resident today because they were originally written as part
of Will's context-assembly path.

The `ast_gate import_boundary` engine does walk inline / function-body
imports (it does *not* walk `TYPE_CHECKING` only), so the lazy form
does not escape detection — and is correctly caught under the
expanded `forbidden:` list.

---

## Why this is structurally harder than a one-line move

The three tools are not free-standing — they share dependencies on the
Will-layer `cognitive_service` and `qdrant_service` *protocols* and
on `ArchitecturalContextBuilder`'s own internal helpers that currently
live under `will/tools/`.

A clean closure requires deciding:

- Which of the three tools genuinely belongs in Will (because they
  carry cognitive decisions) versus which is pure data assembly
  (which belongs in Shared or Body).
- Whether the shared protocol surface (`CognitiveProtocol`,
  `QdrantProtocol`) is sufficient for the tools' needs after they move.
- Whether the `_factory` pattern itself should remain in Body or move
  to a composition root.

Doing it as part of #313 closure would mean either taking on a
multi-file move (re-homing 3 modules + their tests + any helpers) or
authoring three separate sub-decision ADRs. Neither is appropriate
in-line with the doctrine-rule parity closure.

---

## Closure path

Two viable options for the eventual refactor:

**Option A — Re-home the three tools to `src/shared/cognitive_tools/`
or equivalent.**

The tools are mechanical builders operating over protocols
(`CognitiveProtocol`, `QdrantProtocol`). They make no strategic
decisions; they assemble. They satisfy ADR-049 §7.2 Admission Test 2
("No Strategic Decisions") and Test 3 (no exclusive ownership of a
domain). Moving them to Shared resolves the body→will exclude and
satisfies Paper §7.2's "no exceptions" claim without an excludes
entry.

**Option B — Invert ownership: Body owns the context-builder factory
and constructs the tools via dependency injection.**

The lifespan or composition root receives instances from Will (which
keeps owning the tool implementations) and passes them into Body via
`CoreContext`. Body never imports from Will because the references
arrive pre-constructed.

Option A is preferred on first reading: the tools are stateless and
data-shaped; they fit ADR-049's long-horizon "shared as pure
contracts" direction. Option B keeps the tools in Will at the cost
of growing `CoreContext`'s surface — viable if the tools are deemed
to carry decision logic on closer inspection.

---

## Deadline

**2026-09-16** (120 days from acceptance). Matches ADR-051 / ADR-062.

- Warning state: audit emits a warning when this date passes if the
  exclude entry is still present.
- Blocking state: 30 days past deadline (2026-10-16), the entry is
  treated as a rule violation; `bootstrap.py` fails audit until
  refactored or until this ADR is amended.

---

## Consequences

**Positive:**

- All three body→will imports in `bootstrap.py` are governed under
  one ADR with one deadline. The "TBD" deadline marker in
  `layer_separation.yaml` is replaced with `2026-09-16` and a
  back-reference here.
- The three tools' architectural classification — Will (decisive) or
  Shared (mechanical) — is named as an open question, ready for the
  refactor to resolve.

**Negative:**

- The refactor itself is not done; Body's `bootstrap.py` continues
  to import from Will at function-call time. Each cold-path execution
  of `_factory()` triggers the import.

**Neutral:**

- The lazy-import pattern is a workaround for cold-start cost, not
  an architectural shield. Either Option A or Option B is structurally
  cleaner than the current state.

---

## Verification

This ADR is verified when, on or before 2026-09-16:

1. Either `src/body/infrastructure/bootstrap.py` no longer imports
   from `will.*` (eagerly or lazily), or this ADR has been amended
   with a new deadline and named blocker.
2. The `src/body/infrastructure/bootstrap.py` entry in
   `architecture.layers.no_body_to_will` `excludes:` is removed (if
   refactored) or its comment is updated to reference this ADR's new
   deadline.

---

## References

- ADR-049 — Doctrine-rule parity; D3 sets the closure ADR + deadline
  requirement that this document satisfies.
- ADR-051 — file_handler.py closure (precedent for this ADR's shape).
- `src/body/infrastructure/bootstrap.py:60–64` — the lazy import block.
- `src/will/tools/architectural_context_builder.py` — first tool.
- `src/will/tools/module_anchor_generator.py` — second tool.
- `src/will/tools/policy_vectorizer.py` — third tool.
- `.intent/enforcement/mappings/architecture/layer_separation.yaml`
  RULE 12 `excludes:` block — the entry this ADR closes.

---

## Note — 2026-05-31 (#490): engine check renamed

The phrase "`ast_gate import_boundary` engine" in this ADR's body is
superseded by the rename landed under #490 — the engine check is now
`runtime_import_boundary`, the file is `checks/runtime_import_boundary.py`,
and the class is `RuntimeImportBoundaryCheck`. Constitutional intent
unchanged; the rename brings the mechanism name into line with the
constitutional intent (forbids runtime invocation, allows type-level
proprioception via `if TYPE_CHECKING:`). See `.intent/CHANGELOG.md`
#490 entry for the full rationale.
