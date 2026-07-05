---
kind: adr
id: ADR-141
title: "ADR-141 — Assisted Lane: Subprocess Audit for Non-Graph Engine Fixes"
status: accepted
depends_on: ["ADR-109", "ADR-073"]
---

<!-- path: .specs/decisions/ADR-141-assisted-lane-subprocess-audit.md -->

# ADR-141 — Assisted Lane: Subprocess Audit for Non-Graph Engine Fixes

**Date:** 2026-07-05
**Status:** Accepted (governor decision 2026-07-05 — D1–D7 ratified. Implementation
lands as one change-set; `not_audit_engine` → `not_graph_engine` rename is a one-cycle
breaking change accepted at the verdict dict boundary.)
**Author:** Darek (Dariusz Newecki)
**Closes:** #663

**Governing ADRs:**
- ADR-109 D6 — defines the self-reference boundary this ADR lifts
- ADR-073 D3 — engine taxonomy

---

## Context

ADR-109 D6 deferred subprocess validation for engine-touching diffs with the note
"disproportionate to how rarely engine-bug findings occur." The motivating case (#661 —
a `no_orphan_files` false positive whose fix was a detector bug in `knowledge_gate.py`)
was resolved as a direct governed commit. #663 tracks the deferred work.

### The two engine classes

Investigation (#663 recon, 2026-07-05) found that the 16 registered engines split
cleanly on DB dependency:

| Engine | Uses `context.knowledge_graph` / `symbols_map`? | Subprocess-validatable? |
|--------|------------------------------------------------|------------------------|
| `knowledge_gate` | Yes — requires live DB graph (built by DbSyncWorker) | No — graph is stale relative to worktree |
| All other 15 | No — pure filesystem / AST / intent analysis | Yes — stateless AuditorContext is sufficient |

The `knowledge_gate` engine (and its private helper `_knowledge_gate_duplication.py`) is
the only engine whose oracle requires DB data built from the pre-patch codebase. Running
the subprocess with the worktree's code but the pre-patch graph would produce a stale
verdict; the refusal is correct for this engine.

The other 15 engines — `ast_gate`, `artifact_gate`, `glob_gate`, `runtime_gate`,
`taxonomy_gate`, `workflow_gate`, `contracts_gate`, `attestation_gate`, `cli_gate`,
`action_gate`, `grc_judge`, `llm_gate`, `llm_gate_stub`, `passive_gate`, `regex_gate`
— do not touch the knowledge graph. Their rules run correctly in a subprocess with
`stateless=True` AuditorContext against the worktree's code.

---

## Decisions

### D1 — Split the engine-touching boundary by graph dependency

The assisted lane routes engine-touching diffs on graph dependency, not engine presence
alone:

- **Graph-dependent engine touch** (`knowledge_gate.py`): keep the existing refusal
  (ADR-109 D6). Updated error message distinguishes this case from D2.
- **Graph-independent engine touch** (all other 15): route to the subprocess audit
  path (D3). The ADR-109 D6 boundary is lifted for these engines.

### D2 — Engine graph-dependency declared on the engine class

`BaseEngine` gains `requires_knowledge_graph: ClassVar[bool] = False`.
`KnowledgeGateEngine` overrides it to `True`. `EngineRegistry` exposes
`graph_dependent_engine_files() -> frozenset[str]` — the source-file set for engines
where `requires_knowledge_graph is True`.

`_touches_audit_engine()` in `assisted_actions.py` is extended to return a
`_EngineTouchResult` named tuple `(serviceable: list[str], must_refuse: list[str])`
distinguishing the two classes without re-testing:

```
serviceable = engine_source_files ∩ touched_py − graph_dependent_files
must_refuse  = graph_dependent_engine_files ∩ touched_py
```

### D3 — Subprocess isolation model

For serviceable engine touches, the lane spawns a subprocess that:

1. Prepends `{worktree_path}/src` to `sys.path` ahead of all installed package paths,
   so the worktree's engine code shadows the process's cached modules.
2. Initialises `AuditorContext(worktree_path, stateless=True)` — skips DB knowledge-
   graph load; the oracle runs purely from filesystem analysis.
3. Calls `run_filtered_audit(actx, rule_ids=[finding_rule], files=None)` at full scope
   and returns findings as a JSON dict to stdout.

The current Python interpreter is used (same venv third-party packages, different
source files on disk from the worktree). No new interpreter binary or virtual
environment is created.

### D4 — Subprocess IPC

- **Input:** a temp JSON file in `var/tmp/` (not argv — findings can be large).
  Fields: `worktree_path`, `rule_id`, `subject_files`.
- **Output:** JSON dict `{"findings": [...], "ok": true, "error": null}` on stdout.
  Non-zero exit or stdout-parse failure → `subprocess_audit: False` in the verdict.
- **Timeout:** 120 s (matches the existing test-runner timeout in `tool_runner.py`).
- **On failure:** subprocess result is included in `data["subprocess_error"]`;
  `checks["subprocess_audit"] = False`; no proposal is created.

### D5 — Subprocess runner in tool_runner.py sanctuary

The subprocess runner is a new function in `src/body/atomic/tool_runner.py` (the
existing designated subprocess sanctuary, per `governance.dangerous_execution_primitives`
rule). The bootstrap script is written to `var/tmp/` (never `/tmp/`).

### D6 — Verdict shape changes

`checks` in the `action_assisted_validate_diff` result gains two new keys:

| Key | Present when | Value |
|-----|-------------|-------|
| `not_graph_engine` | engine-touching diff | True if no graph-dependent engine touched |
| `subprocess_audit` | non-graph engine touch | True if subprocess returned ok + rule cleared |

The existing `not_audit_engine` key is **renamed** to `not_graph_engine`. The proposal
API (`lane_routes.py`) accepts either key name during a one-cycle migration window (the
rename is a breaking change at the verdict dict boundary; direct consumers must update).

### D7 — What this does NOT decide

- Subprocess validation for `knowledge_gate`-touching fixes. The DB graph is stale
  relative to the worktree and cannot reliably validate the rule clearing. Direct
  governed commit remains the correct disposition.
- Rebuilding the knowledge graph inside the subprocess from filesystem state. That
  capability would unblock knowledge_gate subprocess validation and is separate scope.
- LLM-gate subprocess validation. The llm_gate engine requires network access to the
  LLM provider; its subprocess model is distinct and deferred.

---

## Ratifications (governor — 2026-07-05)

1. **D1 (boundary split by graph dependency)** — ratified. Knowledge_gate fixes continue
   to refuse; the 15 graph-independent engines get the subprocess path.
2. **D2 (class attribute + registry method)** — ratified. `requires_knowledge_graph`
   ClassVar is the declared dependency signal.
3. **D3 (subprocess isolation via stateless AuditorContext)** — ratified.
4. **D4 (IPC via var/tmp JSON file, 120 s timeout)** — ratified.
5. **D5 (tool_runner.py sanctuary)** — ratified.
6. **D6 (not_audit_engine → not_graph_engine rename, one-cycle window)** — ratified.
7. **D7 (deferred scope)** — accepted as boundary of this change-set.

---

## Consequences

- Engine fixes for 15 of 16 engine families can now be proposed and validated via the
  assisted lane without requiring a direct governed commit.
- `knowledge_gate.py` fixes continue to require a direct governed commit. The refusal
  message is updated to name the distinction explicitly.
- `not_audit_engine` → `not_graph_engine` is a breaking rename on the verdict dict;
  any consumer of the raw action result must update.
- The `var/tmp/` bootstrap script is ephemeral; written per-invocation, cleaned up
  after the subprocess exits.
