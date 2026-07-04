---
kind: adr
id: ADR-137
title: "ADR-137 — Instrument No-Data Semantics and Sanctuary Registry"
status: accepted
---

<!-- path: .specs/decisions/ADR-137-instrument-no-data-semantics-sanctuary-registry.md -->

# ADR-137 — Instrument No-Data Semantics and Sanctuary Registry

**Date:** 2026-07-02
**Governing paper:** `.specs/papers/CORE-Instrument-Attestation.md`
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-07-02)
**Band:** B — Governance Infrastructure
**Grounding papers:** CORE-Instrument-Attestation.md; ADR-045 (finding lifecycle);
ADR-091 (artifact-type discipline)
**Related:** Issue #563 (F-19 convergence); external architecture review 2026-07-02 §7a, §7d, §13b

---

## Context

### The no-data problem

`src/cli/resources/runtime/health.py:479-484` implements the frozen-flow override:

```python
flow_zero = created == 0 and resolved == 0 and stuck == 0
if flow_zero and trajectory["direction"] in ("stable", "insufficient-data"):
    trajectory["direction"] = "frozen"
```

This is the correct semantics: **zero flow is a distinct verdict class, not a clean pass.**
It was added as Finding #6 / issue #563 fix after the F-19 verification failure — a period
during which AuditViolationSensor posted zero findings because its universe was empty, and
the system read this as "converging" rather than "not looking."

The pattern is right but anonymous. `AuditViolationSensor` itself has no equivalent: if its
artifact glob returns zero files, it runs the auditor (which produces zero violations),
reports completion, and nothing downstream distinguishes this from a genuinely clean pass
over a healthy file population.

### The sanctuary problem

Two production code sites write files through mechanisms the `no_direct_writes` sensor
cannot see (pathlib variable-receiver pattern, detection-inert per ADR-073 §check taxonomy):

- `src/shared/action_logger.py:54` — append-mode log write; FileHandler has no append
  primitive; circular dependency if routed through ActionExecutor
- `src/cli/resources/coherence/seed.py:211` — streaming JSONL export; materializing the
  full collection in memory to use `write_runtime_text` would be impractical

Both sites carry `SANCTUARY (#506 Option 3)` comments. The comment is the only governance
record. There is no registry, no schema, no expiry, and no closure-ADR discipline. A third
site added tomorrow with the same comment would be indistinguishable from the two known,
reviewed sites.

---

## Decision

### D1 — No-data guard in AuditViolationSensor

When `file_count == 0` after the artifact glob walk, `AuditViolationSensor.run()` MUST post
a `no_data` report rather than proceeding to the audit pass. The report subject is
`audit_violation_sensor.no_data` with payload fields `rule_namespace`, `file_count: 0`, and
`artifact_type`. The run still satisfies the silence contract (a report was posted) but the
`no_data` subject is distinguishable from `run.complete`, allowing future sensors and
dashboard queries to detect universe-empty cycles.

This operationalizes the frozen-flow principle at the sensor level, giving
`CORE-Instrument-Attestation.md` its second working instance.

### D2 — Sanctuary registry

Create `.intent/enforcement/sanctuaries.yaml`. Each entry carries:
- `site`: repo-relative file path
- `rule_id`: the rule the site would otherwise violate
- `rationale`: why delegation is structurally impossible
- `closure_adr`: this ADR (ADR-137)
- `deadline`: "open" if no path to closure exists; else a date

The two existing SANCTUARY comment sites become the first two entries.

### D3 — Update SANCTUARY comments

`action_logger.py` and `seed.py` SANCTUARY comments are shortened to a single reference
line: `# SANCTUARY: see .intent/enforcement/sanctuaries.yaml` plus the invariant reason.
The full rationale lives in D2's registry entry, not in the code.

### D4 (future) — Graduate to a named rule

Once D1 is applied to at least one additional sensor beyond `AuditViolationSensor`, extract
the pattern as a named rule in `.intent/rules/governance/instrument_quality.json`:
`governance.instrument.no_data_verdict`. CORE-Instrument-Attestation.md points at two
working instances and graduates from informational to law. Scheduled as a separate work
package; not in scope here.

---

## Consequences

**Positive:**
- AuditViolationSensor universe-empty cycles are now visible in the blackboard and
  distinguishable from clean passes — the F-19 failure mode is structurally detectable
- Sanctuary sites are enumerable from `.intent/` rather than requiring a grep of all
  SANCTUARY comments in src/
- Adding a new sanctuary site now requires an entry in the registry (governance friction),
  not just a code comment (invisible)

**Negative / watch items:**
- `file_count == 0` can be a legitimate transient state (new repo, repo without the
  artifact type). The `no_data` report is advisory-level; it does not block. Downstream
  consumers should treat repeated `no_data` reports as a sensor-health signal.
- D4 is explicitly deferred. `governance.instrument.no_data_verdict` does not exist as a
  rule until that ADR ships.

---

## Delivery phases

| Phase | Deliverable | Status |
|---|---|---|
| D1 | `AuditViolationSensor` — no-data guard | Done |
| D2 | `.intent/enforcement/sanctuaries.yaml` | Done |
| D3 | SANCTUARY comment updates | Done |
| D4 | Named rule + CORE-Instrument-Attestation graduation | Future ADR |
