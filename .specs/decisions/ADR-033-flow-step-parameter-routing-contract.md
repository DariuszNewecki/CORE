---
kind: adr
id: ADR-033
title: ADR-033 — Flow→Step Parameter Routing Contract
status: accepted
---

<!-- path: .specs/decisions/ADR-033-flow-step-parameter-routing-contract.md -->

# ADR-033 — Flow→Step Parameter Routing Contract

**Date:** 2026-05-10
**Governing paper:** `.specs/papers/CORE-Flow.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Closes:** #216

---

## Context

`FlowExecutor._execute_step` currently merges caller params into every
step unconditionally:

```python
merged_params = {**step.params, **caller_params}
```

Every caller parameter is forwarded to every step. `ActionExecutor._prepare_params`
injects `core_context` conditionally by signature inspection, but does not
filter any other caller param — they pass through verbatim.

This is a de facto contract that is stated nowhere. Its consequences:

- **Strict-signature steps TypeError.** 6 of 21 registered atomic actions
  have no `**kwargs`: `fix.imports`, `check.imports`, `claim.proposal`,
  `sync.db`, `sync.vectors.code`, `sync.vectors.constitution`. When
  FlowExecutor forwards an unrelated caller param to any of these, execution
  halts with a TypeError.

- **`**kwargs` steps silently absorb garbage.** The remaining 15 actions
  accept `**kwargs` and swallow every unrecognised param without complaint.
  The routing passes, but the param never does anything. The silent-swallow
  case is worse than the TypeError case — it produces no signal that routing
  is wrong.

- **Pass/fail is a coding-style coincidence.** Whether a Flow with
  heterogeneous step signatures succeeds or fails depends on which steps
  happen to be strict vs flexible, not on any declared contract.

`flow.build_tests` is the first Flow where this becomes operational rather
than theoretical. A caller invoking `flow.build_tests(source_file="src/foo.py")`
succeeds at step 1 (`build.tests` accepts `**kwargs`), TypeErrors at step 2
(`fix.imports` is strict), and steps 3–4 silently absorb the param.

`#215` cannot land safely — wiring `flow_id` support into RemediationMap will
trigger the first autonomous flow invocation — until this contract is decided.
This ADR is that decision.

---

## Decision

### D1 — `consumes` field on `FlowStep`

Add `consumes: tuple[str, ...] | None` to the `FlowStep` dataclass (frozen).

Semantics:

| YAML value | `consumes` in Python | Behaviour |
|---|---|---|
| Field absent | `None` | No caller params forwarded to this step |
| `consumes: []` | `()` | No caller params forwarded (explicit) |
| `consumes: [source_file]` | `("source_file",)` | Only `source_file` forwarded |

**Default is isolation (`None` → no forwarding).** Explicit declaration is
required for every step that needs a caller param. This is consistent with
CORE's "no implicit law" principle — routing behaviour must be readable from
the flow YAML without inspecting Python action signatures.

A step that needs multiple caller params declares all of them:
`consumes: [source_file, target_dir]`.

### D2 — Filter in `FlowExecutor._execute_step`

Replace the unconditional merge:

```python
# Before
merged_params = {**step.params, **caller_params}
```

With a filtered merge:

```python
# After
if step.consumes is None:
    filtered_caller = {}
else:
    filtered_caller = {k: v for k, v in caller_params.items() if k in step.consumes}
merged_params = {**step.params, **filtered_caller}
```

Static `step.params` always pass through. Caller params pass through only
for declared keys. Undeclared caller params are silently dropped at the
FlowExecutor boundary — they never reach `ActionExecutor`.

### D3 — YAML schema extension for `.intent/flows/*.yaml`

The `consumes` key is optional per step. Absent means no caller params
forwarded. Example:

```yaml
steps:
  - ref_id: build.tests
    kind: action
    required: true
    consumes: [source_file]        # receives caller source_file
    params: {}

  - ref_id: fix.imports
    kind: action
    required: false
    consumes: [source_file]        # receives caller source_file
    params: {}

  - ref_id: fix.headers
    kind: action
    required: false
    consumes: [source_file]        # receives caller source_file
    params: {}

  - ref_id: fix.format
    kind: action
    required: false
    consumes: [source_file]        # receives caller source_file
    params: {}
```

A step with no `consumes` key (or `consumes: []`) runs with only its static
`params`.

### D4 — Loader change in `FlowRegistry._load_file`

Extend the per-step parse block to read `consumes`:

```python
raw_consumes = raw.get("consumes")
consumes = tuple(raw_consumes) if raw_consumes is not None else None

steps.append(
    FlowStep(
        ref_id=ref_id,
        kind=kind,
        required=required,
        params=params,
        consumes=consumes,
    )
)
```

`raw.get("consumes")` returns `None` when the key is absent (default isolation)
and `[]` when explicitly set to empty (same effect, explicit). Both map to
no-forwarding behaviour — the distinction is for YAML authoring clarity only.

### D5 — `core_context` injection is not affected

`ActionExecutor._prepare_params` injects `core_context` by signature
inspection. This is a system injection, not a caller param, and is not
governed by this contract. It remains unchanged.

### D6 — Nested Flow steps

When a step is `kind: flow`, `FlowExecutor._execute_flow_step` calls
`self.execute(step.ref_id, write=write, **params)`. The `params` passed
in are already the filtered `merged_params` from D2 — the outer-level
`consumes` filter controls what the nested flow's executor receives as
caller params. The nested flow then applies its own per-step `consumes`
filters. Filtering cascades correctly without any additional mechanism.

---

## Alternatives Considered

**Signature-based filtering.** FlowExecutor inspects each action's Python
signature and forwards only matching kwargs. Rejected: the routing behaviour
is only discoverable by reading `src/` Python code. It does not satisfy the
requirement that a non-programmer governor can read the flow YAML and know
exactly what routes where. It also fails for `**kwargs` actions — they match
all params, which is the current bug.

**First-step-only.** Caller params route only to the first step; subsequent
steps run on static `step.params` + `write` only. Rejected: `flow.build_tests`
requires `source_file` in steps 2–4, not just step 1. This contract works
only for flows where the caller's context is needed by exactly one step.

**Zero caller params.** Flow runtime is parameterless; all state lives in
static `step.params`; Workers build a per-invocation FlowDefinition before
calling. Rejected: requires Workers to construct FlowDefinitions at runtime,
which breaks the registry pattern and moves flow logic back into Worker code —
the violation this paper was written to prevent.

---

## Consequences

**Immediate.** `FlowStep` gains a `consumes` field. `FlowRegistry._load_file`
parses it. `FlowExecutor._execute_step` filters on it. `CORE-Flow.md §6`
gains a parameter routing section. These are the only required changes.

**flow.build_tests YAML.** The first flow YAML authored under this contract
must declare `consumes` per step. The example in D3 is the correct template.
This is the deliverable for the #215 follow-up.

**Existing flows.** There are no flows in `.intent/flows/` today without
`consumes` declarations. When new flows are authored, the absent-means-no-
forwarding default ensures that a flow with no `consumes` declarations is
safe by default — it receives no caller params, which may surprise authors
who expect the old broadcast behaviour. The YAML schema and `CORE-Flow.md §6`
are the documentation surfaces for this expectation.

**Auditability.** A governor reading a flow YAML can determine exactly which
caller params reach which step without reading any Python source. This is the
governance invariant this decision protects.

**Validator future work.** A future `FlowValidator` check — a step declares
`consumes: [source_file]` but the declared action has no `source_file`
parameter — would surface authoring errors before runtime. This is Band D
backlog; not blocking this ADR.

---

## CORE-Flow.md §6 Amendment

Add the following subsection after the `FlowResult` schema table:

---

### Parameter Routing

A caller may supply runtime parameters when invoking a Flow:

```python
result = await flow_executor.execute("flow.build_tests", write=True, source_file="src/foo.py")
```

Each step declares the caller parameters it consumes via the `consumes` field
in its YAML declaration. `FlowExecutor` forwards only declared keys to that
step. Undeclared caller parameters are dropped at the FlowExecutor boundary
and never reach `ActionExecutor`.

A step with no `consumes` declaration (or `consumes: []`) receives no caller
parameters — only its static `params` are passed.

Static `step.params` always pass through regardless of `consumes`.

This contract ensures parameter routing is auditable from the flow YAML
without inspecting Python action signatures.

---

## References

- `src/body/flows/executor.py` — `_execute_step` (line 9017)
- `src/body/flows/registry.py` — `FlowStep`, `FlowRegistry._load_file`
- `src/body/atomic/executor.py` — `_prepare_params` (line 2191)
- `CORE-Flow.md §6` — Execution Contract (amended by this ADR)
- GitHub #216 — this issue
- GitHub #215 — RemediationMap flow_id wiring (blocked on this ADR)
