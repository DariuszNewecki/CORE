---
kind: adr
id: ADR-034
title: ADR-034 — OptimizerWorker Formal Deferral
status: accepted
---

<!-- path: .specs/decisions/ADR-034-optimizer-worker-formal-deferral.md -->

# ADR-034 — OptimizerWorker Formal Deferral

**Date:** 2026-05-10
**Governing paper:** `.specs/papers/CORE-OptimizerWorker.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Closes:** #246

---

## Context

`CORE-OptimizerWorker.md` declares OptimizerWorker as a constitutional
officer with a defined mandate: observe ViolationExecutor discovery
patterns, graduate high-confidence patterns into the RemediationMap, and
retire patterns that consistently fail. The paper's status is "Not Yet
Designed."

The 2026-04-28 constitutional coherence audit surfaced finding F-18:
OptimizerWorker is acknowledged unimplemented without a formal deferral
decision. The paper status line is not a constitutional decision — it is
an observation. F-18 asks for either implementation or a dated ADR that
locks the deferral as constitutional law and removes the ambiguity.

The `CORE-OptimizerWorker.md` §3 already states the correct rationale
for deferral: OptimizerWorker needs ViolationExecutor discovery data at
scale before pattern-graduation has substrate. VE is active but has not
yet accumulated enough discovery cycles to surface graduatable patterns.
Building the worker before the input data exists produces an instrument
with nothing to instrument.

---

## Decision

### D1 — OptimizerWorker is formally deferred

OptimizerWorker implementation is deferred until ViolationExecutor has
accumulated sufficient discovery data for pattern-graduation to be
meaningful. This is a constitutional decision, not a paper status line.
The deferral is in effect from this ADR's date.

### D2 — Review trigger

The deferral is reviewed when either condition is met:

1. ViolationExecutor has successfully discovered and surfaced **≥ 20
   distinct action candidates** across ≥ 5 different rule namespaces
   (evidenced by `core.blackboard_entries` with
   `subject LIKE 'discovery.candidate%'` and status = `resolved`).

2. **12 months** have elapsed since this ADR's date (2026-05-10) without
   condition 1 being met — at which point the governor reassesses whether
   the OptimizerWorker mandate remains architecturally sound.

At review, the outcome is either: commence design (opening a new issue
against #115) or extend the deferral with a dated addendum to this ADR.

### D3 — Active constitutional commitments removed

`CORE-OptimizerWorker.md` §3 is amended to reference this ADR as the
authoritative deferral record. The paper status transitions from
"Not Yet Designed" to "Formally Deferred (ADR-034)". No implementation
work, worker declaration, or RemediationMap entry is authorized until
the review trigger in D2 fires.

### D4 — #115 retained as the implementation epic

GitHub issue #115 ("OptimizerWorker — design and implement") remains
open as the forward-looking epic. When D2's review trigger fires and
implementation commences, #115 is the issue that carries it. This ADR
and #115 are the canonical forward reference pair.

---

## Consequences

**Immediate.** F-18 from the 2026-04-28 coherence audit is closed.
The constitutional ambiguity ("acknowledged unimplemented, no decision")
is resolved. A future auditor re-running the coherence check will find
a dated ADR, not an open finding.

**Forward.** The review trigger in D2 is the gate. When VE discovery
data accumulates, the governor is prompted to open design work against
#115. Until then, no OptimizerWorker work is warranted.

**`CORE-OptimizerWorker.md` amendment.** §3 status line updated to
reference this ADR. No other paper changes required.

---

## References

- `CORE-OptimizerWorker.md` §3 — deferral rationale (substrate argument)
- `.intent/CHANGELOG.md` — F-12 entry: paper §3 updated so deferral is
  grounded in absence of VE discovery data, not absence of VE
- GitHub #246 — coherence audit finding F-18 (closed by this ADR)
- GitHub #115 — implementation epic (retained, gated on D2 trigger)
- Constitutional coherence audit 2026-04-28, Pass 1
