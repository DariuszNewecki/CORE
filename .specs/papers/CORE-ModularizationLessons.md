---
kind: paper
id: CORE-ModularizationLessons
title: 'Lessons Learned: First Autonomous Modularization Run'
status: canonical
doctrine_tier: informational
---

# Lessons Learned: First Autonomous Modularization Run
# Session: 2026-05-03
# File split: src/body/atomic/sync_actions.py → sync_actions/

---

## What worked

- End-to-end pipeline ran without human intervention after approval
- `SplitPlan` schema validation caught structural problems early
- Logic Conservation Gate correctly blocked semantically unsafe splits
- `__init__.py` re-export pattern preserved caller import paths
- `fix.headers` self-healed the header violations introduced by the split autonomously
- Confidence gate correctly deferred the `file_role_detector.py` split (LLM was right — no clean seam)

---

## Failure 1 — Decorator blindness in ModularitySplitter

**What happened:** `ModularitySplitter` extracted function bodies correctly but silently dropped `@register_action` and `@atomic_action` decorators. The split `sync_actions/sync_actions.py` contained three plain `async def` functions with no registration. The daemon appeared to work post-split because stale `__pycache__` bytecode from the pre-split `.pyc` files served the old registered versions. Next clean boot will show `sync.db`, `sync.vectors.code`, and `sync.vectors.constitution` missing from the registry entirely — breaking 26 call sites.

**Root cause:** `ModularitySplitter._build_module()` reconstructs module content from AST node source ranges. It does not walk the decorator list of each function/class node and include the decorator lines in the extracted range. Decorators at lines N-M that precede `def` at line M+1 are not captured.

**Severity:** Critical. Any split of a file containing `@register_action` or `@atomic_action` will silently produce broken output that passes the Logic Conservation Gate (function bodies are conserved) but fails at runtime.

**Mitigations required:**
1. **Immediate (this session):** Manually restore decorators in `sync_actions/sync_actions.py`.
2. **Short-term:** Fix `ModularitySplitter._build_module()` to include decorator lines when extracting a function or class node. The `ast` node carries `decorator_list` — the line range must start at `decorator_list[0].lineno` when decorators are present, not at `node.lineno`.
3. **Medium-term:** Add a post-split validation step in `action_fix_modularity` that checks each produced file for registration decorator presence when the source file contained them. If a registered action's decorator is absent from all produced files, abort with `ok=False` before writing.
4. **Governance:** Add a constitutional rule or audit check that detects registered action functions (those decorated with `@register_action`) that are not present in the action registry at runtime. This closes the gap between "file exists" and "action is operational."

---

## Failure 2 — __pycache__ masks runtime breakage

**What happened:** After the split wrote broken files, the daemon started and successfully registered all three sync actions — from stale `.pyc` bytecode. The error (`Action not found: sync.db`) only surfaced when `DbSyncWorker` tried to execute, because `ActionExecutor` uses the live in-memory registry (populated at import time from the new broken files), not the cache. The registry initialization log showed successful registration from cache; execution failed from live code. These two signals contradicted each other.

**Root cause:** Python's import system uses `__pycache__` when `.pyc` is newer than `.py`. After `file_handler.write_runtime_text()` writes new `.py` files, the old `.pyc` remains valid until the interpreter invalidates it. A daemon restart triggers re-import, which may still use cached bytecode depending on mtime comparison.

**Mitigations required:**
1. After any `fix.modularity` write, invalidate `__pycache__` for the affected package: `find <package_dir> -name "*.pyc" -delete` or `python3 -Bc "import compileall; compileall.compile_dir(...)"`.
2. In the post-split validation step (see Failure 1 mitigation #3), import the produced files in a subprocess with `PYTHONDONTWRITEBYTECODE=1` to force fresh interpretation.

---

## Failure 3 — Logic Conservation Gate cannot detect operational breakage

**What happened:** The Logic Conservation Gate passed. Function bodies were conserved. The gate measures token/line similarity between original and produced content — it does not know that a function missing its `@register_action` decorator is operationally broken, because the decorator is not part of the function body in the AST sense.

**Root cause:** The gate is a content conservation check, not an operational correctness check. It answers "did the code disappear?" not "does the code still do what it did?"

**Mitigations required:**
1. The Logic Conservation Gate should be augmented with a decorator conservation check: any decorator present on a function in the original must be present on the corresponding function in the split output.
2. Alternatively, treat decorator presence as part of the function's "logical surface" — include decorator lines in the line range that the gate measures.

---

## Failure 4 — LLM module naming drifts from source stem

**What happened (caught and fixed this session):** The LLM produced a `SplitPlan` with `new_package_name` differing from the source file stem. `ModularitySplitter` would have placed output files under the wrong path, causing `__init__.py` re-exports to break all callers. Fixed by enforcing `new_package_name == Path(source_file).stem` in `SplitPlan.validate()` and overriding from action context in `action_fix_modularity`.

**Status:** Fixed. Validate() now enforces the constraint. Action overrides LLM-provided structural fields with authoritative values.

---

## Failure 5 — `logger` exported from package __init__

**What happened:** `ModularitySplitter` generated `sync_actions/__init__.py` with `from .sync_actions import ..., logger`. `logger` is a module-private implementation detail and should never be re-exported from the package. Any caller doing `from body.atomic.sync_actions import logger` would get a module-level logger object, which is a contract violation.

**Root cause:** `ModularitySplitter` re-exports all symbols listed in the split plan, including those that begin with an underscore only if not private by naming convention. `logger` does not start with `_`, so it is treated as a public symbol.

**Mitigations required:**
1. In `ModularitySplitter`, exclude well-known private-by-convention names from `__init__.py` re-exports: `logger`, `log`, `_logger`, and any name matching the pattern `*logger*` or `*log*` at module level.
2. More generally: add a denylist of symbol names that should never be re-exported from a package `__init__.py` regardless of naming convention.

---

## Summary — What fix.modularity cannot yet be trusted to do autonomously

| Capability | Status |
|---|---|
| Split files with clean function/class boundaries | ✅ Works |
| Preserve function body logic (Conservation Gate) | ✅ Works |
| Preserve caller import paths via __init__.py | ✅ Works (after stem fix) |
| Delete original monolith | ✅ Works |
| Preserve registration decorators (@register_action, @atomic_action) | ❌ Broken — Failure 1 |
| Detect operational breakage post-split | ❌ Absent — Failure 3 |
| Cache invalidation after write | ❌ Absent — Failure 2 |
| Filter private-by-convention symbols from __init__ re-exports | ❌ Broken — Failure 5 |

**Conclusion:** `fix.modularity` is safe for files that contain only plain functions and classes with no registration decorators. It must not be used autonomously on files that contain `@register_action`, `@atomic_action`, or other framework-registration decorators until Failure 1 and Failure 3 mitigations are in place. The `impact_level` must remain `moderate` (human approval required) until the decorator conservation gap is closed.

---

## Required follow-up issues

1. **ModularitySplitter decorator blindness** — fix `_build_module()` line range to include decorator lines; add decorator conservation check to Logic Conservation Gate or as a post-split validation step.
2. **__pycache__ invalidation after write** — add cache invalidation to the `fix.modularity` write path.
3. **logger/private symbol filter in __init__ generation** — denylist well-known private-by-convention symbols from package re-exports.
4. **Runtime registration gap detector** — constitutional rule or sensor that detects `@register_action` functions absent from the live registry.
