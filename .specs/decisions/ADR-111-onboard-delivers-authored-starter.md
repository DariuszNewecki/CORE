---
kind: adr
id: ADR-111
title: ADR-111 — `project onboard` delivers the authored starter-intent (BYOR code×Induce cell)
status: accepted
---

<!-- path: .specs/decisions/ADR-111-onboard-delivers-authored-starter.md -->

# ADR-111 — `project onboard` delivers the authored starter-intent, it does not generate one

**Status:** Accepted — governor-ratified 2026-06-17
**Date:** 2026-06-17
**Grounding paper:** `CORE-BYOR.md` (§4 the code×Induce cell; §8 byor.py disposition) — primary.
**Builds on:** ADR-108 (external adoption ships a minimal *authored* starter, not a copy), ADR-075 (framework/project namespace), ADR-095 D1 (drift is named, not papered over).
**Operationalizes:** UR-04 (Constitution Before Artifact) — primary; UR-01 (Universal Input Acceptance) — secondary.
**Closes:** #640 step 1 (the BYOR command works); unblocks #640 step 2 (newcomer docs).

---

## Context

`CORE-BYOR.md` defines BYOR as the adoption surface over a typed Repository and
names three configurations. The **code × Induce** cell — an adopter brings a code
repository that has no `.intent/`, and CORE must establish one — is today served
by `core-admin project onboard` (`src/cli/logic/byor.py`). That implementation is
both broken and built on the wrong premise (#640):

- **Broken:** it reads templates from `src/features/project_lifecycle/starter_kits/default/`,
  a path that was never created after the Wave-4 refactor; the `read_text()` calls run
  unconditionally before the dry-run branch, so it crashes even in `--dry-run`.
- **Wrong premise:** it runs `KnowledgeGraphBuilder` over the target repo and
  *generates* a constitution from what the code already does. This inverts CORE's
  thesis — intent is the prescriptive law the artifact must obey, not a description
  induced from the artifact (`CORE-BYOR.md` §5 parameter 1). It is also heuristically
  hollow on real external repos (`domain_map` returns `{}`; capability discovery needs
  `# CAPABILITY:` comments external repos do not have), producing a near-empty file
  that *looks* like governance while enforcing almost nothing.

ADR-108 already created the right artifact: `examples/starter-intent/.intent/` — a
small, *authored*, drift-guarded constitution (four universal, deterministic,
LLM-free rules) plus the irreducible machinery floor an offline audit requires.
What is missing is the delivery mechanism that puts it into an adopting repo.
This ADR decides that mechanism. It does not modify the starter; it consumes it.

## Decision

### D1 — `project onboard <target>` *delivers* the authored starter, it does not generate one

`project onboard <target>` copies the canonical starter payload —
`examples/starter-intent/.intent/` — into `<target>/.intent/`. The payload is the
**machinery floor** (`META/`, `taxonomies/`, `enforcement/config/`, the
`enforcement/mappings/starter.yaml` binding) plus the **starter constitution**
(`constitution/CONSTITUTION.md`, `rules/starter.json` — `symbol_ids` blocking;
`docstrings`, `no_print`, `no_bare_except` reporting). Delivery is a copy of an
authored artifact, never a synthesis from the target's code.

### D2 — Code-analysis generation is removed from the authoritative path

`KnowledgeGraphBuilder` is no longer used to author constitution content. No part
of the delivered `.intent/` is induced from the target repo. If a future enhancement
offers code-analysis output, it ships only as an explicitly-labelled, non-authoritative
**suggestion** for the human to consider (`CORE-BYOR.md` §8) — out of scope for this
cell. The delivered law is the adopter's to read, ratify, and extend (UR-04, UR-08).

### D3 — Safety and command semantics

- **No overwrite.** If `<target>/.intent/` already exists, onboard refuses with
  guidance (the adopter already has a constitution; CORE will not silently replace it).
- **Dry-run is the default.** The default invocation previews the tree that *would*
  be delivered; `--write` applies it. All writes route through the **`file.create`
  atomic action via `ActionExecutor`** — the sanctioned scaffold surface (`project new`
  uses the same). A direct `FileHandler.write` on a literal `.intent/` path is
  hard-blocked by the governed-artifact tier (constitution-read-only); delivery
  therefore addresses the external repo through a CORE-root-relative path that does
  not match the `.intent/` prefix and so classifies as writable.
- **Minimal identity stamp.** The adopting repo's name is stamped where the starter
  expects a project identity; no other content is mutated. Delivery is otherwise
  byte-for-byte the authored starter.

### D4 — Source of truth and the packaging dependency, stated honestly

`examples/starter-intent/` is the single source of truth for the payload (ADR-108 D2);
onboard copies *from* it. Invocation from the CORE source tree works immediately.
Invocation from an installed `core-runtime` wheel requires the starter to be packaged
with the distribution — **ADR-108 D3 (machinery-in-wheel), which is deferred.** This
ADR does not assume D3 is done: until it lands, wheel-based onboard is gated and must
fail loud with that reason rather than silently delivering nothing.

### D5 — Namespace and ownership

The delivered tree becomes the adopter's own `.intent/`. Per ADR-075, in adopter terms
the rules layer is theirs to author (`project::<external>`) and the machinery floor is
framework-owned. Keeping the framework floor in sync with CORE upgrades (re-delivery /
upgrade path) is a separate concern, out of scope here.

### D6 — This completes the on-ramp's first step

With D1–D5, `project onboard` produces a `.intent/` that the F-10 offline audit (the
CI gate) can run against — closing the `cold-reviewer.md` "no `.intent/` → the action
fails" dead-end. Surfacing BYOR in the newcomer docs (#640 step 2) is unblocked and
follows in a separate change; it MUST NOT promise the self-serve path until D1–D5 ship.

## Consequences

- **The on-ramp becomes honest and small.** An external repo gets a legible, four-rule
  constitution it can understand and extend — not a 248-file copy of CORE's `.intent/`
  (rejected by ADR-108) nor a hollow generated file (rejected here).
- **The philosophical inversion is removed.** CORE stops deriving law from the artifact;
  the human owns the law from the first commit (UR-04).
- **One dependency is exposed, not hidden:** wheel-based onboard waits on ADR-108 D3.
- **The starter's drift-guard becomes load-bearing for adopters too:** because onboard
  ships exactly `examples/starter-intent/`, CORE's own audit of that directory now
  protects every adopter's starting point. Keep `sync-to-demo.sh` and the starter audit green.
- **`byor.py` is rewritten, not patched:** the dead `TEMPLATES_DIR`, the unconditional
  `read_text`, and the `KnowledgeGraphBuilder` generation path are removed.

## Alternatives considered

- **Keep the generator, just fix the path.** Rejected: repairing the template path leaves
  the inverted premise (law induced from code) and the empty-scaffold problem intact.
- **Copy CORE's full `.intent/`.** Rejected by ADR-108: a ~248-file blob is hostile to
  adopt and drift-prone; it enforces, in practice, a handful of rules behind enormous surface.
- **LLM-generate a bespoke constitution per repo.** Rejected: an un-ratified, machine-authored
  constitution violates "humans write the law" (UR-08) and the defensibility invariant.

## References

- `CORE-BYOR.md` — grounding paper; §4 (code×Induce cell), §5 (intent-provenance asymmetry),
  §8 (byor.py disposition), §9 (this is grounded ADR #2).
- ADR-108 — external adoption ships a minimal authored starter, not a copy (D2 source-of-truth;
  D3 machinery-in-wheel, the deferred dependency).
- ADR-075 — framework/project namespace split.
- `examples/starter-intent/.intent/` — the canonical delivery payload.
- `src/cli/logic/byor.py`, `src/cli/resources/project/onboard.py` — the implementation to rewrite.
- #640 — BYOR non-functional (step 1 closed by this ADR; step 2 unblocked).

---

## Amendment — 2026-06-20 (ADR-119)

### A1 — D1 revised: `project onboard` delivers machinery floor only

ADR-119 establishes that `project onboard` is Phase A of Scout's two-phase delivery. It
delivers the machinery floor only; it no longer delivers the four-rule starter constitution.

**D1 is amended:**

`project onboard <target> [--write]` copies the machinery floor from
`examples/starter-intent/.intent/` into `<target>/.intent/`. Specifically:

- `META/` (bootstrap schemas, enums.json, vocabulary.json and schema)
- `taxonomies/` (operational_capabilities.yaml, cognitive_roles.yaml,
  filesystem_operations.yaml)
- `enforcement/config/` (action_risk.yaml and companions)

It does **not** copy `constitution/`, `rules/`, or `enforcement/mappings/` (the rules
layer). Those are Scout's domain (`project scout`, Phase B).

An operator who wants rules follows with `project scout <target> [--write]` (Phase B), or
authors rules manually (Guard path). The delivery is still a copy of authored artifacts,
never a synthesis from the target's code — D1's original "not generated, authored" invariant
is preserved and tightened.

### A2 — D6 revised: the on-ramp now has two explicit steps

ADR-111 D6 stated: "With D1–D5, `project onboard` produces a `.intent/` that the F-10
offline audit can run against." This is no longer fully true after the scope narrowing.
After machinery-only delivery, the offline audit finds no rules and returns a
governance-collapse `ERROR` (per ADR-108 D4) — which is the correct signal: machinery is
present, no law has been ratified yet.

D6 is amended: `project onboard` completes the first step; `project scout` (or manual rule
authoring) completes the second. Together they produce a `.intent/` the F-10 audit can run
against productively. The `docs/cold-reviewer.md` newcomer docs (T2) must describe both
steps. ADR-111 D6's invariant that docs MUST NOT promise the self-serve path until delivery
is complete is preserved — the bar is now Phase A + Phase B shipped, not Phase A alone.
