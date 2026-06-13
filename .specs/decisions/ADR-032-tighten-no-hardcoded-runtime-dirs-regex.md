---
kind: adr
id: ADR-032
title: ADR-032 — Tighten `no_hardcoded_runtime_dirs` regex to path-construction context
status: accepted
---

# ADR-032 — Tighten `no_hardcoded_runtime_dirs` regex to path-construction context

**Date:** 2026-05-10
**Status:** Accepted
**Deciders:** Governor (Dariusz Newecki)

---

## Context

ADR-031 introduced `architecture.path_access.no_hardcoded_runtime_dirs` with a
`regex_gate` enforcement. The rule statement scopes violations to "path construction
expressions." The initial regex used three patterns:

```
["'](?:reports|logs)/
["']reports["']
["']logs["']
```

The second and third patterns match any string literal containing `"reports"` or
`"logs"` — including log messages, string comparisons, docstrings, and exclude lists.
This is broader than the rule statement intends.

Observed in the 2026-05-10 remediation session: proposal `98aed243` targeted 24 files.
`fix.path_resolver` (deterministic AST transformer operating on `BinOp(op=Div)` nodes)
produced changes in only 5 of those 24. The remaining 19 had regex matches but no
actual path-construction nodes. After fixing the 5 true violations, the audit count
remained at 40 — confirming the rule's regex was flagging ~35 false positives.

## Decision

Replace the two broad bare-string patterns with a single path-construction-context
pattern. The new pattern set:

```
["'](?:reports|logs)/        ← directory-prefix usage ("reports/filename")
/\s*["'](?:reports|logs)["'] ← path-division operator  (something / "reports")
```

This catches the two structural forms of runtime path construction in the codebase
while excluding standalone string literals in non-path contexts.

Known limitation: `os.path.join(base, "reports")` is not caught by either pattern.
This is accepted — the codebase uses `pathlib` division throughout; `os.path.join`
usage with these strings has not been observed.

The same pattern is mirrored in `_RUNTIME_DIR_PATTERN` in
`src/body/atomic/fix_actions.py` so the remediator's pre-filter stays aligned with
the rule's detection scope.

## Consequences

- False-positive count drops from ~35 to ~0 on the pre-existing corpus.
- True violations (actual path-construction sites) remain detected.
- `fix.path_resolver` and the regex gate now address the same population.
- Rule count after tightening reflects genuine governance debt, not noise.
- `os.path.join` + runtime dir names is an accepted blind spot; mitigated by the
  codebase's consistent use of pathlib.
