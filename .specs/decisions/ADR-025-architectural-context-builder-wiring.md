---
kind: adr
id: ADR-025
title: 'ADR-025: ArchitecturalContextBuilder construction site — CoreContext factory
  over agent-internal construction'
status: retired
---

# ADR-025: ArchitecturalContextBuilder construction site — CoreContext factory over agent-internal construction

**Status:** Retired 2026-10-09 — the anchor map Priority 1 depends on was never built; see §Retirement (2026-10-09) at the end. Accepted 2026-05-05.
**Date:** 2026-05-05
**Governing paper:** `.specs/papers/CORE-Context-Packet-Doctrine.md`
**Authors:** Darek (Dariusz Newecki)

## Context

`ArchitecturalContextBuilder` provides Priority 1 ("Semantic Architectural Context") mode for `CodeGenerator` — the prompt path that includes vector-retrieved policy hits, module-anchor placements, similar-example retrieval, and target-file content. When `context_builder is None`, `CodeGenerator.semantic_enabled` is False and the system falls back to Priority 2 (context-enriched; may itself be degraded when qdrant is unconfigured) or Priority 3 (basic; goal string only).

As of 2026-05-05, `ArchitecturalContextBuilder` has zero callsites. The class exists; nothing constructs one. Specifically:

- `CoderAgent.__init__` does not accept a `context_builder` parameter.
- `CodeGenerator.__init__` accepts one but defaults to `None`; CoderAgent passes nothing.
- `build.tests` (and any other CoderAgent consumer) is structurally locked out of Priority 1 mode regardless of runtime conditions.

This was surfaced 2026-05-05 during #228 root-cause investigation. Five `build.tests` failures on 2026-05-04 generated invalid Python that the syntax-validator correctly refused to write. The structural finding is consistent with — though not solely demonstrated by — the failure pattern.

## Decision

**Wire `ArchitecturalContextBuilder` through `CoreContext` using a factory + lazy property, mirroring the existing `context_service` pattern exactly.**

1. Add `context_builder_factory: Callable[[], Any] | None` field to `CoreContext`.
2. Add `_context_builder: Any` private cache field.
3. Add `@property context_builder` that returns the cached instance, calling the factory on first read and raising `RuntimeError` if no factory is configured.
4. Wire the factory at every composition root that currently sets `context_service_factory` (CLI lifecycle and daemon composition root).
5. Extend `CoderAgent.__init__` to accept `context_builder: ArchitecturalContextBuilder | None = None` and pass it through to `CodeGenerator`.
6. Update `action_build_tests` to read `core_context.context_builder` and pass it to `CoderAgent`, mirroring the existing `context_service` JIT-fallback behavior.

## Alternatives Considered

**B — Construct `ArchitecturalContextBuilder` inside `CoderAgent.__init__`.** Rejected. Would require CoderAgent to receive five additional dependencies (policy_vectorizer, anchor_generator, etc.) or import-and-construct them itself. Either crosses architectural layers — CoderAgent would directly depend on PolicyVectorizer and ModuleAnchorGenerator instead of receiving them. This is the hidden-dependency-in-agent anti-pattern previously named by ADR-008 and the carry-forward "daemon composition root fix" thread.

**C — Construct in `build_tests_action` and pass directly to CoderAgent.** Rejected. Localizes the wiring to one consumer; every future CoderAgent consumer would repeat the construction. The action becomes a service-locator, coupling it to infrastructure decisions that belong at the composition root.

## Consequences

**Positive:**

- Wiring is consistent with the existing `context_service` factory pattern. One pattern in the codebase, not two.
- Dependencies are explicit at the composition root, not hidden inside agents.
- ArchitecturalContextBuilder becomes immediately usable by any agent that needs Priority 1 prompts; future consumers don't re-solve the construction question.
- `CodeGenerator.semantic_enabled = True` becomes attainable for build.tests, enabling the highest-context prompt path.

**Negative:**

- Two composition-root sites must be updated together (CLI and daemon). If only one is wired, agents reachable from the other site silently fall back to Priority 2/3 — same kind of observability gap ADR-009 named for IntentGuard state.
- Whether Priority 1 mode actually produces better-quality test output than Priority 2 with properly-wired qdrant is an empirical question this decision does not answer. Post-fix invalid-Python rate on build.tests is the test.

## Non-Goals

- This ADR does not specify whether `ContextService` should always have a fully-wired qdrant client. That is a separate decision affecting the Priority 2 path.
- This ADR does not add a `core-admin inspect context-builder` health check that would close the observability gap noted above. Follow-up.

## References

- Surfaced during: #228 build.tests root-cause investigation (2026-05-05).
- Related: #238 (DecisionTracer persistence broken — separate observability gap).
- Pattern source: `CoreContext.context_service` / `context_service_factory` / `_context_service` triple in `src/shared/context.py`.
- userMemories carry-forward: "ContextBuilder needs to be wired before CoderAgent for build.tests."

## Retirement (2026-10-09)

**Retired by:** the governor, 2026-10-09 ("remove the feature"), during the dead-code sweep
(`var/reports/2026-10-09-dead-code-sweep-plan.md`). The text above is kept as the record.

**Why.** Priority 1 ("Semantic Architectural Context") asks `ModuleAnchorGenerator.find_best_placement` for
the best placement in the Qdrant collection `core_module_anchors`. That collection was never built: its
builder (`generate_all_anchors`) had no caller, and the collection does not exist. So
`ArchitecturalContextBuilder.build_context` raised on every call, and `build.tests` — the only consumer this
ADR wired — failed on that path instead of falling back.

**Evidence.** `core.action_results`: `build.tests` last ran 2026-06-28; the other CoderAgent users
(`code_generation_phase`, `interactive_test`) never received a builder; the live test-generation loop
(`build.test_for_symbol`) does not use CoderAgent. The open question in Consequences (whether Priority 1
beats Priority 2) was never testable, because Priority 1 never ran successfully.

**What was removed** (3cfee49d): `ArchitecturalContextBuilder`, the anchor subsystem
(`ModuleAnchorGenerator`, `anchor_builder`, `anchor_search`, `anchors/`, `layers`, `module_descriptor`),
`shared/tools/context/`, `CodeGenerator`'s Priority-1 branch, `CoreContext.context_builder` /
`context_builder_factory`, and `build.tests`' JIT block. CodeGenerator now has two modes: context-enriched
(`ContextService`) and standard.
