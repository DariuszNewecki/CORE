<!-- path: .specs/papers/CORE-Workflow-Papers-First.md -->

# CORE Workflow: Papers First, Then Code

**Status:** Constitutional Companion Paper
**Authority:** Constitution (derivative, non-amending)
**Scope:** All code-changing operations executed by CORE (CLI, agents, workflows)

## Rule

Any operation that **writes or modifies** files under `src/**` or `tests/**`
MUST cite an approved paper under `.intent/papers/**` as evidence **before** the change is executed.

"Cite" means the execution record contains a `paper_ref` that matches an existing file path under `.intent/papers/`.

If `paper_ref` is missing, invalid, or points to a non-existent file, the operation is invalid and MUST be blocked.

## Conflict Resolution

When two papers contradict each other, the following precedence rules apply in order:

1. **Authority level wins.** A paper at constitution authority overrides a paper at policy authority. The authority level is declared in the paper's front matter.

2. **Specificity wins.** When two papers at the same authority level contradict, the more specific paper overrides the more general one. A paper scoped to a single component overrides a paper scoped to a layer; a paper scoped to a layer overrides a paper scoped to the system.

3. **Human decision.** When neither rule above resolves the contradiction, it is escalated to the architect. The resolution is recorded as an amendment to one of the papers, with a `supersedes` note naming the overridden claim. Silence does not resolve a contradiction.

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
