<!-- path: .specs/planning/SESSION-PROTOCOL.md -->

# CORE — Session Protocol

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
| `.specs/commercial/` | Private commercial material (e.g. tech-rep onboarding) | Gitignored; not published |
| `.specs/commercial/cadence.md` | Working cadence — three modes, trigger rules, weekly rhythm, content channel priority | Revised when goals or constraints change |
| `.specs/commercial/PR-XX/` | Pharma pilot (unnamed) — requirements, product position, build gap, demo plan | Updated as pilot progresses |
| `.specs/planning/CORE-Operational-Completeness.md` | Operational tracker — ADR-085 5+3 gate (post-A3) | Updated per its §4 rules when a 5+3 feature ships or quality goal advances |
| `.specs/planning/archive/CORE-A3-plan.md` | Historical — A3 milestone closure record (A3 closed 2026-05-12; archived 2026-06-07) | Frozen content; ADR index in this file ends at ADR-076 |
| `.specs/planning/SESSION-PROTOCOL.md` | This document | Revised when the protocol itself changes |
| `.specs/planning/INTERACTION-CONTRACT.md` | Operating contract between governor and architect | Loaded at session-open Step 1; revised when the contract itself changes |
| `.intent/` | Runtime governance — constitution, rules, enforcement, workers | Updated as governance evolves |
| `.intent/CHANGELOG.md` | Constitutional version history — anchors each ADR to the governance change it represents | Updated every time an ADR lands |
| GitHub Issues | Parked items, hazards, open questions, verification-pending, governance-debt | Opened and closed every session |
| GitHub Milestones | One per band (A through E); the strategic progress surface | Updated as issues close |
| GitHub Projects board | Visual band status — kanban, roadmap, governance-debt views | Updated automatically as issues open and close |
| GitHub Discussions | Architectural questions needing broader input | Opt-in |
| GitHub Releases | Capability milestones ("Band X closed" or "vN.N.N") | On band closure or major milestone |
| Git commit history | The authoritative record of what changed and when | Generated as sessions run |

What is no longer kept: long-form handoff documents under `.specs/state/handoffs/handoff-*.md`. The existing archive (pre-this-protocol) remains as historical record; no new ones are produced. Session activity is reconstructible from Git history, GitHub Issue events, and GitHub Releases — no separate session log is maintained.

Note: gitignored subtrees (`.specs/commercial/`) exist alongside the published ones and are not reflected in the repo or context packets.

---

## 3. Session opening

Seven steps. Reads first, commits nothing.

**Step 1 — Contract load.** The architect loads `.specs/planning/INTERACTION-CONTRACT.md` before any state scan. A fresh architect instance that has not loaded this document is not yet operational — the governor is owed the load before being asked anything substantive. This step is the architect's responsibility; the governor verifies it has happened by observing the architect's first turn.

**Step 2 — Context read.** The architect reads the two Project Files context packets via the `view` tool at `/mnt/project/`:
- `context_tree.txt` — read first; small filtered directory tree for structural navigation.
- `context_intent_specs.txt` — full `.intent/` and `.specs/` snapshot; grepped as needed during the session. This is the architect's primary state surface: ADR table, A3 plan, constitution, rules, enforcement mappings, papers, and all governance specifications.

Both files are produced on lira by `make context` and uploaded to the Claude.ai Project before the session opens. They reflect the state of the repo at last sync. If they are absent or stale, the governor runs `make context` and re-uploads before proceeding. The architect does not ask the governor to upload or paste code mid-session; the Project Files upload is the delivery mechanism.

Tool preference order for data needs within a session: `view` / `bash_tool` against the Project Files first; Claude Code prompts for anything requiring live system state or `src/` code content (Steps 3–4 below, and any code-level reconnaissance during the session).

**Step 3 — System state scan.** The architect produces a Claude Code prompt that the governor runs on lira at session open. The prompt must cover: `core-admin code audit` (verdict + finding count), `systemctl --user status core-daemon` and `systemctl --user status core-api` (service liveness — both must be up; the audit CLI on :8000 depends on `core-api`). The architect does not wait for the output before proceeding to Steps 5–6; it reasons from the A3 plan and ADR table as the primary state surface. If the scan reveals an unexpected condition, the governor opens an issue and surfaces it as the session's lead candidate or a blocker.

Canonical state-scan Claude Code prompt:

```
Run the following and report the results:

1. core-admin code audit
2. systemctl --user status core-daemon
3. systemctl --user status core-api
4. core-admin runtime dashboard --plain

Report: audit verdict, total finding count, finding distribution by rule_id, daemon status, api status.
```

**Step 4 — GitHub state scan.** The architect produces a Claude Code prompt to retrieve open issue state for the current band's milestone. The governor runs it on lira. The architect uses the A3 plan and ADR table (from `context_intent_specs.txt`) as its primary state surface and does not block on GitHub output.

Canonical issue-scan Claude Code prompt:

```
Run the following and report the results:

gh issue list --milestone "Band E" --state open \
  --json number,title,labels,assignees \
  --limit 50

Also run:
gh issue list --milestone "Band E" --state open \
  --label "status:verification-pending" \
  --json number,title --limit 20

gh issue list --milestone "Band E" --state open \
  --label "status:blocked" \
  --json number,title --limit 20

gh issue list --search "no:milestone label:priority:high state:open" \
  --json number,title,labels \
  --limit 20

Report: full open issue list, verification-pending subset, blocked subset, unbanded high-priority subset.
```

Close anything that has resolved. Do this first because closures free up pick candidates.

**Step 5 — Candidate list.** From remaining open issues, identify 2–4 candidates for the session's lead. Preference order:

1. Items surfaced last session (regardless of band or milestone).
2. Banded items with `priority:high` on the currently-advancing band's milestone.
3. Unbanded items with `priority:high`.
4. Remaining banded items on the currently-advancing band's milestone.

Unbanded items without `priority:high` are not session lead candidates — they are backlog until banded or escalated. The preference order exists to make picks determinate; the governor's pick always governs.

**Step 6 — Pick one lead.** The governor picks. The architect can propose and argue, but the pick is the governor's. Name it explicitly and state the expected session outcome in one sentence.

**Step 7 — Commit to the lead.** Once chosen, stop evaluating candidates. The parked list is a feature, not a backlog to clear. Newly-surfaced items during the session become new issues, not new leads.

---

## 4. Session running

The interaction contract between governor and architect governs the session itself. The contract is canonical at `.specs/planning/INTERACTION-CONTRACT.md` and is loaded at session-open Step 1. It is not re-specified here.

One protocol note: when the session surfaces a new parked item, hazard, governance-debt, false-positive, or open question, it is **opened as a GitHub issue during the session**, not deferred to session close. Opening is cheap; deferring causes loss.

---

## 5. Session closing

Four steps. Most are one-line actions.

**Step 1 — Commits.** Work-product commits landed during the session using the governor's existing multi-line commit message discipline. Push to origin if the state is coherent.

**Step 2 — Issues updated.** Close any issues resolved by this session's commits. Confirm labels still accurate on open issues.

**Step 3 — Operational tracker maintenance.** A3 is closed (2026-05-12). Post-A3 operational tracking lives in `CORE-Operational-Completeness.md` (ADR-085 5+3). If this session changed something the tracker tracks, edit it per its §4 update rules:
- A 5+3 feature shipped → update §2.1 Current status + §6 Activity log.
- A quality goal advanced → update §2.2 first-met date + §6 Activity log.
- All eight items satisfied → surface to governor for the explicit D5 constraint-relaxation act (see §4 of the tracker).

ADR landings are recorded in `.intent/CHANGELOG.md` and `.specs/decisions/` is the canonical ADR record — no separate ADR index is maintained in `planning/`. The archived `CORE-A3-plan.md` ADR index is frozen at ADR-076 (2026-05-29).

If nothing the operational tracker tracks changed this session, skip this step. Routine issue closures and commits do not require tracker edits — those are reconstructible from Git and GitHub.

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
- The interaction contract between governor and architect during active work — see `.specs/planning/INTERACTION-CONTRACT.md`.
- Coding or designing workflows beyond the session-open/session-close bookends.
- Issue-label semantics (see the label catalog on GitHub; each label carries its own description).
- Band definitions or strategic scope (see `archive/CORE-A3-plan.md` for the historical band record; post-A3 scope lives in `CORE-Operational-Completeness.md`).

---

*This protocol was established as part of the Band A closure session (2026-04-26) when the previous `handoff-*.md` pattern reached structural strain. It is expected to evolve as operational experience with the GitHub-tracking split accumulates.*

*Revised 2026-04-26: §3 gained Step 1 (Contract load) and the original five steps renumbered to 2–6; §4 rewritten to reference `.specs/planning/INTERACTION-CONTRACT.md` rather than externalize the contract; §8 updated to point at the same document.*

*Revised 2026-05-02: §3 gained Step 2 (Context fetch) and the remaining steps renumbered to 3–7. Step 2 documents the Google Drive context packet delivery mechanism (`context_tree.txt` + `context_core.txt`) and the `make context` command that produces them.*

*Revised 2026-05-03: §3 Step 2 updated — Google Drive delivery replaced by Claude.ai Project Files. Context packets are uploaded to the Project before the session opens and read via the `view` tool at `/mnt/project/`. Step renamed from "Context fetch" to "Context read." Drive file IDs and `Google Drive:read_file_content` references removed. Matches INTERACTION-CONTRACT.md §3.2 revision of the same date.*

*Revised 2026-05-03: §5 Step 3 rewritten. Previous text referenced "Known Blockers," "Resolved Blockers," and "Milestone Summary" sections that the current A3 plan does not contain. New text aligns with the plan's actual section structure (A3 Gates, A3 Phases, Bands, Architectural Decisions Made). §2 row for `CORE-A3-plan.md` correspondingly updated to describe "gates, phases, bands, ADR index" rather than "bands, phases, known blockers."*

*Revised 2026-05-14: §2 gained GitHub Projects board row; §3 Step 4 updated to reference the Projects board as the primary visual surface for session-open state scan, with the Issues tab filter set retained as the verification step.*

*Revised 2026-05-17: Two-file context model adopted. §3 Step 2: `context_core.txt` replaced by `context_intent_specs.txt` (`.intent/` + `.specs/` snapshot only; `src/` code excluded). Tool preference order added to Step 2. §3 Steps 3–4: architect no longer executes these interactively; both steps now describe canonical Claude Code prompts that the governor runs on lira at session open. Architect proceeds to Steps 5–6 without waiting for output; live state surfaces through issues when decision-relevant. INTERACTION-CONTRACT.md §3.2 cross-reference to "Step 2 tooling inventory" remains valid — Step 2 now carries the tool preference order explicitly.*

*Revised 2026-05-24: Three drifts corrected. §3 Step 3: canonical state-scan prompt extended to include `systemctl --user status core-api` alongside `core-daemon`; prose updated to name both services explicitly. §2: `.specs/commercial/` row added (gitignored private commercial material); trailing note added that gitignored subtrees exist outside the context packets. §3 Step 5: preference order extended to four tiers — last-session items, banded `priority:high`, unbanded `priority:high`, remaining banded items; unbanded items without `priority:high` explicitly excluded from lead candidacy. §3 Step 4 canonical prompt gains a fourth `gh` call for unbanded `priority:high` issues to match the expanded Step 5 preference order.*

*Revised 2026-05-24: §3 Step 4 fourth `gh` call corrected. The unbanded-issue lookup originally used a non-existent `--no-milestone` flag (`gh issue list` only supports `-m, --milestone`), which would have failed with `unknown flag: --no-milestone`. Replaced with the equivalent `--search "no:milestone label:priority:high state:open"` form, which is the supported GitHub search syntax for the same filter. Verified against `gh` CLI on lira.*
