---
kind: adr
id: ADR-139
title: "ADR-139 — MyPy Type Safety Remediation Strategy"
status: accepted
---

<!-- path: .specs/decisions/ADR-139-mypy-type-safety-remediation.md -->

# ADR-139 — MyPy Type Safety Remediation Strategy

**Date:** 2026-07-02
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-02)
**Band:** C — Code Quality
**Grounding papers:** URS §4.3 (quality gates); ADR-039 (audit gate timeout fix)
**Related:** Issue #728 (smoke failures); `quality.type_safety` gate (currently advisory)

---

## Context

As of 2026-07-02, `python -m mypy src/` reports **435 errors** across `src/`. The
`quality.type_safety` audit gate is currently **advisory** — findings are surfaced but do
not block commits. This is intentional: the gate was wired before the error backlog was
measured, so promoting it to blocking immediately would lock every commit.

### Error distribution (measured baseline)

| Error code | Count | Category |
|------------|-------|----------|
| `attr-defined` | 77 | Missing attribute (stale/wrong type) |
| `arg-type` | 72 | Wrong argument type at call sites |
| `import-untyped` | 48 | Missing type stubs — all `yaml` (PyYAML) |
| `union-attr` | 46 | Accessing attribute on `X \| None` without guard |
| `call-arg` | 32 | Unknown keyword arguments (wrong model fields) |
| `assignment` | 20 | Incompatible assignment types |
| `override` | 13 | Signature mismatch with supertype |
| `operator` | 13 | Unsupported operand types |
| `return-value` | 8 | Wrong return type |
| other | 11 | `abstract`, `valid-type`, `misc`, etc. |
| **Total** | **435** | |

### Top error-dense files

`will/governance/coverage_runner.py` (10), `body/atomic/path_resolver_rewriter.py` (10),
`will/governance/audit_runner.py` (9), `body/autonomy/micro_proposal_executor.py` (9),
`cli/commands/governance.py` (8), `will/self_healing/test_generation/code_extractor.py` (7),
`will/self_healing/coverage_watcher.py` (7).

### Root cause clusters

**Cluster A — stubs (48 errors, one package):** All 48 `import-untyped` errors come from
`yaml` (PyYAML). Installing `types-PyYAML` eliminates them with zero code changes.

**Cluster B — `X | None` without guard (46 errors):** Optional-typed fields accessed
directly without a None check. Pattern: `self.cognitive_service.aget_client_for_role(…)`
where `cognitive_service` is typed `CognitiveService | None`. These are real latent bugs.

**Cluster C — stale model attr / call-arg (77 + 32 = 109 errors):** Call sites reference
attributes or keyword arguments that no longer exist on the current model. Often caused by
model refactors where the signature changed but callers were not updated.

**Cluster D — `Result[Any]` rowcount (10 errors):** SQLAlchemy `Result` object used with
`.rowcount` which is not on `Result[Any]` — needs cast to `CursorResult`.

**Cluster E — override mismatches (13 errors):** Subclass `execute()` signatures that
diverge from `Component.execute()`. The supertype contract may need a `Protocol`-based
loosening or the subclasses need to align.

---

## Decisions

### D1 — Fix Cluster A immediately (stubs install, no code changes)

Install `types-PyYAML` as a dev dependency. This eliminates 48 errors (11% of total) with
zero code changes and zero risk. Run as the first step of any remediation sprint.

```
pip install types-PyYAML
# add to requirements-dev.txt / pyproject.toml dev dependencies
```

### D2 — Remediate clusters in priority order: B → C → D → E

Remediating in error-count order (A already done) with rationale:

| Order | Cluster | Why first |
|-------|---------|-----------|
| 1 | B (union-attr, 46) | Real latent bugs — None dereference at runtime |
| 2 | C (attr-defined + call-arg, 109) | Largest block; stale callers accumulate drift |
| 3 | D (rowcount, 10) | Mechanical SQLAlchemy cast; contained |
| 4 | E (override, 13) | Requires supertype design decision first |

Cluster E (override) is addressed last because it may require a governor decision on
whether to widen the `Component.execute()` signature or enforce strict subtype conformance.

### D3 — Each cluster delivered as a governed atomic change-set, not a bulk rewrite

Each cluster fix is a separate commit with ruff + mypy verification. No cluster spans more
than one logical subsystem in a single commit. This keeps diffs reviewable and keeps the
gate advisory until a clean-pass commit is achievable.

### D4 — Gate promotion to blocking after total errors reach zero

`quality.type_safety` is promoted from advisory to blocking only after a full clean pass
(`mypy src/` exits 0 with no `--ignore-missing-imports` flag). The promotion is a single
`.intent/rules/` enforcement field change committed by the governor.

Until then the gate remains advisory — findings are surfaced at every audit cycle but do
not block commits. This avoids locking the repo while the backlog is being cleared.

### D5 — `--ignore-missing-imports` is a temporary scaffold, not permanent policy

During the remediation period, CI and the audit gate run with `--ignore-missing-imports` to
avoid noise from third-party packages lacking stubs. This flag is removed as part of the D4
gate-promotion commit. Any new `import-untyped` errors surfacing after D1 are addressed
inline — they do not restart the cluster prioritisation.

### D6 — Cluster E (override) resolution deferred to governor

The 13 `override` errors all trace to `execute()` signature mismatches between concrete
components and `Component.execute()`. Two options exist:

- **Option A**: Widen the supertype signature (add `*args`/`**kwargs` or use a `Protocol`)
- **Option B**: Align all subclass signatures to match the supertype strictly

The governor authors a brief follow-on ADR or decision note before Cluster E is touched.
Neither option is pre-selected here.

---

## Constraints and invariants

- No `# type: ignore` suppressions are added to resolve errors — they hide real bugs.
  The only permitted `# type: ignore` is on pre-existing lines that have them; new ones
  require explicit governor sign-off.
- Stub packages (`types-*`) are dev dependencies only — never in the production install.
- The `quality.type_safety` advisory gate remains wired and firing throughout remediation;
  findings are not suppressed in the audit dashboard.
- MyPy is run with `--strict` off during remediation (current project baseline). Moving to
  `--strict` is out of scope for this ADR.

---

## Sequence

```
D1  Install types-PyYAML            → −48 errors (435 → ~387)
D2a Fix Cluster B (union-attr)      → −46 errors (~387 → ~341)
D2b Fix Cluster C (attr/call-arg)   → −109 errors (~341 → ~232)
D2c Fix Cluster D (rowcount)        → −10 errors (~232 → ~222)
D2d Fix Cluster E (override)        → −13 errors (~222 → ~209)
    (remaining ~209 = other/misc; addressed inline during above passes)
D4  Gate promotion commit           → quality.type_safety → blocking
```

Estimated total remaining after D1–D2d: ≤ 50 (misc/other errors too scattered
for cluster treatment; addressed opportunistically during other change-sets).

---

## Files to change (D1 only — all others per-cluster)

| File | Change |
|------|--------|
| `pyproject.toml` or `requirements-dev.txt` | Add `types-PyYAML` |
