---
kind: adr
id: ADR-108
title: ADR-108 — External adoption ships a minimal authored starter-intent, not a copy of CORE's .intent/
status: accepted
---

<!-- path: .specs/decisions/ADR-108-external-adoption-minimal-starter-intent.md -->

# ADR-108 — External adoption ships a minimal authored starter-intent, not a copy of CORE's `.intent/`

**Date:** 2026-06-14
**Status:** Accepted — D1 and D2 implemented this session (`examples/starter-intent/`, demo synced). D3 (machinery-in-wheel) is the agreed direction; implementation deferred to its own change-set. Drafted under the governor's direction "do both — ADR, commit, push."
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-14).

**Grounding decisions:**
- **`DariuszNewecki/core-audit-demo`** — the F-10.4 verification artifact that proves the CORE
  Constitutional Audit GitHub Action works against an *external* repository (inline PR
  annotations + merge-blocking exit code). Until now it adopted CORE by copying CORE's **entire**
  `.intent/` (~248 files) to enforce, in practice, one legible rule. Its README promised "a truly
  minimal starter constitution — see CORE issue #545," but #545 is a closed path-resolution bug,
  not that work. The minimal starter did not exist. This ADR creates it.
- **`.specs/.../Prior Art and the End-to-End Gap.md`** — the "adopt CORE" claim rests on an
  external project being governable. A 248-file copy makes that claim hostile to adopt and prone
  to drift; this ADR makes it honest.
- **#545 / #544** — the four `shared/infrastructure/intent/` loader modules
  (`operational_capabilities`, `cognitive_roles`, `filesystem_operations`, `vocabulary_projection`)
  are *fail-closed*: each is the sole sanctioned reader of a specific taxonomy/vocab file and
  raises rather than returning empty. They define the irreducible **machinery floor** an offline
  audit needs, independent of which rules run. This is load-bearing for D1's split and D3's target.

**Related:**
- `scripts/demo.sh` — the complementary proof: CORE governing *itself* locally, LLM-free. This ADR
  is about the *other* proof: governance *travelling* to an external repo's CI. Both are needed.
- `examples/starter-intent/` — the source-of-truth artifact this ADR introduces.
- `src/cli/resources/code/audit.py` → `mind/governance/stateless_audit.py` — the offline audit path
  whose load requirements set the floor.
- Memory `[[feedback_two_surface_requires_two_structures]]` — rules and machinery are two surfaces
  with different owners; unifying them into one copied blob was the bug.
- Memory `[[user_reviews_adrs_not_code]]` — this ADR is the review surface for the starter.

---

## Context

`core-audit-demo` adopts CORE by copying all of `.intent/`. That copy is the wrong artifact:

1. **It drifts.** CORE evolves its schemas and rule-ids continuously; every adopter's copy rots
   the moment it does, silently, with no signal.
2. **It speaks CORE's internal dialect.** An outsider inherits `linkage`, `purity`,
   `infrastructure` namespaces and self-host concepts (workers, flows, proposal-lifecycle,
   contracts) that have no meaning for a project that is merely being *audited*.
3. **It makes the on-ramp a lie.** "Drop CORE's `.intent/` into your repo" means copying ~248
   files to enforce a handful of rules.

Picking fewer rules inside that frame does not help — a stripped copy is still a copy. The
problem is the *copy*, not its size.

### Empirical floor

The offline audit (`core-admin code audit --offline` → `run_stateless_audit`) was run against
progressively-stripped trees to find what it actually requires. Result: it does **not** need
`workers/`, `flows/`, `workflows/`, `phases/`, `artifact_types/`, `contracts/`, `cim/`,
`governance/`, or the `knowledge_gate`/`llm_gate` rules (filtered out — they need a DB/LLM). It
**does** hard-require, regardless of ruleset:

- `META/` bootstrap schemas + `enums.json` + `vocabulary.json` (+ schema);
- three fail-closed taxonomies: `operational_capabilities.yaml`, `cognitive_roles.yaml`,
  `filesystem_operations.yaml`;
- `enforcement/config/` (eager-loaded).

These ~27 files are **machinery** — CORE-internal, identical for every adopter, never hand-edited.
The remaining ~4 files (`constitution/`, `rules/*.json`, `enforcement/mappings/*.yaml`) are the
**rules** an adopter actually authors. The audit dispatches on `engine` + `params.check_type`, not
on rule-id, so an adopter can author plain-language rule ids (`starter.symbol_ids`) mapped to
existing deterministic engines without touching any machinery.

---

## Decision

### D1 — Adopters ship a minimal *authored* starter, not a copy

The canonical adoption artifact is a small, authored `.intent/` whose **rules layer** is written in
plain, project-neutral language and whose **machinery layer** is the irreducible floor above. The
reference starter enforces four universal, deterministic, LLM-free rules: `# ID:` anchors on public
symbols (blocking), docstrings, no `print()` in library code, and no silently-swallowed exceptions.
It produces inline annotations and a blocking exit on a planted violation — the honest minimum.

### D2 — Source of truth lives in CORE; the demo is a one-way mirror

The starter is version-controlled **in CORE** at `examples/starter-intent/`, where CORE's own audit
guards it against drift (`verify.sh`: a planted violation must still fail the gate). `core-audit-demo`
is a **published mirror**, regenerated by `sync-to-demo.sh` (CORE → demo, one-way). The demo's
checkout lives in CORE's gitignored `var/external/` as a publish target, not as source. The demo
holds nothing authoritative except its `LICENSE` and `.gitignore`; even its consumer README is
CORE-owned (`DEMO-README.md`). This retires the stale #545 README pointer.

### D3 — (Deferred) The machinery floor belongs in the `core-runtime` wheel

The ~27 machinery files are pure runtime substrate; an adopter should never carry or maintain them.
The agreed direction is to bundle them in the `core-runtime` wheel as package data, with the loader
falling back to the packaged baseline when the consumer does not override. After D3, an adopter's
`.intent/` shrinks to the rules layer only (~4 files), and the "adopt by writing almost nothing"
claim becomes literally true. D1's machinery/rules split is drawn precisely so that D3 is invisible
to adopters — the starter and the demo shrink, nothing else changes. Implementation is its own
change-set; this ADR records the direction and the floor it must preserve.

### D4 — The delivered starter actually enforces: one law root, and the gate fails closed

D1 promises the starter "produces inline annotations and a blocking exit on a planted violation."
Verifying that promise (the T1 gate of the BYOR program backlog) surfaced two ways the consumer
audit could *silently* not enforce. Both are closed here as invariants of the audit gate, not just
of this starter.

1. **Law is sourced from a single root.** A rule and its enforcement mapping are one corpus and
   MUST be read from the same root — the `IntentRepository` root — never split across the
   code-under-audit root (`repo_path`). The audit had rooted policies at the IntentRepository but
   the enforcement mappings at `repo_path`. When those diverged — a BYOR consumer audited from
   CORE's source tree, where the `.env` `REPO_PATH`/`MIND` pin separates law-root from cwd — every
   rule loaded but none mapped, and the gate returned a false-green PASS. This is the same lesson
   OPA encodes with bundles (policy and data load together from one source) and matches the
   project's two-surface principle: `repo_path` is the *artifact* axis; the constitution is the
   *law* axis, and the two halves of the law share its root.

2. **The gate fails closed on governance collapse.** If the constitution declares rules but **zero**
   of them map to an enforceable engine, the audit can evaluate nothing; it MUST NOT return PASS.
   The stateless runner returns a distinct `ERROR` verdict (CLI exit 2 — operator action, not
   developer action). This is the application of the existing `governance.no_governance_bypass`
   rule ("if a precondition cannot be evaluated, block") to the F-10 offline path, and mirrors the
   Kubernetes admission-control default (`failurePolicy: Fail`) for a security-critical gate: a
   check that cannot run denies, it does not wave through.

   **Boundary.** This fires only on *total* collapse (declared rules > 0, mapped rules = 0). A
   partial declared-only set — CORE's own Class-A unmapped rules — and the all-skipped-in-stateless
   case (rules mapped, but every engine needs the graph or LLM) are honest coverage gaps already
   surfaced in `skipped_rules`; they remain non-blocking. Fail-closed is reserved for "a
   constitution that enforces nothing," not "a constitution that enforces less here."

This is gate behavior, so it lives on the audit path (`AuditorContext`, `stateless_audit`), not in
the starter content. It was anchored here rather than on ADR-085 (which scopes *what* engineering
builds, not *how* the gate behaves) because T1 — "does the delivered starter actually enforce?" —
is this ADR's promise to keep. Verified by a co-pointed consumer that blocks on a planted violation,
a divergent-root case that now binds all four rules, and a no-mappings case that returns `ERROR`;
regression-pinned in `tests/mind/governance/test_audit_context__enforcement_root.py` and
`tests/mind/governance/test_stateless_audit__fails_closed.py`.

---

## Consequences

- **Positive.** The on-ramp is honest and small; the starter is drift-guarded by CORE's own gate;
  "what is authoritative" is unambiguous (the tracked template always wins); D3 can land later with
  zero churn to adopters.
- **Cost.** Until D3, the machinery floor is duplicated into each adopter's repo (and the demo).
  This is the explicit, bounded debt D3 retires. The duplication is mechanical (copied verbatim by
  `sync-to-demo.sh`), so it does not drift between source and mirror within a release.
- **Follow-up.** D3 implementation (wheel packaging + loader fallback). The reference starter's rule
  set is intentionally tiny; adopters are expected to grow `rules/starter.json`, not edit machinery.
