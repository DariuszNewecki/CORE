<!-- path: .intent/papers/CORE-RemediationMap.md -->

# CORE — The RemediationMap

**Status:** Canonical
**Authority:** Policy
**Scope:** Autonomous remediation routing

---

## 1. Purpose

This paper defines the RemediationMap — the declared routing table from
Rule to AtomicAction — and how it is read and applied at runtime.

---

## 2. Definition

The RemediationMap is a YAML file at:
`.intent/enforcement/remediation/auto_remediation.yaml`

It declares, for each remediable rule, which AtomicAction handles it,
at what confidence, and at what risk level.

It is read at runtime by the RemediatorWorker to determine whether a
Finding can be autonomously remediated and which action to dispatch.

---

## 3. Entry Structure

Each entry in the map declares:

| Field | Required | Description |
|-------|----------|-------------|
| `action` | Yes | The registered AtomicAction ID. e.g. `fix.imports` |
| `confidence` | Yes | Float 0.0–1.0. How reliable this mapping is. |
| `risk` | Yes | One of: `low`, `medium`, `high` |
| `description` | Yes | Human-readable explanation of the mapping. |
| `status` | Yes | One of: `ACTIVE`, `PENDING` |

---

## 4. Dispatch Rules

The RemediatorWorker applies these rules when reading the map:

**Only ACTIVE entries are dispatched.** PENDING entries are documented
for roadmap visibility only. They never produce Proposals.

**Minimum confidence is 0.80.** Entries with confidence below 0.80 are
not dispatched, regardless of status. This threshold is declared in
`.intent/enforcement/config/governance_paths.yaml` under
`remediation.min_confidence`. It is not hardcoded.

**One action per rule.** Each rule maps to exactly one AtomicAction.
A rule with multiple competing actions has not been specified precisely
enough.

---

## 5. Confidence Tiers

| Confidence | Tier | Meaning |
|------------|------|---------|
| >= 0.90 | safe_only | Fully deterministic. No reasoning required. Auto-dispatched. |
| >= 0.80 | medium_risk | Deterministic with light validation. Auto-dispatched. |
| >= 0.50 | all_deterministic | Handler confirmed working but confidence limited. NOT dispatched (below min). |
| < 0.50 | not dispatched | Handler stub only. NOT dispatched. |

---

## 6. How It Is Read

The RemediatorWorker loads the map via `_load_remediation_map()` which
reads the file at the path declared in `governance_paths.yaml`. The path
is not hardcoded in code.

The map is loaded fresh on each Worker run. Changes to the map take
effect on the next daemon cycle without restart.

---

## 7. Relationship to AtomicAction `remediates` Field

The RemediationMap is the authoritative routing declaration.
The `remediates` field on a registered AtomicAction is the implementation
declaration. They must be consistent:

- If a rule appears in the RemediationMap, the declared action must have
  that rule in its `remediates` field.
- If an action declares `remediates: ["rule.id"]`, that rule should appear
  in the RemediationMap.

Inconsistency between the two is a governance gap.

---

## 8. Non-Goals

This paper does not define:
- the format of the YAML file beyond the fields above
- how AtomicActions are implemented
- the Proposal creation process
