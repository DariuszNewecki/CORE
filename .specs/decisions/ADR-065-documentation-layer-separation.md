---
kind: adr
id: ADR-065
title: 'ADR-065 — Documentation layer separation: `.specs/` vs `docs/`'
status: accepted
---

<!-- path: .specs/decisions/ADR-065-documentation-layer-separation.md -->

# ADR-065 — Documentation layer separation: `.specs/` vs `docs/`

**Status:** Accepted
**Date:** 2026-05-20
**Authors:** Darek (Dariusz Newecki)
**Relates to:** CORE-Features.md (`.specs/papers/`), CORE-Product-Tiers.md
(`.specs/papers/`), `docs/` directory (existing, previously ungoverned)

---

## Context

CORE maintains two directories that contain human-readable documents:

- `.specs/` — architectural decisions (ADRs), strategic papers, URS, planning
  documents. Governor-only territory. Referenced by Claude Code prompts and
  governance tooling.
- `docs/` — exists in the repository and is indexed by the vector store
  (`docs/**/*.md`, `docs/**/*.rst`), but has carried no declared governance
  rule about what belongs there or who its audience is.

As the feature registry (`CORE-Features.md`) and product tier definitions
(`CORE-Product-Tiers.md`) were authored, the question of canonical document
location surfaced. Both documents serve an internal governance audience and an
external reader audience — but not identically. The absence of a declared
layer separation means every future document decision is made without law.

This ADR declares the law.

---

## Decision

### D1 — Two layers, two audiences, two authorities

`.specs/` is the **governance layer**. Documents here are authoritative
governance artifacts: they are source of truth, they are referenced by
tooling, and they are amended by the governor under constitutional authority.
The audience is internal: the governor, the architecture, and Claude Code.

`docs/` is the **communication layer**. Documents here are reader-facing:
they communicate CORE's capabilities, design, and usage to external audiences
— contributors, customers, investors, and the public. They carry no
constitutional authority. They are derived from, or informed by, governance
artifacts; they are not governance artifacts themselves.

### D2 — Authority and derivation

`.specs/` documents are authoritative. When a `.specs/` document and a
`docs/` document describe the same subject, `.specs/` is correct by
definition. `docs/` documents that drift from `.specs/` are stale, not
contradictory.

`docs/` documents MAY reference `.specs/` documents as their authoritative
source. `.specs/` documents MUST NOT depend on or reference `docs/` for
any authoritative claim. The dependency direction is one-way:
`docs/` → `.specs/`, never the reverse.

### D3 — Document placement rules

A document belongs in `.specs/` if any of the following are true:

- It is an ADR.
- It is a URS, architectural paper, or strategic paper that governs product
  or system decisions.
- It is referenced by a governance rule, a Claude Code prompt, or an
  enforcement mapping.
- It is the source of truth for a feature, capability, or policy claim.

A document belongs in `docs/` if all of the following are true:

- Its primary audience is external (contributors, customers, investors,
  the public).
- It communicates rather than governs.
- It may be rewritten for clarity without amending any governance decision.

A document that serves both audiences is authored once in `.specs/` as the
authoritative version. A separate reader-facing version MAY be derived and
placed in `docs/`. The two are distinct documents. The `.specs/` version is
not simplified for the `docs/` version; the `docs/` version is not promoted
to the `.specs/` version.

### D4 — Specific placement decisions

| Document | Canonical location | Rationale |
|---|---|---|
| `CORE-Features.md` | `.specs/papers/CORE-Features.md` | Authoritative feature registry; governs tier packaging; referenced by Feature issues |
| `CORE-Product-Tiers.md` | `.specs/papers/CORE-Product-Tiers.md` | Authoritative tier definitions; governs commercial representation |
| Feature overview (reader-facing) | `docs/features.md` (when created) | Derived from `CORE-Features.md`; external audience; not authoritative |
| ADRs | `.specs/decisions/ADR-NNN-*.md` | Governance decisions; always `.specs/` |
| URS | `.specs/urs/` | Requirements; always `.specs/` |
| Usage guides, tutorials, API reference | `docs/` | Communication; external audience |

### D5 — GitHub Feature issues link to `.specs/`, not `docs/`

GitHub Feature issues reference `.specs/papers/CORE-Features.md#F-XX` as the
authoritative feature definition. If a `docs/` counterpart exists, it MAY be
linked as supplementary reading. The `.specs/` reference is the canonical one.

---

## Consequences

**Positive:**

- Every future document placement decision has a declared rule to follow.
  The distinction does not live in chat history; it is constitutional.
- The feature registry and tier paper have confirmed canonical locations.
  GitHub issues, roadmap items, and external references can link to them
  without the link ever becoming stale due to a document move.
- The `docs/` directory becomes a governed communication surface rather than
  an ungoverned accumulation of files.

**Negative:**

- Two versions of some documents must be maintained when both a governance
  artifact and a reader-facing version exist. The governor is responsible
  for keeping the `docs/` version current when the `.specs/` version is
  amended.

**Neutral:**

- Existing `docs/` content is not retroactively audited by this ADR. Files
  already in `docs/` that should be in `.specs/` (or vice versa) are
  governance debt to be resolved as encountered, not as a bulk migration.

---

## Verification

This ADR is verified on an ongoing basis. A violation occurs when:

1. A governance artifact (ADR, strategic paper, feature registry) is authored
   in `docs/` rather than `.specs/`.
2. A `.specs/` document is modified to depend on or reference a `docs/`
   document for an authoritative claim.
3. A `docs/` document is promoted to authoritative status without being moved
   to `.specs/` and amended as a governance decision.

No automated rule is defined here; verification is governor responsibility.
A future audit rule MAY be authored to detect placement violations
mechanically.

---

## References

- `.specs/papers/CORE-Features.md` — feature registry; D4 placement confirmed
- `.specs/papers/CORE-Product-Tiers.md` — tier definitions; D4 placement confirmed
- `docs/` directory — exists in repo; previously ungoverned; now governed by this ADR
