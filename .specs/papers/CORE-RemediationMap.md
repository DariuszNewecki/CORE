<!-- path: .specs/papers/CORE-RemediationMap.md -->

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

## 4. Write Authority

The RemediationMap is a `.intent/` artifact. `.intent/` is read-only to
CORE — no autonomous process may write, modify, or delete any file under
`.intent/`, including the RemediationMap. This rule has no exceptions and
no future autonomous override path.

The human architect is the sole authority for adding, modifying, or
retiring RemediationMap entries.

CORE may surface optimization suggestions — for example, ViolationExecutor
may identify a pattern that warrants a new mapping — but the suggestion is
advisory only. The human reviews it and edits the file directly. CORE never
writes the result back.

---

## 5. Dispatch Rules

The RemediatorWorker applies these rules when reading the map:

**Only ACTIVE entries are dispatched.** PENDING entries are documented
for roadmap visibility only. They never produce Proposals.

**Minimum confidence is 0.80.** Entries with confidence below 0.80 are
not dispatched, regardless of status. This threshold is a constitutional
Rule declared in `.intent/rules/will/autonomy.json` under rule ID
`autonomy.remediation.min_confidence_floor`. It is blocking at runtime.
Changing the threshold requires a rule amendment — it is not an
operational configuration value.

**One action per rule.** Each rule maps to exactly one AtomicAction.
A rule with multiple competing actions has not been specified precisely
enough.

---

## 6. Confidence Tiers

These tiers describe dispatch behaviour by confidence band. All tiers
are deterministic — the labels reflect dispatch status, not quality
of the underlying handler.

| Confidence | Dispatch status | Meaning |
|------------|-----------------|---------|
| >= 0.90 | Auto-dispatched | Fully validated mapping. No reasoning required. |
| >= 0.80 | Auto-dispatched | Validated mapping with light risk. |
| >= 0.50 | Not dispatched | Handler exists but confidence is below the minimum floor. |
| < 0.50 | Not dispatched | Handler stub only. Not ready for autonomous dispatch. |

Entries in the 0.50–0.79 band are documented for roadmap visibility.
They will be dispatched once confidence is raised to 0.80 or above
through additional validation.

---

## 7. How It Is Read

The RemediatorWorker loads the map via `_load_remediation_map()` which
reads the file at the path declared in `governance_paths.yaml`. The path
is not hardcoded in code.

The map is loaded fresh on each Worker run. Changes to the map take
effect on the next daemon cycle without restart.

---

## 8. Relationship to AtomicAction `remediates` Field

The RemediationMap is the authoritative routing declaration.
The `remediates` field on a registered AtomicAction is the implementation
declaration. They must be consistent:

- If a rule appears in the RemediationMap, the declared action must have
  that rule in its `remediates` field.
- If an action declares `remediates: ["rule.id"]`, that rule should appear
  in the RemediationMap.

Inconsistency between the two is a governance gap.

---

## 9. Non-Goals

This paper does not define:
- the format of the YAML file beyond the fields above
- how AtomicActions are implemented
- the Proposal creation process
