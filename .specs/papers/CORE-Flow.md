<!-- path: .specs/papers/CORE-Flow.md -->

# CORE — Flow

**Status:** Constitutional Paper
**Authority:** Policy (derivative, non-amending)
**Scope:** All execution composition in CORE
**Depends on:**
- `.specs/papers/CORE-Action.md`
- `.specs/papers/CORE-Mind-Body-Will-Separation.md`
- `.specs/papers/CORE-Workers.md`

---

## 1. Purpose

This paper defines the **Flow** — the missing primitive between an
AtomicAction and a Worker.

Its purpose is to:

- Close the gap between single-purpose execution and autonomous agency.
- Prevent AtomicActions from accumulating composition logic they must
  not carry.
- Prevent Workers from hardwiring execution pipelines that belong in a
  declared, reusable layer.
- Make the three-level execution hierarchy explicit and enforceable.

---

## 2. The Three-Level Execution Hierarchy

CORE execution is structured in exactly three levels. No component may
exist outside them.

```
AtomicAction  — does exactly one thing
      ↓ composes into
Flow          — named, ordered sequence of AtomicActions or Flows
      ↓ invoked by
Worker        — constitutional officer that decides when and why
```

Each level has a single responsibility. Violations of this separation
are constitutional failures, not design preferences.

---

## 3. Definition

A **Flow** is a named, ordered, reusable composition of AtomicActions
or other Flows.

A Flow:
- Has a declared name and a declared sequence of steps.
- Steps are AtomicActions or other Flows — never inline logic.
- Returns a structured result describing the outcome of each step.
- Respects `write=False` — if any step is called with `write=False`,
  all steps in the Flow must operate in dry-run mode.
- Has no Blackboard presence. It posts no findings, no reports, no
  heartbeats.
- Has no mandate. It is not a constitutional officer.
- Has no autonomous trigger. It runs only when invoked by a Worker or
  by another Flow.
- Has no knowledge of why it is being run.

A Flow does not:
- Decide whether to run.
- Decide which steps to include at runtime.
- Communicate with other Flows or Workers directly.
- Call an LLM. LLM invocations belong inside an AtomicAction, declared
  and registered as such.
- Write to the Blackboard.
- Create Proposals.

---

## 4. What a Flow Is Not

**A Flow is not an AtomicAction.**
An AtomicAction does one thing. If the implementation chains multiple
operations, it is a Flow misclassified as an AtomicAction. The
`@atomic_action` decorator must not be applied to a function that
delegates to other registered actions.

**A Flow is not a Worker.**
A Worker is a constitutional officer with a declared mandate, a
permanent UUID, and Blackboard authority. A Flow has none of these. A
Worker that hardwires its own execution pipeline is carrying work that
belongs in a Flow.

**A Flow is not a Workflow.**
A Workflow is a multi-phase operational sequence declared in
`.intent/workflows/`. Workflows govern how CORE's autonomous loop
operates across phases. A Flow is a Body-layer composition primitive —
it lives in `src/body/flows/` and operates within a single phase.

---

## 5. Declaration

Every Flow is declared as a named Python class in `src/body/flows/`.

A Flow declaration carries:

| Field | Required | Description |
|---|---|---|
| `flow_id` | Yes | Unique dot-notation identifier. e.g. `flow.build_tests` |
| `description` | Yes | One sentence describing what this Flow does. |
| `steps` | Yes | Ordered list of `action_id` or `flow_id` references. |
| `policies` | Yes | List of policy IDs governing this Flow. |

A Flow that is not declared does not exist constitutionally. It cannot
be referenced by a Worker. It cannot appear in a Proposal.

---

## 6. Execution Contract

A Flow is invoked via `FlowExecutor`, the Body-layer dispatcher
analogous to `ActionExecutor` for AtomicActions.

- `FlowExecutor` resolves `flow_id` to its declared step sequence.
- Each step is dispatched in order via `ActionExecutor` (for
  AtomicActions) or recursively via `FlowExecutor` (for nested Flows).
- If any step returns `ok=False` and the step is declared `required`,
  the Flow halts and returns a `FlowResult` with `ok=False` and the
  failing step identified.
- If a step is declared `optional`, failure is recorded but execution
  continues.
- `write=False` is propagated to every step without exception.

Every Flow returns a `FlowResult`:

| Field | Type | Description |
|---|---|---|
| `flow_id` | string | The registered ID of this Flow. |
| `ok` | boolean | True if all required steps succeeded. |
| `steps` | list | Ordered list of `ActionResult` or `FlowResult` per step. |
| `duration_sec` | float | Total wall-clock duration of the Flow. |

---

## 7. Named Constitutional Violations

The following patterns are constitutional violations under this paper:

**Violation 1 — AtomicAction carrying composition logic.**
An AtomicAction that internally invokes other registered AtomicActions
via `ActionExecutor` is a Flow misclassified as an AtomicAction.

*Current named instance:* `build.tests` invokes `fix.imports`,
`fix.headers`, `fix.format`, `CoderAgent`, `IntentGuard`, and
`file.create` internally. It must be reclassified as
`flow.build_tests`. Its constituent operations become the AtomicActions
the Flow composes.

**Violation 2 — Worker hardwiring a step sequence.**
A Worker whose `run()` method contains an explicit ordered sequence of
`ActionExecutor.execute()` calls is carrying Flow logic. The sequence
must be extracted into a named Flow and the Worker must invoke the
Flow by `flow_id`.

**Violation 3 — Flow with Blackboard presence.**
A Flow that calls `post_finding()`, `post_report()`, or
`post_heartbeat()` is violating the Worker/Flow boundary. Blackboard
authority belongs to Workers, not Flows.

**Violation 4 — Flow with runtime step selection.**
A Flow that decides at runtime which steps to include — based on
findings, conditions, or LLM output — is not a Flow. It is Worker
logic or AtomicAction logic misplaced in the composition layer.

---

## 8. Relationship to the Remediation Path

The constitutional remediation path is:

```
Finding → RemediationMap → Proposal → Flow or AtomicAction → ActionExecutor
```

A Proposal may declare either an `action_id` or a `flow_id` as its
execution target. The distinction is transparent to the RemediationMap —
it routes to whichever primitive is registered for the rule.

`FlowExecutor` is the execution boundary. The Proposal does not know
whether it is invoking a single action or a pipeline.

---

## 9. Relationship to `DevSyncWorkflow`

`DevSyncWorkflow` is a multi-phase operational sequence, not a Flow in
the sense defined here. Its Fix phase and Sync phase are sequences of
AtomicAction invocations that should be extracted into declared Flows:

- `flow.fix_code` — `fix.headers → fix.ids → fix.duplicate_ids →
  fix.imports → fix.logging → fix.placeholders → fix.atomic_actions →
  fix.modularity → fix.format`
- `flow.sync_state` — `sync.db → sync.vectors.code →
  sync.constitutional.vectors`

`DevSyncWorkflow` becomes the orchestrator that invokes these Flows in
declared order — not the site where the sequences are hardwired.

---

## 10. Non-Goals

This paper does not define:

- The `FlowExecutor` implementation.
- The `FlowResult` schema beyond the fields declared in section 6.
- Retry or compensation logic within Flows — that belongs to the
  invoking Worker.
- Parallel step execution — all Flows are sequential unless a future
  paper declares otherwise.
- How Flows are discovered or indexed at runtime.

---

## 11. Closing Statement

The three-level hierarchy — AtomicAction, Flow, Worker — mirrors the
consensus of forty years of systems design: Unix pipes, Make, Airflow,
Kubernetes controllers, and BPMN all separate the atom, the pipeline,
and the scheduler.

CORE's contribution is to make each level a governed, declared,
constitutional primitive — not an ad-hoc implementation pattern.

An AtomicAction that knows it is part of a pipeline is not atomic.
A Worker that hardwires its pipeline is not an officer — it is a
script. A Flow that decides when to run is not a pipeline — it is an
agent without a mandate.

The separation is not bureaucracy. It is the condition under which
autonomous execution remains governable.

**End of Paper.**
