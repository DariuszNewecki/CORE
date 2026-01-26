<!-- path: .intent/papers/CORE-Workflow-Papers-First.md -->

# CORE Workflow: Papers First, Then Code

**Status:** Constitutional Companion Paper
**Authority:** Constitution (derivative, non-amending)
**Scope:** All code-changing operations executed by CORE (CLI, agents, workflows)

## Rule

Any operation that **writes or modifies** files under `src/**` or `tests/**`
MUST cite an approved paper under `.intent/papers/**` as evidence **before** the change is executed.

“Cite” means the execution record contains a `paper_ref` that matches an existing file path under `.intent/papers/`.

If `paper_ref` is missing, invalid, or points to a non-existent file, the operation is invalid and MUST be blocked.

## Notes

This paper defines the workflow law only. Tooling and enforcement mechanisms are defined elsewhere.
