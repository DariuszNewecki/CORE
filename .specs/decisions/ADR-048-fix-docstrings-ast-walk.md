---
kind: adr
id: ADR-048
title: ADR-048 — `fix.docstrings` walks the AST instead of the knowledge graph
status: accepted
---

<!-- path: .specs/decisions/ADR-048-fix-docstrings-ast-walk.md -->

# ADR-048 — `fix.docstrings` walks the AST instead of the knowledge graph

**Status:** Accepted
**Date:** 2026-05-15
**Authors:** Darek (Dariusz Newecki)
**Closes:** none directly; closes the detection-vs-remediation gap that
ADR-047 exposed.
**Relates to:** ADR-047 (`purity.docstrings.required` moved to ast_gate),
ADR-008 (action impact classification), CORE-Action.md (atomic action
contract), CORE-Finding.md §6 (what makes a finding actionable).

---

## Context

ADR-047 moved `purity.docstrings.required` from `llm_gate` to `ast_gate`.
The new gate uses `ast.walk(tree)` to find any `FunctionDef`,
`AsyncFunctionDef`, or `ClassDef` node missing `ast.get_docstring(node)`,
skipping `_`-prefixed names. It is correct: it finds every public
symbol whose body lacks a docstring, anywhere in the tree — including
methods inside classes, nested functions, and class declarations
themselves.

On 2026-05-15, the post-restart audit cycle produced findings on seven
files. The governor approved all seven `fix.docstrings` proposals. All
seven reached `Status: completed` in ~10 seconds each. **Zero git
commits landed. Zero files changed.** Every invocation logged "All
public symbols have docstrings." and returned `ok=True` without doing
any work.

### Root cause — two stacked bugs in `fix.docstrings`

Reading `src/body/self_healing/docstring_service.py:_async_fix_docstrings`:

1. **Knowledge-graph-only symbol discovery** (lines 109-121).
   ```python
   knowledge_service = context.knowledge_service
   graph = await knowledge_service.get_graph()
   symbols = graph.get("symbols", {})
   ...
   symbols_to_fix = [
       s for s in symbols.values()
       if s.get("kind") == "function" and not _has_docstring_in_source(repo_path, s)
   ]
   ```
   Two filters mask findings:
   - `kind == "function"` excludes `ClassDef` (knowledge graph indexes
     classes under `kind == "class"`).
   - The knowledge graph indexes top-level symbols only. Methods inside
     a class and nested functions inside a parent function are never in
     `symbols.values()`, so they cannot be candidates regardless of
     their `kind`.

2. **The mutation path calls a non-existent atomic action** (lines 205-214).
   ```python
   for rel_path, modifications in file_modification_map.items():
       for mod in modifications:
           await executor.execute("write.docstring", ...)
   ```
   `write.docstring` is not registered in `ActionRegistry`. If `symbols_to_fix`
   were ever non-empty, this `executor.execute` call would raise. It is
   currently inert because the knowledge-graph filter short-circuits to
   "All public symbols have docstrings." before reaching this line.

The combined effect: `fix.docstrings` is a no-op for the entire class of
findings ADR-047 surfaces (methods, classes, nested functions), and
silently masks a second bug that would surface immediately if (1) were
fixed in isolation.

### Observed concrete consequences (2026-05-15)

| File | Symbol AST-gate flagged | Why fix.docstrings missed it |
|---|---|---|
| `src/api/main.py:46` | `def health_check()` | Nested inside `create_app()` — not in knowledge graph |
| `src/will/workers/commit_reachability_auditor.py:51` | `async def run(self)` | Method on a class — not in knowledge graph |
| `src/cli/commands/audit_reporter.py:39` | `class AuditPhase` | `kind == "class"` excluded by filter |
| `src/body/atomic/registry.py:295` | nested `def decorator()` | Nested function — not in knowledge graph |
| `src/body/atomic/modularity_fix.py:286,290,294,298` | four functions | Likely nested or method-shaped |

The detection layer is correct on each of these. The remediation layer
sees an empty candidate set.

### Why this matters for the autonomy story

The proposals on the dashboard read `completed`. Lifetime counters move.
"Last consequence" updates. But the underlying violations remain — and
will be re-detected on the next audit cycle, generating new findings,
new proposals, new no-op completions. **A loop dynamic distinct from
the two CORE memory already names** (transient-failure flooding, stale
revival): *detection-remediation scope mismatch* — the detector flags
more than the remediator can handle, and the remediator's
silent-success path renders the loop invisible until you check that
files actually changed.

### Canonical insertion logic already exists

`src/body/workers/doc_writer.py:_insert_docstring` (lines 172-208) walks
`ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef` via `ast.walk`,
computes the insertion line as `body[0].lineno - 1`, computes indentation
as `" " * (node.col_offset + 4)`, dedups via "skip if first body element
is a string Expr," and processes bottom-to-top to preserve line numbers.
That worker is declared in `.intent/workers/doc_writer.yaml` with
`status: paused`, so the logic is idle. It is the correct
implementation; it just lives in the wrong place.

`PromptModel.load("docstring_writer")` (line 142) and `extract_source_code`
(line 30) both already handle all three node kinds correctly.

The fix is to relocate and integrate logic that already exists, not to
write something new.

---

## Options considered

**Option A — Replace the knowledge-graph walk with an AST walk, and
absorb `_insert_docstring` from doc_writer.** Single-file change to
`docstring_service.py`. Reuses every reusable component already in the
tree. doc_writer's worker declaration moves to retirement after the
logic relocates.

**Option B — Register `write.docstring` as a real atomic action.**
Fixes bug 2 explicitly. Adds one new file (`write_docstring_action.py`)
plus an entry in `action_risk.yaml`. Conceptually clean per
CORE-Action.md — single-symbol insertion is an atomic operation. But
the inner write is a thin wrapper over `FileHandler.write_runtime_text`
plus AST insertion, with no separate governance distinction worth
modeling as its own action. Adds surface without commensurate
governance value.

**Option C — Add a fallback path inside `fix.docstrings` that re-detects
symbols via AST when the knowledge-graph filter returns empty.**
Two-stage discovery — try graph first, fall back to AST walk if graph
is empty. Compatible with the existing logic. But preserves the
graph-walk as the primary path, even though the AST walk is strictly
more comprehensive. Doesn't simplify, doesn't fix bug 2.

**Option D — Narrow ADR-047's AST gate scope to match the existing
remediation coverage.** Restrict `check_docstrings_present` to top-level
`FunctionDef|AsyncFunctionDef` only; drop `ClassDef` and skip nested
nodes. Eliminates the gap by under-detecting. *Regression on ADR-047's
correctness gain. Rejected on principle.*

---

## Decision

### D1 — Symbol discovery via `ast.walk(tree)`, not the knowledge graph

`_async_fix_docstrings` in `src/body/self_healing/docstring_service.py`
discovers symbols needing docstrings by parsing the target file directly:

```python
src = (repo_path / file_path).read_text(encoding="utf-8")
tree = ast.parse(src)
candidates: list[tuple[ast.AST, int]] = []  # (node, lineno)
for node in ast.walk(tree):
    if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
        continue
    if node.name.startswith("_"):
        continue
    if ast.get_docstring(node) is not None:
        continue
    candidates.append(node)
```

This matches `ast_gate`'s `check_docstrings_present` definition of
"public symbol needing a docstring" exactly (`purity_checks.py:34-49`).
Detection and remediation converge on the same predicate, by
construction.

The `file_path` parameter is now required when `_async_fix_docstrings`
is invoked autonomously. The legacy whole-tree sweep mode (`file_path
is None` — used by CLI) iterates over every `.py` file under
`src/api/**`, `src/cli/commands/**`, `src/will/workers/**`,
`src/body/atomic/**` (matching the audit rule's scope) and applies the
same AST predicate. The knowledge-graph dependency is removed entirely
from this code path.

### D2 — Inline AST-based insertion replaces the non-existent atomic action

The `executor.execute("write.docstring", ...)` call site is replaced by
inline insertion logic ported from `doc_writer._insert_docstring`. For
each generated docstring, the function:

1. Locates the target node by matching `lineno` (more robust than name —
   handles classes and methods with same-named symbols elsewhere in the
   file).
2. Computes the insertion offset as `body[0].lineno - 1` (1-indexed AST
   → 0-indexed line list).
3. Computes the indentation as `" " * (node.col_offset + 4)`.
4. Processes insertions bottom-to-top so earlier line numbers stay
   valid after later inserts shift the file down.
5. Persists the rewritten file via
   `core_context.file_handler.write_runtime_text(rel_path, content)` —
   the governed mutation surface (CORE-Mutation-Surface; the same path
   `fix.headers`, `fix.ids`, `fix.format` use).

No new atomic action is registered. The line in `action_risk.yaml`
stays untouched. The fix is internal to the existing `fix.docstrings`
action's implementation.

### D3 — Retire `doc_writer` worker

`src/body/workers/doc_writer.py` and `src/will/workers/doc_worker.py`,
plus their declarations `.intent/workers/doc_writer.yaml` and
`.intent/workers/doc_worker.yaml` (both currently `status: paused`),
become redundant once D2 absorbs the insertion logic. They are
deleted. The blackboard subject family `write.docstring` (referenced
only by these workers) becomes unused; no entries currently exist of
that subject.

Removing dead-or-paused parallel paths is in keeping with
CORE-Common-Governance-Failure-Modes §10 (Cleverness Accumulation —
parallel implementations are suspect).

---

## Consequences

### Positive

- **The detection-remediation gap closes.** Every finding ADR-047 can
  surface, ADR-048's `fix.docstrings` can act on. Methods, classes,
  nested functions, async functions — all reachable.
- **The masked second bug is fixed by the same change.** The
  non-existent `write.docstring` call site is gone. If a future
  refactor changes the discovery side, the mutation side won't latently
  break.
- **The autonomous loop produces real consequences for docstring
  findings, not false `completed` signals.** Approving a
  `fix.docstrings` proposal now reliably lands a commit and changes
  the file. The dashboard's "completed" counter reflects work that
  happened.
- **One canonical implementation, not two parallel ones.** The
  insertion logic lives in one place. Future fixes to indentation,
  multi-line docstrings, or symbol matching update one file.
- **`fix.docstrings`'s impact_level (`moderate` in action_risk.yaml)
  remains correct.** The action still invokes an LLM to generate the
  docstring text; that's the moderate-risk operation. The insertion
  mechanics are deterministic; the LLM judgment is the reason for
  moderate classification.

### Negative

- **Whole-tree sweep mode (legacy CLI) reads more files.** Previously
  it iterated `symbols.values()` from the in-memory knowledge graph;
  now it walks the filesystem. Order of magnitude similar (~400 files
  in the four scope dirs vs ~400 indexed symbols), but the I/O shape
  differs. On the autonomous path (`file_path` supplied), this is
  irrelevant — one file is read.
- **The knowledge graph becomes one path narrower.** D1 removes one of
  the graph's consumers. Other consumers (orphan checks, blast-radius
  computation, vector building) are unaffected. But the precedent is
  worth noting: high-fidelity AST inspection beats knowledge-graph
  indexing for purity-style checks, generally. Future authoring should
  weigh whether new checks should also bypass the graph.
- **Symbol matching by `lineno`** assumes the source file hasn't
  changed between detection (audit posts finding with line) and
  remediation (action reads file fresh). In practice this is safe —
  the action reads the file in the same execution as it walks the AST
  — but if multiple proposals were batched and the first edit shifted
  line numbers, the second's `lineno` would be stale. **Mitigation:**
  the bottom-to-top processing order inside a single file invocation
  preserves correctness within one call; the cross-proposal case is
  prevented by `ViolationRemediator`'s per-file dedup
  (`one_finding_one_proposal`).

### Neutral

- ADR-047's rule scope and engine choice are unchanged.
- `purity.no_todo_placeholders` (the placeholder-content rule) is
  unchanged.
- Action risk classification for `fix.docstrings` is unchanged
  (`moderate`).
- `extract_source_code` and `_has_docstring_in_source` become unused
  helpers in `docstring_service.py` — D1 stops calling them. They are
  removed in the same change.
- Action impact level for the (now retired) `write.docstring` action
  was not declared in `action_risk.yaml`; nothing to remove there.

---

## Verification

This ADR is verified when, after D1+D2+D3 land:

1. Approving a `fix.docstrings` proposal for a file with a known
   missing docstring on a class, method, or nested function (e.g. any
   of the seven files documented above) produces a commit by
   `core-daemon` that adds the docstring at the correct location with
   correct indentation. The audit re-run on the same file passes
   `purity.docstrings.required`.
2. Approving a `fix.docstrings` proposal for a file with no missing
   docstrings (rare, but possible due to manual edits between
   detection and remediation) logs "All public symbols have
   docstrings." and returns `ok=True` *without* attempting to call any
   non-existent action.
3. `core-admin proposals show <id>` on a successfully-executed
   docstring proposal shows `Status: completed`, the corresponding git
   commit hash in `execution_results`, and a non-zero file
   modification count.
4. The `awaiting_reaudit` quarantine flow handles the case where the
   action runs but the symbol-in-question has been deleted between
   detection and remediation (no node matches `lineno`) — the action
   reports `ok=True` with an empty modification list, the proposal
   completes, the audit re-run on next cycle confirms no violation,
   and ADR-045 quarantine resolves the finding.

A single end-to-end demonstration against one file (e.g.
`src/api/main.py:health_check`) satisfies criterion 1. Criterion 2 is
covered by running against a file that has no current violations.
Criterion 3 is observable on every successful execution. Criterion 4
requires a controlled stale-finding scenario; out of scope as a
verification requirement but worth noting as defensive behavior.

---

## References

- `src/body/self_healing/docstring_service.py:84-214` — current
  `_async_fix_docstrings`; D1 + D2 target.
- `src/body/self_healing/docstring_service.py:52-81` —
  `_has_docstring_in_source`; removed under D1.
- `src/body/self_healing/docstring_service.py:30-49` —
  `extract_source_code`; removed under D1.
- `src/body/workers/doc_writer.py:172-208` — `_insert_docstring`
  reference implementation; absorbed into `fix.docstrings` under D2.
- `src/body/workers/doc_writer.py:60-170` — full doc_writer worker
  body; deleted under D3.
- `src/will/workers/doc_worker.py` — doc_worker bridge; deleted under
  D3.
- `.intent/workers/doc_writer.yaml`, `.intent/workers/doc_worker.yaml`
  — paused worker declarations; deleted under D3.
- `src/mind/logic/engines/ast_gate/checks/purity_checks.py:32-49` —
  `check_docstrings_present` (ADR-047); D1 mirrors its predicate.
- `src/shared/infrastructure/storage/file_handler.py:97-126` —
  `FileHandler.write_runtime_text`; the mutation gateway D2 uses.
- `var/prompts/docstring_writer/` —
  `PromptModel.load("docstring_writer")` artifact; unchanged.
- ADR-047 — `purity.docstrings.required` moved to ast_gate; this ADR
  closes the gap that move surfaced.
- 2026-05-15 governor session — 7 `fix.docstrings` proposals reached
  `completed` status with zero file modifications. Observation that
  motivated this ADR.
