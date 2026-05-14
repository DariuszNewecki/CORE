# CORE — GitHub Project Management

**Status:** Active
**Authority:** Policy
**Location:** `.specs/planning/CORE-GitHub-Project-Management.md`
**Scope:** GitHub as the operational work-tracking surface for CORE development
**Relates to:** `SESSION-PROTOCOL.md`, `INTERACTION-CONTRACT.md`, `CORE-A3-plan.md`

---

## 1. Purpose

This document defines what "proper project management on GitHub" means for CORE,
what the current state is, what is missing, and what activities will close the gap.

The audience is the governor and any architect instance opening a session that
involves work-tracking setup or maintenance.

---

## 2. Goal

A governor who is not a programmer should be able to answer the following questions
by opening a browser tab — without running a CLI command or reading a markdown file:

- What is the current band, and how many issues remain open in it?
- What is blocked, parked, or pending verification right now?
- What does the next band contain?
- What governance debt is outstanding?

The GitHub Projects board is the instrument that makes this possible.
It does not replace `.specs/` governance artifacts — ADRs, papers, and the A3 plan
remain authoritative. It replaces the need to query `gh issue list` to see
work status.

---

## 3. What already exists

The following is in place and should not be changed without cause.

### 3.1 Label taxonomy (~33 labels as of 2026-05-14)

**Type labels** — classify what an issue is:

| Label | Meaning |
|---|---|
| `type:task` | Concrete implementation or fix work |
| `type:feature` | New capability or behaviour |
| `type:bug` | Defect in existing behaviour |
| `type:adr` | An architectural decision record to be authored |
| `type:architecture` | Structural or design decision affecting system shape |
| `type:investigation` | Exploratory work with uncertain outcome |
| `type:question` | A decision or clarification the governor must make |
| `type:security` | Security vulnerability or Dependabot alert |
| `type:docs` | Documentation work |
| `type:cli` | CLI surface work |
| `type:tooling` | Dev tooling, scripts, automation |
| `type:ci` | CI/CD pipeline work |
| `type:epic` | Container issue grouping related tasks |
| `type:vision` | Strategic direction items |

**Priority labels**:

| Label | Meaning |
|---|---|
| `priority:high` | Blocking or band-defining |
| `priority:medium` | Normal band work |
| `priority:low` | Housekeeping, cosmetic debt, no urgency |

**Status labels** — workflow state beyond open/closed:

| Label | Meaning |
|---|---|
| `status:blocked` | Cannot proceed without external resolution |
| `status:parked` | Deliberately deferred, not abandoned |
| `status:verification-pending` | Implementation done; runtime confirmation needed |

**Cross-cutting labels**:

| Label | Meaning |
|---|---|
| `governance-debt` | Governance gap that must be closed |
| `hazard` | Known risk that can cause session or system failure |
| `false-positive` | Audit finding confirmed to be incorrect |
| `audit` | Relates to the audit system specifically |
| `db` | Database schema, migrations, or query changes |
| `organizational` | Process, protocol, or team structure |
| `roadmap` | Strategic planning items |
| `dependencies` | Third-party dependency management |
| `github_actions` | CI/CD automation |
| `python` | Python-specific technical issues |

**Band labels** — milestone affiliation when an issue spans multiple sessions:

| Label | Meaning |
|---|---|
| `band:D` | Band D follow-up work |

### 3.2 Milestones

Five band milestones: Band A (closed), Band B (closed), Band C (closed),
Band D (closed), Band E (open). One per band. Band closure triggers milestone close.

Seven legacy release milestones exist from pre-band era. These are historical
and require no maintenance.

### 3.3 Issue writing template

Defined at `SESSION-PROTOCOL.md §6`. Four sections:
- **What it is** — one paragraph description
- **Why it's here** — session context and circumstances
- **What would close it** — bullet list of closure conditions
- **References** — commits, issues, ADRs, papers

### 3.4 Session integration

`SESSION-PROTOCOL.md` defines when issues are opened (during sessions, not deferred)
and closed (session close, Step 2). This discipline is correct and should be preserved.

---

## 4. What is missing

### 4.1 GitHub Projects board

No Projects V2 board exists. Band and issue status is only queryable via CLI.
This is the primary gap: the governor has no visual work-tracking surface.

### 4.2 Label gaps — resolved 2026-05-14

Both label gaps identified here have been closed:

- `priority:low` is in the catalog (description: "Low urgency; park until
  higher priorities clear", color `#e4e669`).
- `type:security` was added 2026-05-14 (description: "Security vulnerability
  or Dependabot alert; warrants prompt triage", color `#d73a4a`).

The remaining content of §6 is retained as historical record of the addition.

### 4.3 Open items not fully materialized as issues — referent gap

This section was written assuming `CORE-A3-plan.md` carried an explicit
"open items" subsection that doubled as a shadow tracker. As of 2026-05-14
that subsection no longer exists — the plan currently holds only: What A3
Is, A3 Gates, A3 Phases, Bands, Architectural Decisions Made, Key Commands,
Architecture Reference. The Bands section lists milestone links and closure
status only, not specific open items.

Two possible readings of activity §9 row 6 are now defensible:

1. **Already complete.** Open items were materialized as issues at some
   earlier point and the A3-plan section was retired; this planning paper
   simply wasn't updated.
2. **Activity needs reframing.** "Open items" should be interpreted against
   another tracker — e.g., items currently surfaced only in commit messages,
   in `.specs/papers/`, or in this session's triage findings (e.g., #258,
   #294, #305, #309, #157 — all surfaced as "needs governor decision" with
   no covering issue body change).

Governor decision needed before activity §9 row 6 can run.

### 4.4 Projects board not referenced in SESSION-PROTOCOL

Once the board exists, the session-open state scan (`SESSION-PROTOCOL §3 Step 2`)
should reference it as the primary visual surface, with CLI queries as the
verification fallback.

---

## 5. Projects board design

### 5.1 Views to create

Three views, each answering a different governor question:

| View name | Type | Groups by | Primary use |
|---|---|---|---|
| **Band board** | Board | Status field | What is in-progress, blocked, or done this band? |
| **Roadmap** | Roadmap | Milestone | What does the multi-band arc look like? |
| **Governance debt** | Table | Label filter: `governance-debt` | What constitutional debt remains? |

### 5.2 Status field (kanban columns)

GitHub Projects V2 provides a built-in `Status` field. This is distinct from
status labels. The field drives kanban column placement; labels drive filtering
and classification. They are complementary, not redundant.

Proposed Status field values:

| Value | Meaning |
|---|---|
| `Backlog` | Planned but not started |
| `In progress` | Active work this session |
| `Blocked` | Waiting on external resolution |
| `Verification pending` | Done; needs runtime confirmation |
| `Done` | Closed |

Note: `status:blocked` and `status:verification-pending` labels remain on issues
for filter queries. The Projects Status field is for visual placement only.

### 5.3 Custom fields (optional)

One optional custom field adds value without complexity:

**`ADR`** — text field, free-form. Populated when an issue has a governing ADR
(e.g. `ADR-031`). Enables filtering "show me all issues whose work is
governed by an existing ADR."

No other custom fields are needed at this stage. Over-engineering the Projects
schema defeats the goal of simple visual oversight.

---

## 6. Label taxonomy additions — complete 2026-05-14

Both labels are live in the catalog:

| Label | Color | Description | Added |
|---|---|---|---|
| `priority:low` | `#e4e669` (pale yellow) | Low urgency; park until higher priorities clear | (in catalog before this paper) |
| `type:security` | `#d73a4a` (red) | Security vulnerability or Dependabot alert; warrants prompt triage | 2026-05-14 |

No labels to remove. The catalog currently holds ~33 entries; the 25-label
baseline cited earlier in this document has grown organically with new
classifications (e.g. `type:bug`, `type:architecture`, `db`, `band:D`)
landing alongside the additions specified here.

---

## 7. Open item materialization

All items currently described in `CORE-A3-plan.md` as open work should become
GitHub issues before Band E begins. The A3-plan's open-items section is then
retired — the plan holds gates, phases, bands, and ADR index only.

The materialization pass:

1. Read the current open items list from `CORE-A3-plan.md`
2. For each item: author an issue body using the `SESSION-PROTOCOL §6` template
3. Assign labels from the governed catalog
4. Assign milestone (Band E if band-appropriate; no milestone if unbanded)
5. Add to the Projects board via auto-add rule (all issues in repo) or manually

This is a single Claude Code session task, not ongoing work.

---

## 8. SESSION-PROTOCOL integration

After the board is live, `SESSION-PROTOCOL.md` requires one amendment:

**§3 Step 2 (State scan)** — add the Projects board URL as the first navigation
target. The existing `gh` CLI commands become the verification step if the board
state is ambiguous.

**§2 "Where things live" table** — add a row:

| GitHub Projects board | Visual band status, kanban, roadmap | Maintained as issues open and close |

No other SESSION-PROTOCOL changes are needed.

---

## 9. Implementation activities

Ordered. Each is a discrete Claude Code task unless noted.

| # | Activity | Who | Output | Status (2026-05-14) |
|---|---|---|---|---|
| 1 | Add `priority:low` and `type:security` labels | Claude Code | Two new labels in repo | ✅ Complete — both in catalog |
| 2 | Create GitHub Projects V2 board with three views | Claude Code | Board live at `github.com/DariuszNewecki/CORE` | ⏸ Blocked on `gh auth refresh -s project,read:project` |
| 3 | Configure Status field with five values | Claude Code | Kanban columns usable | ⏸ Blocked on #2 |
| 4 | Add `ADR` custom text field | Claude Code | Field available on all issues | ⏸ Blocked on #2 |
| 5 | Enable auto-add rule (all repo issues join project) | Claude Code | Existing issues populate board | ⏸ Blocked on #2 |
| 6 | Materialize A3-plan open items as issues | Claude Code | All open items as proper issues | ⚠ Referent unclear — see §4.3 |
| 7 | Triage board: assign Status field to all open issues | Governor | Board reflects actual state | ⏳ Pending #2 |
| 8 | Amend SESSION-PROTOCOL §3 and §2 | Governor (`.specs/` is governor-only) | Protocol references board | ⏳ Pending #2 |

Activity 7 is governor work — only the governor can judge whether an issue
is Backlog vs In progress vs Blocked. It cannot be delegated to Claude Code.

Activity 8 is governor-territory by constitution (`.specs/planning/` is
governor-authored).

---

## 10. Success criteria

The setup is complete when:

- The governor can answer all four questions from §2 Goal by opening one
  browser tab.
- Every open item from the A3-plan is a GitHub issue on the board.
- SESSION-PROTOCOL references the board as the primary visual surface.
- The label catalog covers every category in §3.1 and §6 (≥ 33 entries
  as of 2026-05-14, growing as new classifications emerge).
- The board has three configured views: Band board, Roadmap, Governance debt.

---

## 11. Non-goals

This paper does not govern:

- The content of ADRs, papers, or the A3 plan — those remain in `.specs/`.
- The CORE runtime governance system — GitHub is a human coordination tool,
  not a CORE-governed artifact.
- PR workflows or branch protection — CORE uses direct commits to main;
  this remains unchanged.
- Issue assignment to contributors other than the governor — CORE is a
  solo-governed project at this stage.
