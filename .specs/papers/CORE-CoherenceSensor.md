<!-- path: .specs/papers/CORE-CoherenceSensor.md -->

# CORE — Coherence Sensor

**Status:** Canonical
**Authority:** Policy
**Scope:** Sensor-fixer incoherence detection in the autonomous remediation loop

---

## 1. Purpose

This paper defines the `CoherenceSensorWorker` — the sensing Worker responsible
for detecting when the autonomous loop produces a proposal that executes
successfully but the underlying violation persists.

---

## 2. Problem Statement

The autonomous remediation loop records findings resolved and execution outcome
in `core.proposal_consequences`. A successful execution does not guarantee the
violation is actually gone. If the originating audit sensor re-detects the same
`check_id` and `file_path` after the consequence is recorded, the loop is
producing churn: proposals execute, the violation metric ticks, and the codebase
does not change. This failure mode is silent without a dedicated sensor watching
the consequence chain.

---

## 3. Definition

`CoherenceSensorWorker` is a sensing Worker. It queries the consequence chain,
identifies proposal/finding pairs where a re-detection occurred after execution,
and posts a deduplicated incoherence finding per occurrence. It makes no
decisions. It writes no files. It calls no LLM.

---

## 4. Constitutional Identity

| Field | Value |
|---|---|
| Declaration | `.intent/workers/coherence_sensor.yaml` |
| Class | `sensing` |
| Phase | `audit` |
| Permitted tools | none |
| Approval required | false |
| Schedule | max_interval 600 s (10 min) |
| ADR | ADR-027 |

---

## 5. Detection Logic

One detection cycle:

**Step 1 — Load lookback threshold**
Reads `coherence_lookback_seconds` from `.intent/cim/thresholds.yaml`. Falls
back to 7200 s on any load or coercion failure so a malformed threshold file
does not disable the cycle.

**Step 2 — Query existing incoherence findings**
Fetches all open Blackboard subjects matching the `coherence.incoherence::%`
prefix. Used for deduplication in Step 4.

**Step 3 — Query consequence chain**
Joins `core.proposal_consequences` against `core.blackboard_entries` to find
rows where:
- A consequence was recorded with at least one entry in `findings_resolved`.
- A new, non-terminal finding for the same `check_id` and `file_path` exists
  in `core.blackboard_entries` with `created_at` after the consequence's
  `recorded_at`.
- The new finding is not the same row as the resolved finding.
- The consequence was recorded within the lookback window.

**Step 4 — Post deduplicated findings**
For each row from Step 3, computes a subject:
`coherence.incoherence::{check_id}::{file_hash}`
where `file_hash` is an 8-character MD5 prefix of the `file_path`. Skips
subjects already present in the open set from Step 2. Posts one Blackboard
Finding per new incoherent occurrence.

**Step 5 — Post completion report**
Posts `coherence_sensor.run.complete` with `checked` and `incoherent` counts.

---

## 6. Blackboard Contract

| Subject prefix | Entry type | Producer |
|---|---|---|
| `coherence.incoherence::{check_id}::{file_hash}` | finding | `CoherenceSensorWorker` |
| `coherence_sensor.run.complete` | report | `CoherenceSensorWorker` |

No other worker produces `coherence.incoherence::` findings. Any such entry
from another source is a violation of this paper.

---

## 7. Finding Payload

```
check_id:              {rule check_id from the original finding}
file_path:             {file path of the re-detected violation}
proposal_id:           {UUID of the proposal whose execution did not resolve it}
re_posted_finding_id:  {UUID of the new finding that re-appeared}
detected_at:           {ISO 8601 timestamp}
```

---

## 8. Remediation Posture

`CoherenceSensorWorker` is a DELEGATE-class finding producer. Incoherence
findings require human review — the root cause may be a flawed fixer, a
rule false-positive, or a constitutional gap. Autonomous remediation of
incoherence findings is not permitted. Per ADR-027 D1, this worker detects
only; it does not modify proposals, findings, or source files.

---

## 9. Non-Goals

This paper does not define:
- the remediation strategy for incoherent proposal/finding pairs
- how the root cause of incoherence is diagnosed
- thresholds at which incoherence volume triggers escalation

---

## 10. Amendment Discipline

This paper may be amended only by explicit constitutional replacement, in
accordance with the CORE amendment mechanism.
