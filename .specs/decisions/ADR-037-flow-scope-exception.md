<!-- path: .specs/decisions/ADR-037-flow-scope-exception.md -->

# ADR-037 — Flow refs exempt from ADR-035 per-file scoping

**Date:** 2026-05-11
**Status:** Proposed
**Author:** Darek (Dariusz Newecki)
**Relates:** ADR-035 (one finding, one proposal), ADR-033 (parameter routing), ADR-015 (consequence chain)

---

## Context

ADR-035 established that `ViolationRemediatorWorker` creates one proposal
per `(action_id, file_path)` unit. Each proposal's `scope.files` contains
exactly one file. The rationale (ADR-035 §"Why batching violates the
governance model") rests on three properties: approval granularity at
finding resolution, consequence chain integrity, and UNIX composition.

These properties hold for **atomic actions**, which operate on a single
file: `fix.format` on `src/foo.py`, `fix.modularity` on `src/bar.py`. The
governor's approval decision is bounded to one file; consequence
attribution is unambiguous; the proposal is one input → one transformation
→ one verifiable output.

They do **not** hold for **flows**. A flow like `flow.fix_code` is by
design a codebase-wide operation that runs many fixers across all of
`src/`. The per-file scope is a category mismatch:

- **Approval granularity:** The governor can approve "run flow.fix_code"
  but cannot meaningfully approve "run flow.fix_code scoped to `src/foo.py`"
  — the flow ignores per-file scope, walks the whole codebase, and may
  modify hundreds of unrelated files. The proposal's `scope.files: [foo.py]`
  is a lie.

- **Consequence chain integrity:** ADR-015 D4 requires
  Finding → Proposal → Execution → File change as a 1:1:1:1 path. A flow
  proposal scoped to one file but modifying many breaks this contract on
  the execution → file step. Attribution becomes ambiguous: "which finding
  caused this file's change?"

- **UNIX composition:** A flow is itself a multi-step pipeline — it's
  already a script, not a primitive. Treating one flow invocation as the
  unit of work is more correct than fragmenting it across many proposals
  that each invoke the same whole-codebase flow.

The 2026-05-11 implementation of ADR-035 didn't account for this. Under
the current code, N findings mapping to one flow ref produce N separate
proposals, each carrying a different (meaningless) `file_path` and each,
if approved and executed, running the same flow over the same codebase
N times. ADR-033's parameter-routing filter silently drops the spurious
`file_path`; commit `2a77a9ba` (Layer 1) stops persisting it. But the
N-proposals-per-flow grouping remains.

---

## Why batching is correct for flows

The properties that make batching wrong for atomic actions are the same
properties that make per-file scoping wrong for flows. ADR-035 inverted
the right decision for the wrong unit of work.

For a flow ref, the **flow itself** is the atomic unit of governance
concern — not any individual file the flow touches. The governor's
approval is "should this flow run, given these N findings exist?" — a
single decision over a single operation. Bundling all findings sharing
a flow ref into one proposal preserves the property ADR-035 was
protecting: the approval decision is scoped to one unit of work.

The consequence chain stays 1:1:1:1 with the unit redefined:
**Finding(s) → Flow Proposal → Flow Execution → All files the flow
changed**. The N findings are recorded in `constitutional_constraints
.finding_ids` (already implemented by ADR-035 §References). On revival
(§7a) the entire bundle revives together — correct, because the flow
either ran or didn't.

UNIX composition is preserved because flows are scripts by definition;
fragmenting them across N proposals doesn't increase compositionality,
it just duplicates the script.

---

## Decision

### D1 — Flow refs are grouped by `(ref_id, None)` in `ViolationRemediatorWorker.run()`

The grouping key for flow refs is `(ref_id, None)` — file_path is
collapsed to None. All findings sharing the same `flow_id` bundle into
one proposal. Atomic action refs remain grouped by `(action_id, file_path)`
per ADR-035 D1.

### D2 — Dedup contract follows the same key

`_get_active_proposal_id_by_action_file` returns one entry per
`(ref_id, file_path)` key. For flow proposals, that key is
`(flow_id, None)`. A second finding sharing the flow ref dedup-subsumes
under the same active proposal (per ADR-035 D2).

### D3 — Scope.files for flow proposals carries the affected file list

The proposal's `scope.files` lists every file from every bundled finding.
This is informational — the flow ignores it at execution time — but it
keeps the proposal queryable: "which files contributed findings to this
flow proposal?" remains answerable.

### D4 — `ProposalAction.parameters` for flow proposals carries no file_path

Already established by commit `2a77a9ba` (Layer 1 of the layered fix).
This ADR codifies the contract: flow proposals have
`parameters = {"write": True}` only. No `file_path`.

### D5 — Consequence chain attribution: all bundled findings resolve together

When the flow executes successfully, every finding in the bundle resolves.
When it fails, every finding in the bundle revives (§7a). The chain
stays 1:N at the Finding side and 1:1 at every other step.

---

## Implementation

`src/will/workers/violation_remediator.py`, `run()` method, grouping
loop (currently lines ~221-234):

```python
elif entry:
    ref_id = entry["ref_id"]
    ref_kind = entry["ref_kind"]
    if ref_kind == "flow":
        # ADR-037: flows are codebase-wide; group by ref_id alone
        key = (ref_id, None)
    else:
        # ADR-035: actions are per-file
        file_path = finding["payload"].get("file_path") or None
        key = (ref_id, file_path)
    action_groups.setdefault(key, []).append(finding)
    ref_kinds[ref_id] = ref_kind
```

No other changes required. `_create_proposal` already builds correct
parameters for both kinds (Layer 1). The dedup helper already keys by
`(ref_id, file_path)` so `(flow_id, None)` works naturally.

---

## Consequences

- **Throughput:** N findings sharing a flow ref produce 1 proposal
  instead of N. Reduces proposal volume and execution redundancy
  proportional to finding clustering.

- **Approval cost:** Governor approves one flow-proposal decision
  covering N findings rather than N decisions. This matches the
  reality of what's being approved (one codebase-wide operation).

- **Consequence chain:** Stays whole at the redefined unit. Per-finding
  resolution via `finding_ids` array preserved.

- **Compatibility with ADR-035:** This is not a refinement — it is a
  **categorical exception**. Atomic-action proposals remain
  per-(action, file). Flow proposals are per-ref. The remediator's
  grouping logic carries one explicit conditional on `ref_kind`.

- **Compatibility with ADR-033:** Independent. ADR-033's parameter
  filter operates at flow-step boundary; this ADR operates at proposal
  creation boundary. Both fix related-but-distinct issues in the same
  pipeline.

- **Open question (separate)** — whether flows should be invoked from
  the auto-remediation pipeline at all is governance-debt issue **#290**.
  This ADR makes flow auto-remediation behave correctly if the answer
  to #290 is "yes" or "selectively". If the answer is "no," this ADR
  becomes moot for `auto_remediation.yaml` flow entries but still
  governs any future per-flow proposal flow.

---

## References

- ADR-035 — establishes per-file scoping for atomic actions
- ADR-033 — flow→step parameter routing filter (closed #216)
- ADR-015 — consequence chain attribution (D4)
- Commit `2a77a9ba` — Layer 1 of the layered fix: file_path omitted from flow parameters
- Issue **#290** — Layer 3: governance question on flow auto-remediation
- Incident proposals: 45f23373-…, 3b16c329-… (2026-05-09)
