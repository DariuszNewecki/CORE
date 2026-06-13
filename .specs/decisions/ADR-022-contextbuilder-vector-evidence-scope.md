---
kind: adr
id: ADR-022
title: 'ADR-022: ContextBuilder vector evidence scope'
status: accepted
---

<!-- path: .specs/decisions/ADR-022-contextbuilder-vector-evidence-scope.md -->

# ADR-022: ContextBuilder vector evidence scope

**Status:** Accepted
**Date:** 2026-05-03
**Authors:** Darek (Dariusz Newecki)
**Surfaced via:** Issue #198 (parent #197)

## Context

`ContextBuilder._gather_vector_evidence` (`src/shared/infrastructure/context/builder.py`) queries three Qdrant collections:

- `core_policies` — `.intent/` governance rules
- `core-patterns` — `.intent/` architecture patterns
- `core_specs` — `.specs/` human-intent documents (papers, northstar, requirements, ADRs, planning)

The source comment names `core_capabilities` as "the legacy code-symbol collection." Issue #198 framed the question as: re-include a code-symbol query in `_gather_vector_evidence`, or formally decide not to.

Empirical Qdrant inventory (2026-05-03) showed:

- `core_capabilities` — does not exist.
- `core_symbols` — does not exist.
- `core-code` — exists, 3858 points. Populated by `RepoCrawlerWorker` via the `qdrant_collections` mapping in `governance_paths.yaml` (`python → core-code`). This is the active code-symbol collection.

The `core_capabilities` and `core_symbols` references that remain in source (in `_gather_vector_dimensions`, `VectorProvider` defaults, and the `vectors rebuild --target=symbols` CLI) point at collections that do not exist. Those are name-drift defects tracked separately and are not what this ADR resolves.

This ADR resolves the architectural question only: should `_gather_vector_evidence` query a code-symbol collection at all.

## Decision

`_gather_vector_evidence` continues to query intent-layer collections only: `core_policies`, `core-patterns`, `core_specs`. The active code-symbol collection `core-code` is intentionally not queried.

ContextBuilder evidence kinds are disjoint by source:

- **AST evidence** (`_gather_ast_evidence`, `_gather_db_evidence`) — precise structural facts about code: definitions, signatures, references, call graphs.
- **Vector evidence** (`_gather_vector_evidence`) — semantic similarity over the *intent layer*: what the constitution says, what patterns exist, what human-intent documents bear on the goal.

The two providers answer different questions. AST answers "what is the code." Vector answers "what does the intent say." Code-similarity ("which existing code is semantically near this goal") is a third evidence kind that is not currently produced and is not needed by current ContextBuilder consumers.

If a code-similarity stream is later warranted, it earns its own method (e.g. `_gather_code_similarity_evidence`) querying `core-code` directly. It does not get bolted onto vector evidence.

The misleading source comment naming `core_capabilities` as "legacy" is rewritten to state this rationale and reference this ADR. The comment rewrite lands in the same commit as this ADR.

## Consequences

### Positive

- Evidence kinds stay disjoint and named. A consumer reading ContextBuilder code knows what each provider supplies.
- The test-generation hallucination problem (CoderAgent fabricating APIs) is correctly framed: it requires the actual source file in the prompt, not similar-looking code from a vector neighbour. Solving it via `RemediationInterpretationService.build_reasoning_brief_dict()` wiring (already on the open list) is the right path; mixing `core-code` into vector evidence would have been a false fix.
- A future code-similarity evidence stream can be added cleanly when its consumer exists.

### Negative

- Code-similarity is unavailable to ContextBuilder consumers until that future method is introduced. No current consumer needs it; this is a latent constraint, not an active loss.
- `core-code` is populated and indexed at every crawl but not queried by ContextBuilder. The cost of indexing without ContextBuilder reads is borne by other consumers of `core-code` (the self-healing agent's Dim 2 once its name-drift defect is fixed; future code-similarity work).

### Neutral

- The three name-drift defects surfaced during this investigation (`core_capabilities` references in `_gather_vector_dimensions`, `VectorProvider` defaults, and the `vectors rebuild --target=symbols` CLI) are mechanical fixes tracked as separate Band D issues. They are not contingent on this ADR.

## Alternatives considered

**Re-include `core-code` in `_gather_vector_evidence`.** Rejected. Conflates two evidence kinds (intent semantics vs code similarity) into one method. Existing AST and DB evidence already cover code structure precisely; vector code-similarity adds fuzz where AST is exact. No current consumer needs the addition.

**Rename `_gather_vector_evidence` to `_gather_intent_vector_evidence` and add a parallel `_gather_code_vector_evidence`.** Rejected as premature. The second method has no consumer. Adding it now means writing untested integration. When a consumer surfaces, the method is added at that point — not earlier.

**Treat `core-code` as code-symbol vector evidence and feed it into AST evidence.** Rejected. AST evidence is structural. Vector hits are similarity-based. Mixing them weakens the contract `_gather_ast_evidence` consumers rely on.
