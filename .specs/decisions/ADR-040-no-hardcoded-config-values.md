<!-- path: .specs/decisions/ADR-040-no-hardcoded-values-in-src.md -->

# ADR-040 — No Hardcoded Values in src/

**Date:** 2026-05-12
**Status:** Proposed
**Author:** Darek (Dariusz Newecki)

---

## Context

Separating configuration from code is a foundational principle of
software engineering — present in Twelve-Factor App, Spring
`application.properties`, .NET `appsettings.json`, and every serious
production system built in the last 30 years. The principle is simple:
values that control system behavior at runtime do not belong in source
code. They belong in configuration, where they are visible, adjustable,
and auditable without touching implementation.

CORE already applies this principle to two specific domains:

- ADR-008: `impact_level` externalized to `action_risk.yaml`
- ADR-031: runtime directory paths externalized through `PathResolver`

Both were reactive — a specific problem surfaced, a specific value was
moved. Neither established the general principle.

The trigger for this ADR: a claim limit was adjusted from 500 to 5
during a session by editing `src/` directly. That change required
touching implementation, left no governance trace, and was invisible to
the audit system. The same pattern exists across ~15 identified sites:
worker claim limits, batch sizes, SLA windows, confidence thresholds,
lookback windows, LLM prompt parameters — all hardcoded in `src/`.

CORE's constitutional model already has the right home for these values:
`.intent/enforcement/config/`. This ADR makes placing them there the
law, not the exception.

---

## Decision

### D1 — The rule

Hardcoded numeric and string values that control system behavior MUST
NOT appear in `src/`. They MUST be declared in `.intent/enforcement/config/`
and loaded at call sites via a typed loader following the pattern
established by `src/will/workers/circuit_breaker.py`: a dataclass with
fallback defaults, loaded via `IntentRepository`, degrading gracefully
on failure.

### D2 — Exclusions

The rule MUST NOT flag:

- Enum ordinals — integers whose meaning is their position in a
  sequence (`ROUTINE = 1`, `WARNING = 2`).
- Loop and range literals (`for i in range(3)`).
- Loader files themselves — fallback defaults in a `load_*_config()`
  function are the governed fallback, not a violation.
- `tests/**` — test fixtures use inline values intentionally.
- `infra/**` — outside constitutional audit scope.

Everything else is in scope. There is no escape hatch via comment
annotation; exclusions are explicit, named here or in a future ADR
amendment, and governor-approved.

### D3 — Migration

The migration proceeds in two steps:

1. **Classify and author** — audit all identified sites, group by
   logical concern, author the corresponding `.intent/enforcement/config/`
   YAML files and loader modules.
2. **Wire** — update each call site to read from its loader, removing
   the hardcoded value.

### D4 — Audit rule

A new rule `governance.no_hardcoded_values` lands after at least one
migration grouping is complete, giving it a clean surface to validate
against.

**Statement:** Numeric and string values controlling system behavior
MUST NOT be hardcoded in `src/`. They MUST be declared in
`.intent/enforcement/config/` and loaded via a typed loader.

**Enforcement:** blocking
**Authority:** constitution
**Phase:** audit
**Engine:** `regex_gate` initial deployment; `ast_gate` extension for
default argument literals filed as follow-on.

---

## Consequences

- Any operational value is adjustable by the governor via a YAML edit —
  no `src/` change, no daemon rebuild required.
- The audit system can detect and remediate violations autonomously.
- The principle is now constitutional law and applies to all future
  `src/` additions.
- ~15 known sites require migration; full audit expected to surface
  30–45 sites.
