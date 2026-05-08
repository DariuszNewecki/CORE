# ADR-030 — Daemon stale-code detection posture

**Status:** Accepted
**Date:** 2026-05-08
**Authors:** Darek (Dariusz Newecki)

---

## Context

The CORE daemon does not reload Python modules on file change. Any
change to `src/` — including action registrations, enforcement logic,
governance rules — is silently non-effective until the daemon is
manually restarted. There is no signal, no warning, no audit trail.

This was demonstrated on 2026-04-22 (35-minute stale-classification
window, tracked on #123). The issue was parked as a governor decision.

Three options were evaluated:

**Option A — Document and enforce manual restart.** Surface a dashboard
warning if the running daemon predates the most recent `src/` commit.
No auto-action. Rejected: a human-loop solution is incompatible with
autonomous operation at A3. Convergence stalls indefinitely without
governor awareness.

**Option B — File watcher + graceful self-restart.** Detect `src/`
changes and trigger a controlled daemon restart autonomously. Rejected
for two reasons: (1) a commit that breaks the daemon startup path
(syntax error, failed import, `ConstitutionalError` at init) produces
a restart loop — the daemon dies, restarts, dies again, eventually
falls silent with no Blackboard signal because the daemon that would
post the finding isn't running; (2) a `src/` change may alter
enforcement logic or governance rules — autonomously restarting into
changed governance without governor awareness violates the trust
boundary CORE is explicitly designed to hold. A code deployment is a
governor event, not an autonomous event.

**Option C — Detect and DEGRADE.** On drift detection, the daemon
DEGRADEs, posts a high-priority finding to the Blackboard, surfaces
the condition on the runtime dashboard, and suspends autonomous
execution until the governor restarts it. The governor sees what
changed, decides to restart with intent. One deliberate human action
closes the loop.

## Decision

**Option C — detect and DEGRADE.**

The daemon detects `src/` drift (on-disk commit SHA vs loaded-module
SHA or equivalent), DEGRADEs immediately, and posts a
`governance.stale_daemon` finding to the Blackboard. Autonomous
execution is suspended. The runtime dashboard surfaces the condition
prominently. The governor restarts when ready.

A time-bound escalation applies: if the DEGRADE finding is not
acknowledged within a configurable window (default 30 minutes), it
re-posts at elevated priority. This closes the "governor didn't notice"
failure mode without removing governor intent from the restart decision.

**What CORE does not do:** restart itself after a `src/` change. A
code deployment is a governor-controlled event. The system surfaces
the condition; the governor acts.

## Consequences

**Positive:**
- Startup-path failures (broken imports, failed registration,
  `ConstitutionalError` at init) cannot produce restart loops.
- Governance changes in `src/` are never silently self-applied. The
  governor knows a restart is pending and can review what changed.
- The trust boundary between autonomous operation and governor-
  controlled deployment is explicit and held constitutionally.
- The Blackboard always has a signal — DEGRADE posts before stopping,
  unlike a crash loop which goes silent.

**Negative:**
- Convergence pauses during the DEGRADE window. Findings accumulate
  but are not processed until the governor restarts. For short windows
  this is acceptable; for extended outages it is a G2 risk.
- Implementation requires a drift-detection mechanism (commit SHA
  comparison or module-hash comparison) that does not yet exist.

**Neutral:**
- Manual restart remains the governor's action. The difference from
  Option A is that CORE actively surfaces the need rather than
  silently running stale.

## References

- Issue #123 — Cold-registry detection — daemon reload semantics
- A3 Gate G2 — convergence measurement
- `core-admin runtime health` — primary surface for DEGRADE condition
