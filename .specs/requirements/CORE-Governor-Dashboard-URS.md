# CORE — Governor Dashboard
## User Requirements

**Status:** Active
**Authority:** Policy
**Scope:** `core-admin runtime dashboard` command
**Audience:** Governor (operator of CORE)
**Version:** 1.1
**Last updated:** 2026-04-16

---

## Change Log

| Version | Date | Change |
|---------|------|--------|
| 1.0 | 2026-04-15 | Initial draft — five panels including Governance Coverage (Panel 5) |
| 1.1 | 2026-04-16 | Panel 5 replaced: Governance Coverage → Autonomous Reach. Data sources updated. Threshold configuration demoted to known gap. |

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
| 1 | **Is the system converging?** | Findings resolving faster than created (last 24h) | Flat — no net movement, or system idle | — | Findings accumulating |
| 2 | **Does the governor have items waiting?** | 0 DELEGATE + 0 approval-required DRAFT | — | Any items waiting | Backlog growing or items aging |
| 3 | **Is the loop running?** | All active workers heartbeat < 10 min | — | Any worker 10–60 min stale | Worker missing or dead |
| 4 | **Is the pipeline moving?** | Proposals executing, consequences logged recently | — | Proposals stuck in APPROVED but not executing | Failed proposals, no consequence activity |
| 5 | **Can the daemon self-heal?** | Full autonomous reach — no blocked findings | — | Dry-run graduation candidates waiting | Abandoned findings — daemon cannot self-heal |

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
| Autonomous reach | `core.blackboard_entries` (status = `abandoned`) + `core.autonomous_proposals` (dry-run candidates) + `core.blackboard_entries` (ViolationExecutor in-flight claims) |

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
- Net direction: `converging` / `stable` / `diverging`
- Net delta (+/-)
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
- Total: "X items awaiting governor"

Signal logic:
- Green: 0 items
- Amber: 1–3 items, none older than 24h
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

### Panel 5 — Autonomous Reach

**Headline signal:** Can the daemon self-heal without governor intervention?

This panel answers whether the autonomous loop has a clear path forward — or whether
findings exist that no remediation path can handle. Abandoned findings are the primary
failure signal: they represent governance debt the daemon cannot resolve on its own.

Dry-run graduation candidates are a secondary signal: findings where a ViolationExecutor
path has been proven in dry-run mode and is waiting for promotion to live execution.
These require governor review, but represent forward progress — not blockage.

Shown:
- Abandoned findings (no remediation path — daemon cannot self-heal)
- Dry-run graduation candidates (ready to promote from dry-run to live)
- ViolationExecutor in-flight claims (currently being processed on discovery path)

Signal logic:
- Green: 0 abandoned findings, 0 dry-run candidates
- Amber: Dry-run candidates exist (graduation waiting), 0 abandoned
- Red: Abandoned findings exist (daemon cannot self-heal)

---

## 6. Non-Requirements

The following are explicitly out of scope for this command:

- Individual finding details or file paths → use `core-admin code audit`
- Blackboard entry inspection → use `core-admin workers blackboard`
- Full worker logs → use `core-admin runtime health`
- Proposal details → use existing proposal commands
- Real-time streaming / live TUI → `watch` composability is sufficient
- Web interface → future rendering concern, not an architecture concern now

---

## 7. Implementation Notes

- All five panels are computed in a single DB session with five queries.
- Queries use a fixed 24h window (UTC) for consistency.
- The command degrades gracefully: if one panel's query fails, that panel renders
  as `UNKNOWN` (grey) and the others continue unaffected.

**Known gap — threshold configuration:**
Heartbeat thresholds (10 min amber, 60 min red), the 24h convergence window, and the
30 min pipeline-stuck threshold are currently implemented as named constants in
`src/cli/resources/runtime/health.py`. The requirement that these live in `.intent/`
as configurable policy values is not yet met. This is tracked as a Phase 4 item.

**Known gap — audit_runs write gap:**
`core-admin code audit` does not persist results to the DB. The daemon's sensors
are the continuous audit source; manual audit output is separate. Panel 4's
"last consequence" metric reflects daemon-driven execution only. A manual audit
run does not update the dashboard.

---

## 8. Success Signal

The dashboard is correct when a governor can:

1. Run `core-admin runtime dashboard`
2. Read the output in under 10 seconds
3. Know with confidence whether CORE needs their attention or not

If the governor still needs to run additional commands to answer that question,
the dashboard has failed its requirement.
