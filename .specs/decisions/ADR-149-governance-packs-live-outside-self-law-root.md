---
kind: adr
id: ADR-149
title: 'ADR-149 — Adoptable governance packs live outside the self-law root'
status: accepted
---

<!-- path: .specs/decisions/ADR-149-governance-packs-live-outside-self-law-root.md -->

# ADR-149 — Adoptable governance packs live outside the self-law root

**Status:** Accepted — 2026-07-14
**Date:** 2026-07-14
**Governor resolution (2026-07-14):** accepted as a standalone ADR; location is top-level `packs/`
(open question 1); the pack format schema stays in `.intent/META/` per D2 (open question 2).
**Grounds:** The two-surface principle (`.intent/` is CORE's *own* law, read at runtime via
`IntentRepository`) — governance content that CORE ships *for others to adopt* is a product, not
CORE's self-governance, and its physical location should make that boundary legible. Charter §6 —
*"law precedes machinery"* (the location is decided here before the move).
**Relates:** ADR-108 D2 (the consumer *starter* already lives outside `.intent/`, at
`examples/starter-intent/` — this extends the same boundary to the pack catalog) and ADR-108 D4
(the "single law root" invariant this clarifies, see D3 below); ADR-116 / ADR-121 (the GRC /
adopt-pack program the packs serve); the `adopt-pack` surface (`src/cli/resources/project/
adopt_pack.py`) which reads the catalog and writes each pack's rules + mappings into the *target*
repo.
**Motivating evidence:** The 2026-07-14 full constitutional audit reported 94% effective coverage
with 12 "unmapped" rules. All 12 are exactly the rules of the three adoptable packs
(`architectural_boundaries`, `python_hygiene`, `starter_python`). CORE's own constitution is
effectively 100% enforced; the 6% "gap" is CORE's self-audit counting the products it ships for
others against its own self-governance score — because those products physically sit under
`.intent/`.

---

## Context

`.intent/` is CORE's law: the constitution, rules, enforcement mappings, and META schemas that
CORE reads at runtime to govern *itself*. `IntentRepository` is the single sanctioned reader.

Governance **packs** (`.intent/packs/*.yaml`, `kind: governance_pack`) are a different thing.
`.intent/META/governance_pack.schema.json` defines them precisely: *"a self-contained, versioned
bundle of rule definitions and enforcement mappings that external projects can adopt with a single
declaration. Packs are the external-adoption unit."* They are **products shipped for others** —
`core project adopt-pack` reads the catalog and writes a pack's rules + enforcement mappings into
the **consumer's** repo, where the consumer's audit enforces them.

Two facts show the boundary is already *half* drawn:

1. **Logically, packs are already excluded from CORE's constitution.** The rule-index loader skips
   them outright — `if data.get("kind") == "governance_pack": continue`
   (`intent_repository.py`). They are read only by a separate `PackLoader`, never entered into the
   rule index. So packs do **not** pollute CORE's *enforced law*.
2. **The consumer starter already lives outside `.intent/`.** ADR-108 D2 version-controls the
   delivered starter at `examples/starter-intent/`, not in `.intent/`.

But the pack **instances still physically sit under `.intent/packs/`** — inside the tree a reader
(and the constitutional auditor) treats as "CORE's law." This produces two problems:

- **A measurement falsehood.** The self-audit's coverage denominator counts the 12 pack rules even
  though the rule index excludes them, deflating CORE's own-constitution coverage from ~100% to
  94% and mislabeling shipped products as CORE's self-governance gaps.
- **A legibility falsehood.** ADR-108 D4's own boundary text calls the declared-only set "CORE's
  *own* Class-A unmapped rules" — but they are pack content, not CORE's own. The layout makes a
  reader believe products are law.

The starter is out; the packs are in. That inconsistency is the thing to close.

## Decision

### D1 — Adoptable governance packs live outside the self-law root

Pack **instances** (`kind: governance_pack` declarations) MUST NOT live under `.intent/`. They move
to a top-level `packs/` directory (sibling to `.intent/`, `src/`, `examples/`), the pack registry /
catalog. Rationale: `.intent/` is CORE's *own* law; a pack is a product CORE ships for others to
adopt. Co-locating the two makes products read as law and lets shipped content contaminate CORE's
self-governance metrics. This extends to the pack catalog the exact boundary ADR-108 D2 already
drew for the consumer starter.

### D2 — The pack *format* schema is self-law and stays in `.intent/`

`.intent/META/governance_pack.schema.json` — the schema that defines what a valid pack MUST look
like — remains under `.intent/`. Governing the *shape* of a pack is CORE's self-governance; only
the pack *instances* are products. This split is the load-bearing distinction: **CORE's law about
packs stays in `.intent/`; the packs themselves do not.**

### D3 — Clarify ADR-108 D4: "single law root" is corpus co-location, not physical residency

ADR-108 D4 requires that a rule and its enforcement mapping be read as **one corpus from the same
root — the law root, never split across the code-under-audit root (`repo_path`)** (the OPA-bundle
lesson). This ADR affirms D4 and clarifies its scope: the invariant is that a rule and its mapping
travel **together**, not that all governance content resides physically under `.intent/`. Each pack
is already a self-contained corpus — a single `*.yaml` carrying both `rules` and
`enforcement_mappings` — so the invariant travels with the pack file wherever it lives. Moving packs
to `packs/` does not split any rule from its mapping and therefore does not weaken D4.

### D4 — The self-audit denominator corrects structurally; fix ADR-108 D4's mislabel

With packs no longer under `.intent/`, the constitutional auditor no longer discovers or counts
them — the coverage denominator reflects CORE's own constitution with **no special-case exclusion
needed**. This is the structural fix (packs are genuinely not self-law, so the auditor genuinely
does not see them) rather than the metric-patch alternative (teach the auditor to ignore content
sitting in the law directory). ADR-108 D4's boundary text — which calls the declared-only set
"CORE's own Class-A unmapped rules" — is corrected by append-only note to reflect that the prior
declared-only set was pack content, now relocated.

### D5 — Implementation (bounded; ~4 files)

1. Move `.intent/packs/{architectural_boundaries,python_hygiene,starter_python}.yaml` →
   `packs/`.
2. Re-point `PackLoader`'s root: `intent_repository.py` `list_packs()` / `get_pack()` construct
   `PackLoader(self._root / "packs")` — change to the repo-root `packs/` directory (via the
   sanctioned path resolver, not a raw literal).
3. Update `adopt_pack.py` catalog reads and `pack_loader.py` docstrings (`.intent/packs/` → the
   new root).
4. Update `tests/shared/infrastructure/intent/test_pack_loader.py` fixtures/paths.
5. Verify: `core project adopt-pack core/starter-python --target-dir <tmp>` still previews/writes;
   a full `core-admin code audit` shows the 12 pack rules gone from the declared/unmapped set and
   effective coverage of CORE's own constitution at ~100%.

## Consequences

- CORE's self-audit stops counting shipped products against its own governance score; the coverage
  number becomes an honest measure of CORE's own constitution.
- The self-law / products boundary is legible at the directory level: `.intent/` = CORE governs
  itself (incl. the pack *schema*); `packs/` = governance products CORE ships; `examples/
  starter-intent/` = the delivered consumer starter. Products live outside the self-law root,
  uniformly.
- `IntentRepository` remains the reader of `.intent/`; `PackLoader` remains the separate reader of
  the pack catalog — its root simply moves. No new reader is introduced (the separation already
  existed at the loader level; only the path changes).
- One-time churn across ~4 files and the pack fixtures. No change to the pack *format*, the
  `adopt-pack` contract, or any consumer-visible behavior.

## Open questions (for the governor)

1. **Location name.** `packs/` at repo root (proposed) vs. `governance-packs/` (more explicit) vs.
   grouping under `examples/` alongside the starter. Recommend top-level `packs/` — it is a real
   product registry, not an example.
2. **Does the pack schema truly stay, or move with the instances?** D2 argues the schema is
   self-law (CORE governs pack shape) and stays. If the governor considers the schema itself a
   shipped artifact, it could move too — but then CORE loses its own governance over what a valid
   pack is.
3. **Amendment vs. new ADR.** This could instead land as an ADR-108 D-section (it extends D2's
   boundary). Filed as a standalone ADR because it decides a placement ADR-108 left implicit and
   touches a second ADR's (D4's) framing; fold into ADR-108 if the governor prefers.
