---
kind: adr
id: ADR-158
title: 'ADR-158 — Vocabulary register-assignment corrections: severity moves to Operational, two field-list errors in the register-assignment table corrected'
status: proposed
---

<!-- path: .specs/decisions/ADR-158-vocabulary-register-assignment-corrections.md -->

# ADR-158 — Vocabulary register-assignment corrections: severity moves to Operational, two field-list errors in the register-assignment table corrected

**Status:** Proposed
**Date:** 2026-08-31
**Prompted by:** #854 (G2 fixture-coverage gap-closure for `governance.vocabulary_registers.*`) — depth-verifying
the two rules' mappings surfaced that `CORE-Vocabulary-Registers.md` §5's register-assignment table
disagrees with the already-ratified ADR-059 D2, and that two of the table's field-surface descriptions
don't match any authored content in the live `.intent/` corpus.
**Extends:** ADR-059 (severity vocabulary governance) — this ADR closes the gap between D2's ratified
decision and the paper that was supposed to reflect it.

---

## Context

### Finding 1 — severity's register assignment contradicts ADR-059 D2

`CORE-Vocabulary-Registers.md` §5 assigns Severity (`ERROR`, `WARNING`, `INFO`) to the **Diagnostic**
register (`UPPER_CASE`). ADR-059 D2 (accepted 2026-05-19) already retired that three-value UPPER_CASE
scale and replaced `audit_severity` in `enums.json` with a five-value lowercase scale (`info`, `low`,
`medium`, `high`, `block`), explicitly "consistent with the governed enum" — i.e. the Operational
grammar. `.intent/rules/governance/vocabulary_registers.json`'s `diagnostic_fields_must_be_uppercase`
rule already carries a historical note acknowledging this: "ADR-059 D2 inverted the canonical casing
to lowercase." The paper itself was never updated. Confirmed independently: `enums.json`'s live
`audit_severity` entry is `["info", "low", "medium", "high", "block"]`; `src/shared/models/audit_models.py`'s
`AuditSeverity` docstring states "Stored as lowercase string via `__str__`."

With severity reclassified, the Diagnostic register's only remaining assigned concept-family is Audit
verdict (`PASS`/`FAIL`/`DEGRADED`). A corpus-wide search (every `.intent/**/*.yaml` and `*.json` file,
walked and parsed, not grepped) found zero scalar occurrences of `PASS`, `FAIL`, or `DEGRADED` anywhere
in `.intent/`. Verdict states are computed at runtime (`src/mind/governance/auditor.py`,
`src/shared/infrastructure/intent/audit_verdict.py`) and never authored as static `.intent/` content.
The Diagnostic register therefore has no live `.intent/`-authored surface today.

### Finding 2 — "Enforcement strength" row's surface is unauthored

§5 lists the surface for Enforcement strength (`blocking`, `reporting`, `advisory`) as `` `strength:` /
`enforcement:` field ``. A corpus-wide walk of every `.intent/**/*.yaml`/`*.json` file (excluding
`.intent/META/` and `.intent/enforcement/mappings/`) found `strength` never appears as an authored
field anywhere; `enforcement` appears 58+ times, consistently lowercase (`policy`... `enforcement:
"blocking"`, etc.). `strength` is in fact the name `enums.json` gives to the enum *vocabulary itself*
(`definitions.strength.enum == ["blocking", "reporting", "advisory"]`) — the same value set `enforcement`
fields actually carry. `strength` was apparently intended as an alternate field name and never adopted.

### Finding 3 — "Workflow ordering mode" row's surface is a nested block, not a scalar

§5 lists the surface for Workflow ordering mode (`single`, `sequential`, `parallel`) as `` `ordering:`
field ``. The same corpus walk found `ordering:` is always a nested config block
(`mode`, `depends_on`, `next_on_success`, `next_on_failure`) in every one of the 11 live
`.intent/workflows/stages/*.yaml` files — never a bare scalar. The actual scalar value governed by
`enums.json`'s `workflow_ordering_mode` enum is the nested `ordering.mode` field (confirmed: all 11
files currently carry `mode: sequential`).

---

## Decision

**D1 — Reclassify Severity from Diagnostic to Operational register in §5's table**, citing this ADR
and ADR-059 D2 as the joint basis. This is not a new substantive decision — ADR-059 D2 already made
it — this ADR is the paper-amendment vehicle §9 requires to bring the register-assignment table into
conformance with an already-ratified decision.

**D2 — Correct the "Enforcement strength" row's surface** to `` `enforcement:` field `` only, with a
note that `strength` names the enum's own vocabulary key in `enums.json`, not a field ever authored in
practice.

**D3 — Correct the "Workflow ordering mode" row's surface** to the nested `` `ordering.mode:` field ``.

---

## Consequences

- `.intent/rules/governance/vocabulary_registers.json`'s `operational_fields_must_be_lowercase` rule is
  updated: `severity` (via `enums.json`'s `audit_severity` declaration) joins its governed surface per
  D1; `strength` is dropped and `ordering` corrected to `ordering.mode` per D2/D3.
- `diagnostic_fields_must_be_uppercase` is **retired**, not renamed — per D1, the Diagnostic register
  has no remaining `.intent/`-authored surface for it to check. Enforcement downgraded to `advisory`;
  its `.intent/enforcement/mappings/` entry removed so no findings dispatch; rationale documents the
  reinstatement trigger (a diagnostic-register field is authored into `.intent/`, or verdict states
  become static content), following the existing retirement precedent set by `logic.di.no_global_session`
  (`.intent/rules/architecture/async_logic.json`).
- `CORE-Vocabulary-Registers.md` is corrected throughout (§1's motivating example, §2.3's examples and
  surfaces, §3's table, §4.1's stale rule-ID reference, §4.2 rewritten, §5 per D1-D3, §6, a new §7
  non-goal scoping out code-identifier references) via direct commit citing this ADR, per §9's own
  amendment procedure — the §5 table change is this ADR's decision; propagating that same decision into
  the paper's other illustrative sections is not a further new decision.
- `governance.passive_gate.enforced_by_must_resolve` (`.intent/rules/governance/` — checked via
  `src/mind/logic/engines/contracts_gate.py`) is separately strengthened (tracked under #854, not this
  ADR) to cover `python_runtime`-engine rules and to flag a missing `enforced_by`/`enforcement_location`
  as a violation rather than silently skipping it — the systemic gap that let both of these rules ship
  with no real consumer for as long as they did.

## References

- `.specs/decisions/ADR-059-severity-vocabulary-governance.md` (D2 — the ratified decision this ADR
  reconciles the paper against)
- `.specs/papers/CORE-Vocabulary-Registers.md` (the paper this ADR amends)
- `.intent/rules/governance/vocabulary_registers.json`
- `.intent/rules/architecture/async_logic.json` (`logic.di.no_global_session` — retirement precedent)
- `.intent/META/enums.json` (`audit_severity`, `strength`, `workflow_ordering_mode` definitions)
- Issue #854
