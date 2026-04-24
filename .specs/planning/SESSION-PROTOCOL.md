<!-- path: .specs/planning/SESSION-PROTOCOL.md -->

# CORE — Session Protocol

**Status:** Active
**Authority:** Policy
**Scope:** All CORE development sessions between governor and architect

---

## 1. Purpose

This document defines how a CORE working session opens, runs, and closes. It replaces the previous pattern of producing long narrative handoff documents under `.specs/planning/` with a split: durable architectural artifacts stay under `.specs/`, operational work-tracking lives on GitHub.

The audience is the governor and any architect instance (human or Claude) opening or closing a working session on CORE.

---

## 2. Where things live

| Location | Role | Cadence |
|---|---|---|
| `.specs/decisions/` | ADRs — architectural decisions with rationale | Append-only; rare updates |
| `.specs/papers/` | Constitutional papers | Append-only; rare updates |
| `.specs/northstar/` | Strategic direction documents | Rarely touched |
| `.specs/requirements/` | URS documents | Updated on major feature arcs |
| `.specs/META/` | Schemas governing `.specs/` and `.intent/` documents | Updated when conventions change |
| `.specs/state/` | Investigations and historical snapshots cited by ADRs or papers | Append-only; dated artifacts |
| `.specs/planning/CORE-A3-plan.md` | Strategic roadmap — bands, phases, known blockers | Updated when a band advances or a blocker resolves |
| `.specs/planning/SESSION-PROTOCOL.md` | This document | Revised when the protocol itself changes |
| `.intent/` | Runtime governance — constitution, rules, enforcement, workers | Updated as governance evolves |
| GitHub Issues | Parked items, hazards, open questions, verification-pending, governance-debt | Opened and closed every session |
| GitHub Milestones | One per band (A through E); the strategic progress surface | Updated as issues close |
| GitHub Discussions | Architectural questions needing broader input | Opt-in |
| GitHub Releases | Capability milestones ("Band X closed" or "vN.N.N") | On band closure or major milestone |
| Git commit history | The authoritative record of what changed and when | Generated as sessions run |

What is no longer kept: long-form handoff documents under `.specs/state/handoffs/handoff-*.md`. The existing archive (pre-this-protocol) remains as historical record; no new ones are produced. Session activity is reconstructible from Git history, GitHub Issue events, and GitHub Releases — no separate session log is maintained.

---

## 3. Session opening

Five steps. Reads first, commits nothing.

**Step 1 — System state scan.** Run `core-admin code audit` and record the verdict and finding count. Check `systemctl --user status core-daemon` for daemon liveness. If either is unexpectedly off baseline, that observation precedes any lead selection.

**Step 2 — GitHub state scan.** Open the repository's Issues tab filtered by relevant state labels. Default filter set:
- `status:verification-pending` — has anything passively verified since last session?
- `status:blocked` — has a blocker upstream of something resolved?
- Open issues on the current band's milestone — what's queued?

Close anything that has resolved. Do this first because closures free up pick candidates.

**Step 3 — Candidate list.** From remaining open issues, identify 2-4 candidates for the session's lead. Preference order: items surfaced last session, items `priority:high`, items on the currently-advancing band's milestone.

**Step 4 — Pick one lead.** The governor picks. The architect can propose and argue, but the pick is the governor's. Name it explicitly and state the expected session outcome in one sentence.

**Step 5 — Commit to the lead.** Once chosen, stop evaluating candidates. The parked list is a feature, not a backlog to clear. Newly-surfaced items during the session become new issues, not new leads.

---

## 4. Session running

The interaction contract between governor and architect governs the session itself (verify before proposing, complete files not diffs, exact Claude Code prompts, one focused question per turn, stop-and-report). That contract is not re-specified here.

One protocol note: when the session surfaces a new parked item, hazard, governance-debt, false-positive, or open question, it is **opened as a GitHub issue during the session**, not deferred to session close. Opening is cheap; deferring causes loss.

---

## 5. Session closing

Four steps. Most are one-line actions.

**Step 1 — Commits.** Work-product commits landed during the session using the governor's existing multi-line commit message discipline. Push to origin if the state is coherent.

**Step 2 — Issues updated.** Close any issues resolved by this session's commits. Confirm labels still accurate on open issues.

**Step 3 — A3 plan maintenance.** If a blocker resolved or a band advanced, edit `CORE-A3-plan.md`: move the resolved row from "Known Blockers" to "Resolved Blockers," update "Milestone Summary," add a row to "Architectural Decisions Made" if an ADR landed.

**Step 4 — Release if warranted.** If a band closed or a major capability milestone landed, cut a GitHub Release with the relevant tag (`vN.N.N` per existing convention). Band closure is the canonical trigger. Release notes are the canonical session summary for bands that ship.

---

## 6. Issue writing template

When opening an issue during or after a session, use this minimal structure in the issue body:

```
## What it is

<One paragraph. What is the parked item / hazard / question / verification-pending thing?>

## Why it's here

<One paragraph. Which session surfaced it, under what circumstances, what was the context?>

## What would close it

<Bullet list. What are the conditions under which this issue gets closed?>

## References

- Commits: <sha, sha>
- Related issues: #N, #N
- Related ADRs: ADR-NNN
- Related papers: `papers/CORE-X.md`
```

Labels applied per the governed catalog. Milestone assigned per band if the item belongs to a specific band's strategic arc. Unbanded items stay milestone-less.

---

## 7. When the protocol itself changes

This document is governance text. Changes go through the governor directly — not through Claude Code. Revisions land as commits to `.specs/planning/SESSION-PROTOCOL.md` with a short commit message explaining what changed and why. Major revisions warrant an ADR.

---

## 8. Non-goals

This document does not specify:
- The interaction contract between governor and architect during active work (that contract is governor-set per session).
- Coding or designing workflows beyond the session-open/session-close bookends.
- Issue-label semantics (see the label catalog on GitHub; each label carries its governing description).
- Band definitions or strategic scope (see `CORE-A3-plan.md`).

---

*This protocol was established as part of the Band A closure session (2026-04-24) when the previous `handoff-*.md` pattern reached structural strain. It is expected to evolve as operational experience with the GitHub-tracking split accumulates.*
