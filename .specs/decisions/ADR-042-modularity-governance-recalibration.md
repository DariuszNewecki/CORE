---
kind: adr
id: ADR-042
title: 'ADR-042: Modularity governance recalibration — responsibility-first'
status: accepted
---

<!-- path: .specs/decisions/ADR-042-modularity-governance-recalibration.md -->

# ADR-042: Modularity governance recalibration — responsibility-first

**Status:** Accepted
**Date:** 2026-05-13
**Supersedes:** ADR-007 (partially — threshold and enforcement model replaced; the
seam/class distinction and non-automatable classification are preserved)
**Depends on:** ADR-036 (PathResolver exclusion — generalised into the mechanism
defined here)

> Note (2026-06-06, per ADR-095): D4's commitment "retired when modularity.unix_philosophy comes online" is amended. The LLM-gate shape was the wrong mechanism for architectural judgment; the LOC stack is no longer transitional infrastructure waiting on the gate. D3's `governed_exclusions` register is also retired in favor of in-file `CORE_ROLE` declarations. See ADR-095 D3 + D6.

---

## Context

`modularity.class_too_large` was introduced in ADR-007 with a 400-line threshold.
That threshold was a pragmatic early-phase approximation. CORE has since developed
a mature class population that reveals the threshold's core problem: line count is a
proxy for the thing being governed — responsibility count — and a poor one.

Three structurally distinct shapes appear in the current findings:

- **Seam-large:** mixed responsibilities. The rule fires correctly.
- **Facade-large:** single gateway responsibility; size reflects surface breadth, not
  mixed concerns. The rule fires incorrectly.
- **Algorithm-large:** single cohesive algorithm; decomposition risks correctness. The
  rule fires incorrectly.

The correct model: line count is a *pre-selector* that raises a candidate for review.
The *verdict* is whether the class has more than one responsibility — a question that
requires reasoning, not counting.

The current audit pipeline routes `modularity.unix_philosophy` (the existing
responsibility-check rule, `llm_gate`-backed) through `LLMGateStubEngine`, which
unconditionally returns pass. The llm_gate is operationally inert until the audit
pipeline is wired with an LLM client. Two prerequisite issues are tracked on GitHub
(see References).

---

## Decision

### D1. LOC threshold is a pre-selector, not a verdict

Line count governs whether a class is a *candidate* for responsibility review. It is
not a finding in itself. This principle governs all future modularity rule authoring.

### D2. Raise the pre-selector threshold from 400 to 500

The 401–499 range fires on classes that are algorithm-large or barely over an
arbitrary early-phase boundary. Raising to 500 reduces false positives while
preserving candidates that warrant review. Both `class_too_large` and `needs_split`
thresholds are raised to 500 for consistency.

### D3. Introduce a governed exclusion register as interim mechanism

Until the llm_gate audit path is operational, facade-large and algorithm-large classes
require a documented exception mechanism. The ad-hoc `excludes:` comment pattern
(ADR-036, ADR-040) is replaced by a first-class `governed_exclusions:` block in
`code/modularity.yaml`. Each entry must declare: `file`, `class`, `category`
(facade | algorithm | catalog), `rationale`, and `removal_condition`. Entries missing
any field are a constitution validation error.

Existing ADR-036 (PathResolver) and ADR-040 (operational_config.py) exclusions are
migrated to this register as part of implementation.

### D4. End state (deferred, conditioned on llm_gate wiring)

Once the audit pipeline LLM client is wired and `modularity.unix_philosophy` is
qualified against the class population, the governed exclusion register becomes
unnecessary. Facade-large and algorithm-large classes answer the responsibility
question themselves. The exclusion register is retired at that point. This transition
is tracked on GitHub (see References).

### D5. Close #192 as resolved by recalibration

Issue #192 was filed against the miscalibrated rule. The recalibration resolves it
as a governance fix. Remaining genuine findings (seam-large classes above the new
500-line threshold) are tracked by the audit system directly.

---

## References

- GitHub #306: audit pipeline LLM client wiring (prerequisite for D4)
- GitHub #307: silent stub behavior — llm_gate rules produce no signal and no audit
  indication when LLM client is absent
- ADR-007: original class_too_large introduction
- ADR-036: PathResolver exclusion (migrated to governed_exclusions by this ADR)
- ADR-040: operational_config.py exclusion (migrated to governed_exclusions by this ADR)
