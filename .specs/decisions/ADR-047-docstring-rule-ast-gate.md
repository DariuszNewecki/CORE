---
kind: adr
id: ADR-047
title: ADR-047 — Move `purity.docstrings.required` from `llm_gate` to `ast_gate`
status: accepted
---

<!-- path: .specs/decisions/ADR-047-docstring-rule-ast-gate.md -->

# ADR-047 — Move `purity.docstrings.required` from `llm_gate` to `ast_gate`

**Status:** Accepted
**Date:** 2026-05-15
**Authors:** Darek (Dariusz Newecki)
**Closes:** none directly; informs #311
**Relates to:** ADR-043 (llm_gate throughput — established the pre-selector
discipline for llm_gate rules; this ADR retires one llm_gate rule entirely),
ADR-008 (action impact classification), #311 (verdict-content evidence
comment 2026-05-15), and the 17 rejected fix.docstrings proposals on
2026-05-15 (14 stale + 3 recurrence)

---

## Context

`purity.docstrings.required` (`.intent/enforcement/mappings/code/purity.yaml:55–67`)
is currently `engine: llm_gate`. The rule instruction is:

> "Verify that all public functions and classes have a docstring. Return
> a violation if a docstring is missing or is just a placeholder like 'TODO'."

ADR-043 narrowed the rule's scope to four high-leverage src directories
(`src/api/**`, `src/cli/commands/**`, `src/will/workers/**`,
`src/body/atomic/**`) so the audit completed within SLA. That solved
throughput. It did not solve verdict quality.

### Observed evidence (2026-05-15)

On a single governor session, the inbox accumulated 14 `fix.docstrings`
draft proposals over ~33 hours. Cross-referencing against a fresh audit
run revealed:

- 11 of the 14 targeted files that the LLM gate **no longer flags**.
  Same file, same content, different verdict between the run that
  produced the proposal and the run we inspected against.
- 3 of the 14 targeted files that the LLM gate **does still flag** —
  but on inspection, every flagged symbol has a substantive docstring:

  | Flagged | File | Reality |
  |---|---|---|
  | `def info():` | `src/cli/commands/interactive_test.py:74` | docstring at line 75 |
  | `TODO` | `src/cli/commands/repo_census.py:28` | 11-line docstring at lines 40–50 |
  | `class CapabilityTaggerWorker:` | `src/will/workers/capability_tagger.py:36` | 11-line docstring at lines 37–47 |

  3-out-of-3 sampled FAIL verdicts are false positives.

After rejecting all 14, the audit re-ran (via the autonomous sensor
cycle), the same 3 files re-flagged, ViolationRemediator produced 3 new
proposals, the governor rejected those too. The loop reproduces every
audit cycle, indefinitely. Documented in detail in the #311 comment
posted 2026-05-15.

### Why the LLM gate fails this rule

The verification task is structurally checkable. Either there is a
string literal at position 0 of a function or class body, or there is
not. `ast.get_docstring(node) is not None` answers this in microseconds,
deterministically, with no false positives possible by construction. The
LLM is being asked to do AST-level inspection through a natural-language
interface, and it is mis-reading on substantive docstrings — calling
them missing — across runs.

This is not a prompt-engineering problem. A tighter instruction
("return PASS if any triple-quoted string follows the def/class
line") might reduce the false-positive rate, but it cannot eliminate it,
because the underlying model is making the call non-deterministically.
The right answer is to stop asking the LLM to do a check that AST
solves exactly.

### Why move now

Three signals make this the cheap moment:

1. The structural check is **trivial** — `ast_gate` already imports
   `ast.get_docstring` (used in
   `src/mind/logic/engines/ast_gate/checks/modularity_checks.py:118`)
   and is the canonical home for AST-shaped checks.
2. The placeholder-content concern that originally motivated the LLM
   gate ("a docstring that is just 'TODO'") is **already covered** by
   `purity.no_todo_placeholders`
   (`.intent/enforcement/mappings/code/purity.yaml:4–16`), a `regex_gate`
   that flags `TODO|FIXME|TBD` anywhere in source. A docstring of
   `"""TODO"""` would already trigger that regex. No coverage is lost.
3. Each llm_gate eval against this rule consumes audit-SLA budget on the
   local Ollama provider (per ADR-043: ~17s/call, `max_concurrent=2`).
   Retiring one llm_gate rule frees budget for rules that genuinely
   require semantic judgment (`modernization.legacy_scars`,
   `modularity.unix_philosophy`, `architecture.mind.no_execution_semantics`).

---

## Options considered

**Option A — Move the rule to `ast_gate` with a new `check_type:
docstrings_present`.** Add a check function that walks public functions
and classes, returns violations for missing `ast.get_docstring()`.
Register the new `check_type` in `ast_gate/engine.py`. Update the
mapping. Single change-set, ~50 LoC.

**Option B — Tighten the LLM gate prompt.** Make the instruction
explicit: "If any `Expr(Constant(str))` is the first statement of the
function or class body, return PASS." This pushes AST grammar into the
natural-language interface. Cheap to try; does not eliminate
non-determinism; does not free SLA budget.

**Option C — Per-file `excludes` in the rule's mapping.** Add the three
known-false-positive files to `excludes:`. Treats the symptom of the
day. The exclude list grows monotonically as more files surface
problems. Eventually the rule's effective scope is the empty set, at
which point it is operationally retired without the audit trail of
having been retired.

**Option D — Status quo, accept the loop.** The governor rejects 3
false positives per audit cycle, forever. Documented evidence shows
this costs ~33h of review burden per 14 proposals. Multiplied across
the audit cadence, this is unbounded. Rejected on cost grounds alone.

---

## Decision

### D1 — `purity.docstrings.required` moves from `llm_gate` to `ast_gate`

The mapping at `.intent/enforcement/mappings/code/purity.yaml:55–67` is
updated:

```yaml
purity.docstrings.required:
  engine: ast_gate
  params:
    check_type: docstrings_present
  scope:
    applies_to:
      - "src/api/**/*.py"
      - "src/cli/commands/**/*.py"
      - "src/will/workers/**/*.py"
      - "src/body/atomic/**/*.py"
    excludes:
      - "**/__init__.py"
      - "tests/**/*.py"
```

The `instruction:` parameter from the llm_gate variant is dropped — the
check is structural, not natural-language. Scope is unchanged.

### D2 — Add `check_docstrings_present` to `ast_gate`

A new check function in
`src/mind/logic/engines/ast_gate/checks/purity_checks.py` (or a new
`docstring_checks.py` if `purity_checks.py` is grown sufficiently):

```python
def check_docstrings_present(tree: ast.AST) -> list[Violation]:
    """Flag public functions and classes whose body lacks a docstring."""
    violations: list[Violation] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            continue
        if node.name.startswith("_"):
            continue  # private; out of scope per existing rule semantics
        if ast.get_docstring(node) is None:
            violations.append(Violation(
                rule_id="purity.docstrings.required",
                file_path=...,
                line=node.lineno,
                message=f"{type(node).__name__} '{node.name}' has no docstring",
            ))
    return violations
```

Dispatched in `src/mind/logic/engines/ast_gate/engine.py` at the
`check_type` branch (alongside the existing ~16 check types).

### D3 — Placeholder content remains `purity.no_todo_placeholders`'s job

This ADR does not change the scope, engine, or behavior of
`purity.no_todo_placeholders`. That rule's regex (`TODO|FIXME|TBD`)
already catches placeholder docstrings as a side effect of catching
placeholder strings anywhere in source. No coverage gap opens.

---

## Consequences

### Positive

- **Zero false positives by construction.** The check answers a
  structural question with a structural mechanism. No model
  non-determinism. No run-to-run verdict instability.
- **Sub-millisecond per file** versus ~17s for an llm_gate call.
  Audit SLA gains roughly the full scope's worth of seconds back —
  modest in isolation, additive across the audit cycle.
- **Frees llm_gate concurrency budget.** Per ADR-043, the local Ollama
  provider runs `max_concurrent=2`. Each rule retired from llm_gate is
  one fewer rule contending for that slot.
- **Eliminates the governor-inbox noise** documented in the #311
  comment of 2026-05-15. The recurrence loop on `interactive_test.py`,
  `repo_census.py`, `capability_tagger.py` stops.
- **Sets precedent.** Other llm_gate rules whose verdicts are
  structurally checkable become candidates for the same treatment
  (none currently identified, but the pattern is now articulated).

### Negative

- **Loses semantic judgment about docstring *quality*.** An AST check
  cannot tell whether a docstring is *accurate* or *useful* — only
  whether it is present and non-placeholder. But the LLM gate was not
  reliably judging quality either; the evidence shows it was
  misjudging *presence*, which is the easier task. Trading
  unreliable-semantic for reliable-structural is a net gain.
- **Existing llm_gate cache entries for this rule become orphaned.**
  `llm_gate_engine` caches verdicts keyed by
  `sha256(rel_path + instruction + content)` (`llm_gate.py:55`). When
  the rule's engine changes, the old cache rows are never queried
  again. They are not harmful — just stale rows in the cache table.
  Cleanup is opportunistic, not blocking; can be left to the next
  cache-prune pass.
- **Three files (`interactive_test.py`, `repo_census.py`,
  `capability_tagger.py`) which the LLM has been incorrectly flagging
  will now pass cleanly.** This is correct — they have docstrings —
  but it does mean any past audit history showing these as failing
  will look anomalous next to the post-D1 audit history. This is
  diagnostic information for #311, not noise; flagged here so the
  shift in verdict isn't misread as regression.

### Neutral

- The rule's *scope* (which directories it applies to) is unchanged.
  The ADR-043 narrowing remains in force.
- `purity.no_todo_placeholders` is unaffected.
- The audit's overall coverage count is unchanged. One rule moves
  engine; total rule count stays at 144.

---

## Verification

This ADR is verified when, after D1+D2 land:

1. The next audit cycle runs `purity.docstrings.required` via
   `ast_gate` (visible in audit log — no "llm_gate cache hit" or
   "llm_gate verdict" entries for this rule).
2. The three previously-false-positive files
   (`interactive_test.py`, `repo_census.py`, `capability_tagger.py`)
   no longer produce findings.
3. At least one file genuinely missing a public docstring (in any of
   the four scope directories) produces a finding — confirming the
   check discriminates.
4. The autonomous `ViolationRemediator` no longer generates recurring
   `fix.docstrings` proposals for the three files. The governor inbox
   stays clean across at least two audit cycles.

A single full audit run satisfies 1–3. Two consecutive audit cycles
satisfy 4.

---

## References

- `.intent/enforcement/mappings/code/purity.yaml:55–67` — rule under
  change.
- `.intent/enforcement/mappings/code/purity.yaml:4–16` —
  `purity.no_todo_placeholders` regex_gate (covers the placeholder
  concern).
- `src/mind/logic/engines/ast_gate/engine.py:75+` — dispatch site for
  new `check_type`.
- `src/mind/logic/engines/ast_gate/checks/purity_checks.py` — likely
  home for the new check; `src/mind/logic/engines/ast_gate/checks/`
  is the directory of existing check modules.
- `src/mind/logic/engines/ast_gate/checks/modularity_checks.py:118` —
  existing use of `ast.get_docstring()` in this engine.
- `src/mind/logic/engines/llm_gate.py:55, 88–99` — llm_gate cache key
  (relevant to the orphan-cache note).
- ADR-043 — llm_gate throughput; established the pre-selector
  discipline for llm_gate rules. This ADR is the inverse pattern:
  retire an llm_gate rule when its question is structural.
- #311 — Confirm LLM verdicts materialize for the four llm_gate
  rules gated in d97e3fab. The 2026-05-15 comment documents the
  verdict-quality evidence that motivates this ADR.
- Governor reject batches 2026-05-15 ~08:00 UTC and ~08:20 UTC —
  14 + 3 fix.docstrings proposals rejected as LLM-gate false
  positives or stale.

## Amendment — 2026-05-16 (commit 6c1c7270)

**Predicate tightened: nested-fn closures excluded.**

The `check_docstrings_present` implementation shipped with D2 used `ast.walk`
with no parent awareness. `ast.walk` descends into all child nodes, so a `def`
nested inside another `def` (a closure or inner helper) was flagged as a
violation. These symbols are private-by-construction — unreachable from the
module's public interface — and are not the intent of this rule.

Observed effect: 3 of the first 7 `fix.docstrings` draft proposals (targeting
`body/atomic/registry.py`, `cli/commands/coverage/generation_commands.py`,
`api/main.py`) were pure noise from this gap. All 7 were rejected and findings
returned to `awaiting_reaudit`.

**Fix (commit 6c1c7270):** Before the violation walk, annotate `_parent` on
every node via `ast.iter_child_nodes`. During the walk, skip any
`FunctionDef`/`AsyncFunctionDef` whose immediate `_parent` is also a
`FunctionDef` or `AsyncFunctionDef`. `ClassDef` nodes are not skipped on this
basis — a class nested inside a function is unusual enough to warrant
documentation.

The D2 pseudocode above reflects the original design; the live implementation
in `purity_checks.py` reflects this amendment. ADR-049 doctrine/code parity is
satisfied by this note.

## Amendment — 2026-05-27 (CCC #464)

**Engine transition complete; Context section describes pre-ADR state.**

`purity.docstrings.required` is `engine: ast_gate` as of 2026-05-15. The
Context section's "currently `engine: llm_gate`" (line 20) is historical
narrative describing the pre-decision state when this ADR was drafted, not
a claim about current configuration. Live truth:
`.intent/enforcement/mappings/code/purity.yaml:58–59`. CCC SAMECONCERN
candidate `2f44312f-024b-4290-81d2-415ae363e882` surfaced the temporal
ambiguity; this marker resolves it without rewriting the original text.
