<!-- path: .specs/papers/CORE-Finding.md -->

# CORE — The Finding

**Status:** Canonical
**Authority:** Constitution
**Scope:** All violation detection and sensing in CORE

---

## 1. Purpose

This paper defines the Finding — the unit of observation posted to the
Blackboard by a sensing Worker.

---

## 2. Definition

A Finding is a Blackboard entry of type `finding` that describes a
violation or condition requiring attention.

A Finding observes. It does not prescribe. It does not act.
The Worker that posts a Finding has no authority over what happens next.

---

## 3. Required Payload Fields

Every Finding payload must contain:

| Field | Type | Description |
|-------|------|-------------|
| `rule` | string | The rule ID that was violated. e.g. `style.import_order` |
| `file_path` | string | Repo-relative path to the file containing the violation. |
| `severity` | string | One of: `critical`, `error`, `warning`, `info` |
| `message` | string | Human-readable description of the violation. |
| `rule_namespace` | string | The namespace prefix of the rule. e.g. `style` |
| `status` | string | Initial value: `unprocessed` |
| `dry_run` | boolean | Whether this Finding was posted in dry-run mode. |
| `dry_run_scope` | string | When dry_run is true, one of: `evaluation_only`, `fix_generated`, `finding_suppressed`. Declares which aspect of processing was dry. See `.intent/META/enums.json`. Required when dry_run is true. |

Optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `line_number` | integer | Line where the violation occurs, if determinable. |
| `check_id` | string | The specific check that produced this Finding. |
| `context` | object | Additional structured evidence. |
| `proposal_id` | UUID | Set when status is `deferred_to_proposal`. The ID of the Proposal created for this Finding. Required for revival on proposal failure. |

---

## 4. Subject Format

The subject of an audit violation Finding follows this format:

```
audit.violation::{rule_id}::{file_path}
```

Example:

```
audit.violation::style.import_order::src/body/workers/violation_remediator.py
```

The subject is used for deduplication. A Finding with the same subject
as an existing non-terminal entry is not posted again.

---

## 5. Deduplication Contract

Before posting a Finding, the sensing Worker queries the Blackboard for
existing entries matching the same subject in any non-terminal status
(`open`, `claimed`).

If a match exists: the Finding is skipped. It is not an error.

Deduplication is scoped globally — not per Worker UUID. A Worker's
`worker_uuid` is permanent across daemon restarts — it does not change
between generations. Deduplication by subject is therefore sufficient
and UUID is irrelevant to the dedup check. See
`CORE-Workers-and-Governance-Model.md` §7a.

---

## 6. What Makes a Finding Actionable

Not every violation produces an actionable Finding. The following are
filtered before posting:

- **Sentinel file paths** — `System`, `DB`, `unknown`, `none`, empty string,
  or paths starting with `__symbol_pair__`. These cannot be opened as
  source files by an acting Worker.
- **Non-Python files** — Files that do not end in `.py` are excluded from
  the autonomous remediation loop.
- **Malformed rule IDs** — Rule IDs containing `/` are enforcement mapping
  file paths leaked from the auditor internals. They are not valid rule IDs.

A Finding that passes all three filters is actionable.

---

## 7. Terminal Transitions

A Finding moves from `claimed` to one of these terminal statuses. The
canonical status values are declared in `.intent/META/enums.json` under
`blackboard_entry_status`.

| Status | Meaning |
|--------|---------|
| `resolved` | The violation was fixed. The Finding is closed. |
| `abandoned` | Processing failed. The Finding is closed without fix. |
| `dry_run_complete` | Dry-run completed. A proposed fix exists on the Blackboard but nothing was written. |
| `deferred_to_proposal` | The rule has an active RemediationMap entry. A Proposal has been created. The `proposal_id` field in the payload MUST be set to the created Proposal's ID. |
| `indeterminate` | The acting Worker could not safely proceed. Human review required. |

---

## 7a. Revival on Proposal Failure

`deferred_to_proposal` is terminal at the Finding level, but the downstream
Proposal may fail. This must not result in silent governance debt.

When a Proposal reaches `failed` status, the ProposalConsumerWorker MUST:

1. Query all Findings whose payload `proposal_id` matches the failed Proposal's ID.
2. For each such Finding, set `status = 'open'`, `claimed_by = NULL`, `claimed_at = NULL`.
3. Post a `report` entry recording the revival: the Proposal ID, the count of
   revived Findings, and the failure reason.

Revived Findings re-enter the remediation loop as if freshly posted. The
deduplication contract applies — if the same violation still exists, the
sensor will not re-post it; the revived Finding is sufficient.

---

## 7b. Indeterminate Exit

An `indeterminate` Finding requires explicit human action to exit. No
automated Worker may transition it. The architect reviews the Finding and
either sets status to `open` (re-enter the loop) or `abandoned` (close
permanently). The decision must be recorded in the Finding's `context`
payload field.

---

## 8. Non-Goals

This paper does not define:
- the audit engine that produces violations
- the specific rules that generate Findings
- the acting Worker's remediation strategy
