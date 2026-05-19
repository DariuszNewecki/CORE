# ADR-060 — Governance Input Staleness Closure

**Date:** 2026-05-19
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Band:** E — Constitutional Completeness
**Companion to:** ADR-039 (Audit-input cache invalidation)
**Commit landed:** e36b42f7 (`fix(audit): refresh governance per audit run`)
**Amends:** `CORE-IntentRepository.md §4a`

---

## Context

ADR-039 established per-cycle invalidation of two audit input classes:

- **Source-file inputs** — `_file_list_cache`, `_rel_path_map`,
  `_pattern_cache`, `_AST_CACHE` — cleared by
  `AuditorContext.invalidate_file_cache()`.
- **Rule/policy index** — `IntentRepository._policy_index`,
  `_rule_index`, `_hierarchy` — dropped and rebuilt by
  `IntentRepository.reload()`.

A third input class was not addressed: the governance resources held
directly on `AuditorContext` itself:

- `self.policies` — the governance resources dict, populated once at
  `AuditorContext.__init__` via `_load_governance_resources()`. This is
  the in-memory view of all `.intent/` policy content exposed to rules
  and checks. Even after `IntentRepository.reload()` rebuilds the index,
  `self.policies` retains the boot-time snapshot.
- `self.enforcement_loader` — the `EnforcementMappingLoader` instance,
  also constructed at `__init__`. Enforcement mappings govern which rules
  apply to which files, what check parameters are passed, and which files
  are excluded.

Commit `e36b42f7` closed this gap by adding `reload_governance()` to
`AuditorContext` and wiring it at the entry of
`ConstitutionalAuditor.run_full_audit_async` (`auditor.py:88`).

However, `reload_governance()` was wired to only one of three audit run
entry points. Source-file cache invalidation (`invalidate_file_cache()`)
is called from all three:

| Entry point | `invalidate_file_cache()` | `reload_governance()` |
|---|---|---|
| `auditor.py:89` (`run_full_audit_async`) | ✓ | ✓ (e36b42f7) |
| `filtered_audit.py:143` (`run_filtered_audit`) | ✓ | ✗ missing |
| `audit_violation_sensor.py:124` (`AuditViolationSensor.run`) | ✓ | ✗ missing |

The result is an asymmetry: on the CLI path (`filtered_audit`) and the
daemon sensor path (`AuditViolationSensor`), source files are rescanned
each cycle but governance inputs (policies, enforcement mappings) remain
at boot-time state.

Additionally, `CORE-IntentRepository.md §4a` states:

> "The contract: `.intent/` edits require a daemon restart to take effect."

This clause predates ADR-039 and was not amended when `reload_governance()`
landed. It is now incorrect.

---

## Decisions

### D1 — Extend `reload_governance()` wiring to all three audit entry points

`reload_governance()` is added to `filtered_audit.py` and
`audit_violation_sensor.py` at the same call site as the existing
`invalidate_file_cache()` calls.

Rationale: the asymmetry is an oversight, not a deliberate design choice.
The sensor path (`AuditViolationSensor`) is the most load-bearing case —
it is the autonomous loop's detection mechanism. Enforcement mapping changes
(new mappings, amended excludes, tightened parameters) must be visible
within one sensor interval, not only when a full audit is triggered. The
CLI path (`filtered_audit`) is the governor's primary audit tool; stale
governance there is daily friction.

The cost is one additional `_load_governance_resources()` call and one
`EnforcementMappingLoader` construction per cycle per entry point. At the
current policy count (~180 rules across the active `.intent/` tree) this
is already accepted on the `auditor.py` path and adds no new cost class.

### D2 — Amend `CORE-IntentRepository.md §4a`

The clause "`.intent/` edits require a daemon restart to take effect." is
superseded. The amended contract:

> **The contract:** `.intent/` edits are picked up on the next audit cycle
> via `AuditorContext.reload_governance()`. The daemon does not need to be
> restarted for new or amended rules, policies, enforcement mappings, or
> contracts to become active. The maximum staleness window is one sensor
> interval (600 s, governed in `.intent/workers/audit_sensor_*.yaml`).
>
> A daemon restart is still required when `.intent/` structural changes
> affect `IntentRepository` initialization (e.g. a new directory added to
> `META/intent_tree.yaml`) or when `src/` Python code changes (governed
> by ADR-030).

The rest of §4a — the read-only contract, the singleton model, the
no-write-methods guarantee — is unchanged.

---

## State at ADR acceptance

| Item | State |
|---|---|
| `AuditorContext.reload_governance()` | Exists — commit `e36b42f7` |
| `auditor.py:88` call site | Wired — commit `e36b42f7` |
| `filtered_audit.py` call site | Missing — D1 |
| `audit_violation_sensor.py` call site | Missing — D1 |
| `CORE-IntentRepository.md §4a` | Stale — D2 |

---

## Consequences

**Positive:**

- The ADR-039 goal is fully met across all three audit entry points: the
  drift window for source files, rules, policies, and enforcement mappings
  is bounded to one sensor interval on every code path.
- `CORE-IntentRepository.md` is accurate again. The paper-vs-reality gap
  introduced when `e36b42f7` landed is closed.

**Negative:**

- Two additional `_load_governance_resources()` calls and two additional
  `EnforcementMappingLoader` constructions per cycle (one each for
  `filtered_audit` and `AuditViolationSensor`). At the current policy
  count (~180 rules) this is negligible.

---

## Verification

1. `reload_governance()` is called in `filtered_audit.py` adjacent to the
   existing `invalidate_file_cache()` call at line 143.
2. `reload_governance()` is called in `audit_violation_sensor.py` adjacent
   to the existing `invalidate_file_cache()` call at line 124.
3. `CORE-IntentRepository.md §4a` contains the amended contract from D2
   and no longer contains the clause "restart to take effect."
4. `core-admin code audit` PASS; finding count does not increase beyond
   baseline.

---

## References

- ADR-039 — Audit-input cache invalidation; introduced
  `IntentRepository.reload()` and `invalidate_file_cache()`; commit
  `adf59796`; AST cache supplement `175b46e4`
- ADR-030 — Daemon stale-code detection posture (restart still required
  for Python module changes)
- `src/mind/governance/audit_context.py:159` — `reload_governance()` body
- `src/mind/governance/auditor.py:88` — existing call site
- `src/mind/governance/filtered_audit.py:143` — D1 target
- `src/will/workers/audit_violation_sensor.py:124` — D1 target
- `.specs/papers/CORE-IntentRepository.md §4a` — paper amended by D2
- Commit `e36b42f7` — `fix(audit): refresh governance per audit run`
