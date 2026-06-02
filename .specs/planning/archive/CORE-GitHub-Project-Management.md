# CORE — GitHub Project Management

**Status:** Superseded — operational governance moved to SESSION-PROTOCOL.md + GitHub-native surfaces
**Scope:** Pointer document. The planning content this file originally carried has been overtaken by what was built.
**Last updated:** 2026-05-24

---

## 1. Why this document is a stub

Authored 2026-05-14 as the planning artifact for a Band-tracker Projects V2 board.
The board work landed differently: **Project #6 "CORE Roadmap"** was built around the
Feature Registry (`CORE-Features.md`, ADR-065) rather than band kanban, with a richer
custom-field schema and a feature-centric layout. The board now governs ~86 items
including the F-21..F-43 backlog plus historical issues.

The original §5 board design and §9 activity table are preserved in git history.
The operational surfaces this document used to plan are now stable elsewhere.

---

## 2. Where to look now

| You want… | Look here |
|---|---|
| Label catalog (~37 entries, each carrying its own description) | GitHub Labels tab |
| Projects board | [CORE Roadmap (Project #6)](https://github.com/users/DariuszNewecki/projects/6) — public, 86 items |
| Board custom fields | `ADR` (text), `Band` (iteration), `Feature Status`, `Tier`, `Scope`, `Status` (single-selects) |
| Issue writing template | `SESSION-PROTOCOL.md §6` |
| Session-open state scan | `SESSION-PROTOCOL.md §3 Step 4` (canonical `gh issue list` prompts) |
| Session-close issue updates | `SESSION-PROTOCOL.md §5 Step 2` |
| Bands and milestones | `CORE-A3-plan.md §Bands` |
| Feature registry definitions | `.specs/papers/CORE-Features.md` (ADR-065 D4) |
| ADR-to-issue linkage convention | Custom field `ADR` on Project #6 items |

---

## 3. Original success criteria — retrospective

Assessed 2026-05-24 against the §10 criteria in the historical version of this document:

| Original criterion | State |
|---|---|
| Label catalog ≥ 33 entries | ✓ 37 entries as of 2026-05-24 |
| SESSION-PROTOCOL references the board as primary visual surface | ✓ SESSION-PROTOCOL.md §2 and §3 Step 4 (Revised 2026-05-14) |
| Every open item from A3-plan is a GitHub issue | ✓ Materialized as `[F-21]`..`[F-43]` issues (#395–#417) |
| Governor can answer band/blocker/parked/debt questions from one browser tab | Partially — Project #6 surfaces features and ADR linkage; band-level rollup lives on milestone pages |
| Three configured views: Band board, Roadmap, Governance debt | Not as proposed — Project #6 uses a feature-centric view set built around `Feature Status` / `Tier` / `Scope` instead |

The last two rows are deliberate redirections, not gaps. The Feature Registry direction
served the commercial-readiness arc (Band E) better than a band-tracker would have.

---

## 4. Non-goals (still apply)

This document does not govern:

- The content of ADRs, papers, or the A3 plan — those remain in `.specs/`.
- The CORE runtime governance system — GitHub is a human coordination tool,
  not a CORE-governed artifact.
- PR workflows or branch protection — CORE uses direct commits to main.
- Issue assignment to contributors other than the governor — CORE is a
  solo-governed project at this stage.

---

## 5. When this document changes

This document is now a pointer. Add a row to §2 if a new operational surface is
introduced (e.g., a second Projects board, a new label-catalog convention) that an
architect arriving cold should know about. Substantive policy changes belong in
`SESSION-PROTOCOL.md` or `CORE-A3-plan.md`, not here.

---

*Original 2026-05-14 content (Band-tracker planning, §5 board design, §9 activity table) preserved in git history at commits before this revision. The historical content remains accessible via `git log --follow -- .specs/planning/CORE-GitHub-Project-Management.md`.*
