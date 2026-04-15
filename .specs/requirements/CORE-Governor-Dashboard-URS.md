# CORE — Governor Dashboard
## User Requirements

**Status:** Draft
**Authority:** Policy
**Scope:** `core-admin runtime dashboard` command
**Audience:** Governor (operator of CORE)

---

## 1. Purpose

The governor needs a single command that answers one question in under 10 seconds:

> **Is CORE healthy and converging — or does it need me?**

This is not a diagnostic tool. It is not a log viewer. It is a traffic-light display
for a governor who needs situational awareness without context-switching into raw DB queries
or reading multiple command outputs.

`core-admin runtime health` remains the plumbing diagnostic.
`core-admin runtime dashboard` is the governor's view.

---

## 2. The Core Requirement

The dashboard must answer five questions, each with a color signal (green / amber / red):

| # | Question | Green | Blue | Amber | Red |
|---|----------|-------|------|-------|-----|
| 1 | **Is the system converging?** | Findings resolving faster than created (today) | Flat — no net movement, or system idle | — | Findings accumulating |
| 2 | **Does the governor have items waiting?** | 0 DELEGATE + 0 approval-required DRAFT | — | Any items waiting | Backlog growing |
| 3 | **Is the loop running?** | All active workers heartbeat < 10 min | — | Any worker > 10 min stale | Worker missing or dead |
| 4 | **Is the pipeline moving?** | Proposals executing, consequences logged recently | — | Proposals stuck in APPROVED but not executing | Failed proposals, no consequence activity |
| 5 | **Is governance coverage intact?** | 100% rules mapped, 0 unmapped | — | Unmapped rules exist | Coverage below declared baseline |

Each panel shows the signal color and a single summary line of numbers.
No lists. No file paths. No stack traces. Those belong in other commands.

**Signal color grammar:**

| Color | Meaning |
|-------|---------|
| 🟢 Green | Good — system is doing what it should |
| 🔵 Blue | Neutral — no movement, no problem, no action needed |
| 🟡 Amber | Attention — something may need you soon |
| 🔴 Red | Action required — system needs governor now |

Blue is distinct from amber. Amber carries urgency. Blue is honest neutrality —
the system is not degrading, not healing, just standing still. Blue never demands action.

---

## 3. Data Sources

All data comes from the database. No filesystem reads. No subprocess calls.
The DB is the single source of truth — same principle as every other CORE sensor.

| Panel | Primary Table(s) |
|-------|-----------------|
| Convergence | `core.blackboard_entries` (findings created vs resolved, rolling 24h window) |
| Governor inbox | `core.blackboard_entries` (status = `indeterminate`) + `core.autonomous_proposals` (status = `draft`, approval_required = true) |
| Loop running | `core.worker_registry` (status, last_heartbeat) |
| Pipeline moving | `core.autonomous_proposals` (status distribution) + `core.consequence_log` (most recent entry timestamp) |
| Governance coverage | `core.blackboard_entries` aggregate OR dedicated coverage query (same source as `core-admin admin coverage`) |

---

## 4. Command Specification

```
core-admin runtime dashboard [--plain]
```

**Default mode:** Rich-formatted panels, color signals, human-readable numbers.
**`--plain` flag:** Plain text output, pipe/log/`watch` friendly. Same data, no color codes.

**Composability:** The command must be stateless and exit cleanly so it works with:
```
watch -n 30 core-admin runtime dashboard
```

**No side effects:** The command is read-only. It MUST NOT write to the DB,
post to the Blackboard, or trigger any worker action.

---

## 5. Panel Detail

### Panel 1 — Convergence Direction

**Headline signal:** Are we healing or accumulating?

Shown:
- Findings created in last 24h
- Findings resolved in last 24h
- Net direction: `↓ healing` / `→ flat` / `↑ accumulating`
- Current open finding count (total)

Signal logic:
- Green: resolved > created (last 24h)
- Blue: resolved == created, or both zero (system idle — no movement, no problem)
- Red: created > resolved (last 24h)

---

### Panel 2 — Governor Inbox

**Headline signal:** Does CORE need the governor right now?

Shown:
- DELEGATE items on Blackboard (status = `indeterminate`, entry_type = `finding`)
- Proposals awaiting human approval (status = `draft`, approval_required = true)
- Total: "X items need your attention"

Signal logic:
- Green: 0 items
- Amber: 1–3 items
- Red: 4+ items, or any item older than 24h

---

### Panel 3 — Loop Running

**Headline signal:** Are all workers alive and cycling?

Shown:
- Total workers registered
- Active workers (status = `active`)
- Any worker with last_heartbeat > 10 min: named explicitly
- Oldest heartbeat age

Signal logic:
- Green: all active workers heartbeat < 10 min
- Amber: any active worker heartbeat 10–60 min
- Red: any active worker heartbeat > 60 min, or registered worker missing from recent heartbeats

---

### Panel 4 — Pipeline Moving

**Headline signal:** Are proposals flowing through to execution?

Shown:
- Proposals by status: DRAFT / APPROVED / EXECUTED / FAILED (counts)
- Most recent consequence log entry timestamp ("last action Xm ago")
- Any proposals stuck in APPROVED > 30 min (not yet executed)

Signal logic:
- Green: EXECUTED count > 0 today, no FAILED, last consequence < 60 min ago
- Amber: No execution activity today but no failures either
- Red: FAILED proposals exist, or APPROVED proposals stuck > 30 min

---

### Panel 5 — Governance Coverage

**Headline signal:** Is the governance layer intact?

Shown:
- Rules declared vs rules executed (last audit run)
- Coverage % (effective)
- Unmapped rules count
- Last audit timestamp

Signal logic:
- Green: 100% effective coverage, 0 unmapped
- Amber: Unmapped rules exist (governance debt visible)
- Red: Coverage below last known baseline, or last audit > 24h ago

---

## 6. Non-Requirements

The following are explicitly out of scope for this command:

- Individual finding details or file paths → use `core-admin code audit`
- Blackboard entry inspection → use `core-admin runtime blackboard`
- Full worker logs → use `core-admin runtime health`
- Proposal details → use existing proposal commands
- Real-time streaming / live TUI → `watch` composability is sufficient
- Web interface → future rendering concern, not an architecture concern now

---

## 7. Implementation Notes (for design phase)

- All five panels can be computed in a single DB session with five queries.
- Queries should use a fixed 24h window (UTC) for consistency.
- The command should gracefully degrade: if one panel's query fails,
  show that panel as `UNKNOWN` (grey) and continue rendering the others.
- Heartbeat thresholds (10 min amber, 60 min red) should be configurable
  in `.intent/` or at minimum as named constants — not hardcoded magic numbers.
- The 24h convergence window is a policy decision. It lives in `.intent/`, not in `src/`.

---

## 8. Success Signal

The dashboard is correct when a governor can:

1. Run `core-admin runtime dashboard`
2. Read the output in under 10 seconds
3. Know with confidence whether CORE needs their attention or not

If the governor still needs to run additional commands to answer that question,
the dashboard has failed its requirement.
