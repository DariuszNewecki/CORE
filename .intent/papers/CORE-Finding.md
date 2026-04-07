<!-- path: .intent/papers/CORE-Finding.md -->

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

Optional fields:

| Field | Type | Description |
|-------|------|-------------|
| `line_number` | integer | Line where the violation occurs, if determinable. |
| `check_id` | string | The specific check that produced this Finding. |
| `context` | object | Additional structured evidence. |

---

## 4. Subject Format

The subject of an audit violation Finding follows this format:

audit.violation::{rule_id}::{file_path}

Example:

audit.violation::style.import_order::src/body/workers/violation_remediator.py

The subject is used for deduplication. A Finding with the same subject
as an existing non-terminal entry is not posted again.

---

## 5. Deduplication Contract

Before posting a Finding, the sensing Worker queries the Blackboard for
existing entries matching the same subject in any non-terminal status
(`open`, `claimed`).

If a match exists: the Finding is skipped. It is not an error.

Deduplication is scoped globally — not per Worker UUID. This prevents
different daemon generations from re-posting the same violation when
the sensor restarts with a new UUID.

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

A Finding moves from `claimed` to one of these terminal statuses:

| Status | Meaning |
|--------|---------|
| `resolved` | The violation was fixed. The Finding is closed. |
| `abandoned` | Processing failed. The Finding is closed without fix. |
| `dry_run_complete` | Dry-run completed. A proposed fix exists on the Blackboard but nothing was written. |
| `deferred_to_proposal` | The rule has an active RemediationMap entry. A Proposal has been created. |
| `indeterminate` | The acting Worker could not safely proceed. Human review required. |

---

## 8. Non-Goals

This paper does not define:
- the audit engine that produces violations
- the specific rules that generate Findings
- the acting Worker's remediation strategy
