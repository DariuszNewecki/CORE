---
kind: paper
id: CORE-Workflow-Papers-First
title: 'CORE Workflow: Papers First, Then Code'
status: canonical
doctrine_tier: constitution
---

<!-- path: .specs/papers/CORE-Workflow-Papers-First.md -->

# CORE Workflow: Papers First, Then Code

**Status:** Constitutional Companion Paper
**Authority:** Constitution (derivative, non-amending)
**Scope:** All code-changing operations executed by CORE (CLI, agents, workflows)

## Rule

Any operation that **writes or modifies** files under `src/**` or `tests/**`
MUST cite an approved paper under `.specs/papers/**` as evidence **before** the change is executed.

"Cite" means the execution record contains a `paper_ref` that matches an existing file path under `.specs/papers/`.

If `paper_ref` is missing, invalid, or points to a non-existent file, the operation is invalid and MUST be blocked.

**Aspirational status:** Enforcing rule not yet authored; this is normative design intent.

## Conflict Resolution

This section governs contradictions between `.specs/papers/` doctrine documents only. It does not apply to `.intent/rules/` conflicts, which are governed by `CORE-Rule-Conflict-Semantics.md`.

When two papers contradict each other, the following precedence rules apply in order:

1. **Doctrine tier wins.** A paper at `doctrine_tier: constitution` overrides a paper at `doctrine_tier: foundational`, which overrides `doctrine_tier: informational`. The tier is declared in the paper's YAML frontmatter (per ADR-105 D3).

2. **Specificity wins.** When two papers at the same doctrine tier contradict, the more specific paper overrides the more general one. A paper scoped to a single component overrides a paper scoped to a layer; a paper scoped to a layer overrides a paper scoped to the system.

3. **Human decision.** When neither rule above resolves the contradiction, it is escalated to the architect. The resolution is recorded as an amendment to one of the papers, with a `supersedes` note naming the overridden claim. Silence does not resolve a contradiction.

### Why paper conflict semantics differ from rule conflict semantics

`CORE-Rule-Conflict-Semantics.md` treats rule-vs-rule conflicts as governance errors
requiring no automatic resolution — no implicit precedence, no specificity heuristic.
Paper-vs-paper conflicts deliberately follow different semantics.

Papers are human-read doctrine. A specificity heuristic gives human readers a
deterministic reading order that handles common scope overlap without requiring
governor escalation for every minor contradiction. Rules are machine-enforced law.
A machine cannot apply interpretive judgment, so an unresolvable rule conflict must
surface as an error rather than silently suppress one of the competing rules.
The two surfaces serve different readers and different enforcement mechanisms — their
conflict semantics are intentionally asymmetric, not inconsistent.

## Implementation Status

**The `paper_ref` field does not yet exist in the execution pipeline.**

The Proposal schema, Crate manifest, and consequence log do not currently
carry a `paper_ref` field. The enforcement gate described in the Rule section
above cannot be implemented until:

1. `paper_ref` is added as a field to the Proposal schema.
2. The Proposal creation path (RemediatorWorker, ConsumerWorker) populates it.
3. A blocking rule is added to `.intent/rules/` that rejects Proposals without
   a valid `paper_ref`.

Until those three steps are complete, this paper declares the intended law.
Enforcement is a known implementation gap, not a missing governance decision.
