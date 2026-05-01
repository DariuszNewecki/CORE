<!-- path: .specs/papers/CORE-ViolationSensor.md -->

# CORE — ViolationSensor

**Status:** Canonical
**Authority:** Policy
**Scope:** Audit violation detection

---

## 1. Purpose

This paper defines the ViolationSensor — the sensing Worker that runs
the constitutional auditor and posts violations as Findings.

---

## 2. Definition

The ViolationSensor is a sensing Worker. It runs the constitutional audit
scoped to a declared rule namespace and posts each unresolved violation
as a Finding to the Blackboard.

It makes no decisions. It writes no files. It calls no LLM.
It observes and reports.

---

## 3. Declaration Model

One class backs multiple declarations. Each declaration in
`.intent/workers/audit_sensor_{namespace}.yaml` declares a
`rule_namespace` prefix (e.g. `style`, `architecture`, `modularity`).

The daemon starts one ViolationSensor instance per namespace declaration.
Each instance scopes its audit to rules matching its declared namespace.

---

## 4. Technical Flow

start → register → run → heartbeat → resolve rule IDs
→ run audit → collect violations → filter → deduplicate
→ post findings → post report → end

**Step 1 — Resolve rule IDs**
The sensor queries the IntentRepository for all rule IDs matching its
declared `rule_namespace` prefix. Rule IDs are resolved dynamically —
adding a new rule to an existing namespace automatically brings it
into scope without restarting the daemon.

**Step 2 — Run audit**
The constitutional auditor runs scoped to the resolved rule IDs.
Output is a list of raw violations, each with: `rule_id`, `file_path`,
`line_number`, `message`, `severity`.

**Step 3 — Filter**
Violations are filtered to remove:
- Sentinel file paths (`System`, `DB`, `unknown`, `none`, empty)
- Symbol-pair paths (`__symbol_pair__*`)
- Non-Python files (paths not ending in `.py`)
- Malformed rule IDs (containing `/`)

**Step 4 — Deduplicate**
For each remaining violation, the subject is computed:
`audit.violation::{rule_id}::{file_path}`

The Blackboard is queried for existing entries with the same subject
in non-terminal status (`open`, `claimed`). Matches are skipped.

Deduplication is global — not scoped to this Worker's UUID. This
prevents re-posting after daemon restart.

**Step 5 — Post findings**
Each non-duplicate violation is posted as a Blackboard finding with
`entry_type=finding`, `status=open`.

**Step 6 — Post report**
A completion report is posted summarizing: violations found, posted,
skipped (duplicates), filtered (unactionable).

---

## 5. Output

For each actionable, non-duplicate violation, one Blackboard entry:

entry_type: finding
status:     open
subject:    audit.violation::{rule_id}::{file_path}
payload:
rule:           {rule_id}
rule_namespace: {namespace}
file_path:      {file_path}
line_number:    {line_number or null}
message:        {violation message}
severity:       {critical|error|warning|info}
dry_run:        {bool}
status:         unprocessed

---

## 6. Non-Goals

This paper does not define:
- the audit engine implementation
- how rules are evaluated against code
- what happens after a Finding is posted
