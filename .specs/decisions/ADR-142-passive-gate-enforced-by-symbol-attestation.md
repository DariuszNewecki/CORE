---
kind: adr
id: ADR-142
title: "ADR-142 — Passive Gate Enforced-By Symbol Attestation"
status: accepted
depends_on: ["ADR-138", "ADR-136", "ADR-113"]
---

<!-- path: .specs/decisions/ADR-142-passive-gate-enforced-by-symbol-attestation.md -->

# ADR-142 — Passive Gate Enforced-By Symbol Attestation

**Date:** 2026-07-05
**Status:** Accepted (governor decision 2026-07-05 — D1–D4 ratified. Implementation
lands as one change-set.)
**Author:** Darek (Dariusz Newecki)

**Governing paper:** `.specs/papers/CORE-Rule-Authoring-Discipline.md`
**Governing ADRs:**
- ADR-138 — defines the passive_gate contract (sensor-driven rules yield to the engine)
- ADR-136 — substrate-enforcement taxonomy and the rules→dispatch blind spot
- ADR-113 — evidence classes (PROVEN / ATTESTED / INFERRED)

---

## Context

### The passive_gate surface

23 enforcement mapping entries across 10 mapping files declare `engine: passive_gate`.
Of those, 14 carry an `enforced_by` param — a dotted Python path (`body.module.ClassName`
or `will.module.function_name`) that names the source symbol responsible for enforcement:

```yaml
proposal_lifecycle.transitions.valid_sequence:
  engine: passive_gate
  params:
    enforced_by: "will.autonomy.proposal_state_manager.ProposalStateManager"
```

This is a governance claim: "audit trust is delegated to this symbol; it enforces the
rule at runtime." The claim has no verification. If the named symbol is deleted, renamed,
or moved, the audit engine still returns `ok=True` — the claim becomes silently false.

### The already-stale reference

Recon (2026-07-05) found one stale reference: `.intent/enforcement/mappings/infrastructure/
cli_commands.yaml` names `features.maintenance.command_sync_service._sync_commands_to_db`.
The `features.*` namespace was retired; the actual symbol lives at
`body.maintenance.command_sync_service._sync_commands_to_db`. The audit passes `ok=True`
on a claim that has not been valid since the namespace migration.

### Why this matters

passive_gate is not a workaround — it is the semantically correct engine for rules whose
enforcement lives in runtime substrate (ADR-138 D1). But "correct semantics" depends on
the `enforced_by` claim being true. A stale claim turns a legitimate governance decision
into silent governance absence: the rule exists, the mapping exists, the engine runs, the
finding is `ok=True` — and nobody catches that enforcement was removed.

ADR-136 identified the rules→dispatch blind spot ("no standing sensor for which mappings
route to an unknown engine") but left the `enforced_by` drift vector open. This ADR
closes it.

---

## Passive-gate attestation classes

For precision, the 23 passive_gate rules are classified:

| Class | Description | Example rules | `enforced_by`? |
|-------|-------------|---------------|----------------|
| **A — Runtime substrate** | Enforcement lives in a named Python symbol; the symbol performs a guard (validates, raises, rejects) | `proposal_lifecycle.*`, `planning.*`, `autonomy.conservation.*` | Yes — 14 rules |
| **B — Write-time gate** | Enforcement is PatternValidators at code-generation boundary; fires before any file lands | `code.tests.*`, `code.imports.generated_*` | No — referenced by `note:` |
| **C — Sensor-driven** | A running Worker or Sensor IS the detector; the audit engine correctly yields | `governance.commit_authorship_integrity`, `ai.prompt.governed_change_requires_review` | No |
| **D — Placeholder / retired** | Explicitly not-yet-implemented, or superseded | `ai.prompt.constitutional_grounding_section`, `logic.di.no_global_session` | No |

Only Class A rules carry enforcement claims that can become stale. This ADR targets Class A
exclusively. Class B enforcement is tested by the test suite (PatternValidators has unit
coverage). Class C is owned by the Worker lifecycle. Class D is acknowledged technical debt
or historical record.

---

## Decisions

### D1 — Classify all passive_gate rules by attestation class (data only)

The 4 classes defined above are declared in the mapping `params` block for each rule.
Class A entries MUST carry `enforced_by`. Classes B, C, D MUST NOT.

No code change. This is a naming convention that makes the class visible in coverage
reports and lets D2's check know which entries to verify.

A new mandatory field `attestation_class` is added to every passive_gate mapping:

```yaml
governance.commit_authorship_integrity:
  engine: passive_gate
  params:
    attestation_class: "C"   # sensor-driven; worker IS the detector
    ...
```

The existing `enforced_by` field is only valid when `attestation_class: "A"`.

### D2 — New rule: `governance.passive_gate.enforced_by_must_resolve` (blocking)

A new blocking rule verifies that every Class A passive_gate mapping's `enforced_by`
resolves to an existing Python symbol in `src/`.

**Implementation:** new `check_type: passive_gate_symbol_attestation` in `contracts_gate.py`.
It is context-level (runs once per audit pass, not per file):

1. Walks all `.intent/enforcement/mappings/**/*.yaml`
2. For each `engine: passive_gate` entry with `attestation_class: "A"`
3. Parses `enforced_by` as a dotted path (e.g. `will.autonomy.proposal_state_manager.ProposalStateManager`)
4. Resolves to a candidate file: longest matching prefix → `src/will/autonomy/proposal_state_manager.py`
5. Parses the file's AST; checks that the named class or function (`ProposalStateManager`) is defined
6. Emits a CRITICAL `AuditFinding` for any unresolvable claim

The check is **purely AST / filesystem** — no DB access, no imports, no runtime execution.
It verifies existence of the symbol, not the correctness of its enforcement logic (see D4).

Rule definition lives in a new `.intent/rules/governance/passive_gate_attestation.json`.
Mapping lives in a new `.intent/enforcement/mappings/governance/passive_gate_attestation.yaml`.

### D3 — Fix the stale `features.maintenance.command_sync_service` reference

The CLI commands mapping in `.intent/enforcement/mappings/infrastructure/cli_commands.yaml`
references `features.maintenance.command_sync_service._sync_commands_to_db`. The correct
path is `body.maintenance.command_sync_service._sync_commands_to_db`.

This is a Path A write: the governor names this specific file in the implementation
confirmation.

### D4 — Guard-behavior verification deferred

Level 2 verification (does the named symbol actually *contain* enforcement logic?) is not
in scope for this ADR. The threat model for this ADR is **silent stale references**
(renamed or deleted symbols). The symbol-existence check (D2) fully closes that threat.

Guard-behavior verification would require per-rule integration tests
(e.g., "feed an invalid transition to ProposalStateManager; assert it raises"). That is a
meaningful safety investment and belongs in a future ADR once D2 is established and
operating for at least one cycle.

---

## Deliverables

| ID | Artifact | Description |
|----|---------|-------------|
| D1 | `.intent/enforcement/mappings/**/*.yaml` | Add `attestation_class` field to all 23 passive_gate entries |
| D2a | `.intent/rules/governance/passive_gate_attestation.json` | New rule: `governance.passive_gate.enforced_by_must_resolve` (blocking) |
| D2b | `.intent/enforcement/mappings/governance/passive_gate_attestation.yaml` | Mapping: `contracts_gate` + `passive_gate_symbol_attestation` |
| D2c | `src/mind/logic/engines/contracts_gate.py` | New `_check_passive_gate_symbol_attestation` handler + dispatch |
| D3 | `.intent/enforcement/mappings/infrastructure/cli_commands.yaml` | Fix stale `features.*` → `body.*` reference |
| Tests | `tests/mind/logic/engines/test_contracts_gate__passive_gate_attestation.py` | Unit tests for the new check_type |

Implementation order: D3 → D1 → D2a → D2b → D2c → Tests (one change-set).

---

## What this does NOT cover

- **Guard-behavior verification** — D4 above; separate ADR
- **Class D "not-yet-implemented" rules** — these are acknowledged debt; closing them is
  tracked via the rules themselves (each has an open issue or ADR reference in its note)
- **Class B and C rules** — they have no `enforced_by` claim to verify; their enforcement
  surfaces are tested by other means

---

## Risk

The new check runs at every audit pass. If D3 is applied first, the check launches clean
(0 violations). If D2 is deployed before D3, it immediately fires 1 finding against the
stale `features.*` reference — which is the correct behavior (it is a real violation).
Either order is safe.

The `attestation_class` field on existing mappings (D1) is additive; YAML loaders that
don't consume it are unaffected.
