---
kind: adr
id: ADR-094
title: ADR-094 — URS Satisfaction Sensor (implementing ADR)
status: accepted
---

<!-- path: .specs/decisions/ADR-094-urs-satisfaction-sensor-implementation.md -->

# ADR-094 — URS Satisfaction Sensor (implementing ADR)

**Date:** 2026-06-06
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-06 — drafted under explicit "produce that ADR" confirmation at the close of the URS Verifier paper-completion arc. The decisions below close paper §13's eight numbered deferrals plus §8.2's trusted-kernel obligation. They turn architectural shape into engineering surface; no architectural choice remains open after this ADR.)
**Grounding decisions:** ADR-093 D4 + D7 + D8 (URS-line discipline, grandfathering, recursive cleanup — this ADR ships the mechanical enforcement of D4). ADR-091 D2 (canonical subject format `<artifact_type>::<sub_namespace>::<identity_key_value>`, instantiated here as `urs::<urs_id>::<criterion_id>`). ADR-091 D6 (F-42's published-contract discipline applied to a fourth sensor instance). ADR-090 D1 + D2 + D5 (artifact_type registry shape — D1 introduces a fifth declaration under that schema). ADR-067 (CCC, the prior coherence-family member whose sibling-instrument register this ship amends).
**Related:** `.specs/papers/CORE-URS-Verifier.md` (the paper this ADR codifies — its §13 deferrals 1–8 land as D1–D8 below; §8.2's kernel obligation lands as D9). `.specs/requirements/URS-requirement-fulfillment-verification.md` (the URS the paper operationalizes; its Appendix A Criterion Manifest is the first ship's primary fixture and exercises every behavioral verdict path the sensor implements). ADR-093 D8 (the recursive retrofit whose closure this ADR's first ship vindicates by actually running the manifest through a Verifier).

---

## Context

The paper `CORE-URS-Verifier.md` froze the architectural shape of the URSSatisfactionSensor — sensor-class worker, declared-classification dispatch, deterministic verdicts, no LLM, trusted kernel, coverage manifest, URS-author authority. It left eight named decisions to the implementing ADR (§13 items 1–8) and named one further obligation in §8.2 (the trusted-kernel membership shall be declared as an explicit Python list). This ADR closes those nine.

The decisions are not architectural — the paper closed those. They are engineering choices: storage paths, module layout, cadence, CLI shape, dashboard routing, ship-time status, fixture-lifecycle enforcement posture, retrofit cadence for grandfathered URSs, and kernel membership. Each is small in isolation; together they are everything the implementer needs.

After this ADR's acceptance, the implementation phase is engineering, not governance design — same posture the URS-line wraps up with under ADR-093.

---

## Decisions

### D1 — Register a new `urs` artifact_type in the F-41 registry

Paper §10 left two viable paths: register a new `urs` artifact_type, or reuse `spec_markdown` with a path-prefix discriminator.

**Choice: register a new `urs` artifact_type** at `.intent/artifact_types/urs.yaml` per ADR-090 D1. Discovery globs: `.specs/requirements/URS-*.md` and `.specs/requirements/*-URS.md` (URS-line shape per paper §4.7 + grandfathered `CORE-*-URS.md` shape per ADR-093 D7). `identity_key: path`; `urs_id` is the basename without extension. `supported_sensors: [urs_satisfaction_sensor]`. `supported_actions: []` (no `fix.*` exists for URS-class findings; honest per URS §4 secondary-user posture). Other META-schema-mandated fields are implementer scope.

Rejected: reusing `spec_markdown` with a discriminator. URSs carry runtime-consumable manifests, sit at the governance-grounding layer, and bind the URS-line discipline — materially different from other `.specs/` markdown. Per memory `feedback_two_surface_requires_two_structures`, when material difference doesn't survive unification, unification was the bug.

### D2 — Predicates live in Python, not declared in `.intent/` YAML

Paper §5.1 left one ADR call: predicate code as Python under a sensor-strategies subtree, or as `.intent/` YAML resolved by name.

**Choice: Python.** Mechanical predicates touch the filesystem and read-only DB; their natural form is Python. The predicate registry (paper §5.1: keyed by URS-id × criterion-id) lives in `strategies/mechanical.py` as a Python dict. Membership is governance-visible by code review of that one file; no parallel `.intent/` declaration is introduced. A future amendment may externalize the mapping if predicate count grows past what's reviewable.

Behavioral fixtures are documents and follow the paths + discriminator paper §7.1 already specified.

Module subtree: `src/will/workers/urs_satisfaction_sensor/`. The kernel/strategies split and the six-file kernel membership land in D9.

### D3 — Run cadence: per-cycle on the existing daemon

The Verifier runs once per daemon cycle, same shape as `AuditViolationSensor` and `TestCoverageSensor`. No new schedule, no event-driven trigger at first ship.

Cost: full pass at first ship covers 6 URSs (1 URS-line URS with 12 criteria + 5 grandfathered URSs producing only coverage entries). The mechanical-strategy predicates are O(1) per criterion; behavioral fixture exercises are bounded by fixture count (small at first ship — see D9 for the first-ship fixture set). The aggregate run is cheap and within the daemon-cycle budget existing sensors operate under.

A future amendment may add event-driven triggers (URS file change, manifest amendment) if cadence becomes a cost concern. Today, the per-cycle default holds.

### D4 — CLI surface: `core-admin specs verify [URS_ID]`

The CLI surface is one new command under the existing `core-admin specs` namespace:

```
core-admin specs verify [URS_ID] [--format=text|json]
```

- **Without `URS_ID`:** runs the full pass over every URS under `.specs/requirements/`, identical to the per-cycle daemon invocation. Output is the coverage manifest (paper §9.3) plus the per-criterion findings (paper §9.2).
- **With `URS_ID`:** runs the Verifier against a single URS. The `URS_ID` matches the basename-derived identity (e.g., `URS-requirement-fulfillment-verification`).
- **`--format=text` (default):** Rich-formatted output for governor reading.
- **`--format=json`:** machine-readable output, same shape as the blackboard payload.

The command is implemented as a `@core_command` under `src/cli/commands/specs.py` (extending if present, creating if not). CLI invocation is read-only — `write=False` — so only the per-cycle daemon path persists findings to the blackboard. The CLI's role is governor on-demand inspection.

### D5 — Dashboard: route through the existing Convergence Direction panel

URS findings flow into the existing Convergence Direction panel on the governor dashboard, alongside other audit findings. No new panel ships at first.

Rationale: the URS-namespace subject prefix (`urs::*` per paper §9.1) is enough to filter URS-findings out of the panel's stream if a dedicated view is wanted later. Today, the URS count is small (6 URSs, 12 criteria total under the URS-line); routing them through the existing panel gives the governor the right surface without proliferating dashboard widgets. Per memory `feedback_park_cleanup_when_boundary_works`, visible-but-stable governance surfaces defer to substantive live work.

A future ADR may introduce a dedicated URS Coverage panel once URS count or finding volume warrants it. The architectural posture is "extend the surface when usage demands, not when scope might."

### D6 — Ship status: `active` at first invocation

The Verifier ships with `status: active` in its `.intent/workers/urs_satisfaction_sensor.yaml` declaration. Paper §10 named `active` as the architectural default and parked `paused` as a maturation-cadence option; this ADR commits to `active`.

Rationale: noise floor is bounded. Of the 6 URSs at first ship:

- **1 URS** (`URS-requirement-fulfillment-verification`) carries a manifest (per ADR-093 D8) and produces per-criterion verdicts. Its 12 criteria exercise every behavioral verdict path the Verifier implements.
- **5 URSs** are grandfathered per ADR-093 D7 and produce coverage entries with rationale `pre_urs_line_grandfathered` (per paper §11 paragraph 5). They emit no per-criterion findings.

Active ship is the most honest posture: the Verifier exercises itself the first time it runs, producing immediate evidence that the mechanism works. Per memory `user_prefers_visibility_over_polish`, ugly-but-honest beats pretty-but-incomplete; shipping paused would hide the first useful evidence behind manual activation.

### D7 — Fixture lifecycle: reviewer-attention at first ship; audit rule deferred

Paper §7.3 named the fixture-versioning discipline (fixtures reviewed in the same change-set as the URS criteria they verify) and left enforcement choice to the ADR.

**Choice: reviewer attention at first ship.** No audit rule is added in this ADR's implementation phase. The discipline is enforced by governor + reviewer attention, same posture URS R-011's authoring obligation takes.

Rationale: an audit rule requires designing the change-set boundary semantics (when does a URS amendment count as "substantive enough" to require fixture review?). That boundary is non-trivial and would lock in a coarse rule before evidence accumulates about which fixture amendments actually drift. Per memory `feedback_hardening_over_coverage`, hardening live audit violations beats authoring more schemas; per `feedback_exception_register_growth_trap`, interim carve-out registers grow. The honest move is no rule at first, and a separable GH issue tracking the rule design for after fixture-amendment patterns emerge.

**Deferred work:** GH issue filed at this ADR's ship recording the fixture-lifecycle-audit-rule design as forward work, gated on observed amendment patterns.

### D8 — Pre-URS-line URS retrofit cadence: defer all five at first ship

ADR-093 D7 grandfathered five pre-URS-line URSs: `CORE-Ask-URS.md`, `CORE-Governor-Ask-URS.md`, `CORE-Governor-Dashboard-URS.md`, `URS-consequence-chain.md`, `URS-mechanism-coherence.md`. Paper §13 item 8 left their retrofit cadence to the implementing ADR.

**Choice: defer all five.** The Verifier ships exercising only `URS-requirement-fulfillment-verification.md` (the one URS with a manifest, retrofitted under ADR-093 D8). The five grandfathered URSs produce coverage entries marked `pre_urs_line_grandfathered` per paper §11 paragraph 5 and emit no per-criterion findings.

Rationale: each retrofit is its own scope of work — reading the URS, mapping its prose claims to criterion entries, declaring `verification_class` per criterion, authoring `verifier_hint` and fixtures where behavioral. The cost is non-trivial and the URS-mechanism-coherence retrofit in particular is its own architectural exercise. Bundling them into the Verifier's first ship would conflate two scopes.

**Optional invitation:** governor may author retrofits later; each retrofit lands as forward-coverage per ADR-093 D7 wording. The Verifier picks them up automatically on the next cycle. No code change required.

### D9 — Trusted kernel membership: explicit Python list under `TRUSTED_KERNEL`

Per URS R-007 and paper §8.2, the Verifier declares its trusted kernel as a module-level constant `TRUSTED_KERNEL` importable from `src/will/workers/urs_satisfaction_sensor/kernel/__init__.py`. The constant's value is the list of file paths (relative to repo root):

```python
TRUSTED_KERNEL: list[str] = [
    "src/will/workers/urs_satisfaction_sensor/worker.py",
    "src/will/workers/urs_satisfaction_sensor/kernel/discovery.py",
    "src/will/workers/urs_satisfaction_sensor/kernel/manifest_parser.py",
    "src/will/workers/urs_satisfaction_sensor/kernel/dispatcher.py",
    "src/will/workers/urs_satisfaction_sensor/kernel/finding_emitter.py",
    "src/will/workers/urs_satisfaction_sensor/kernel/coverage_builder.py",
]
```

The strategy modules (`strategies/mechanical.py`, `strategies/behavioral.py`, `strategies/judgmental.py`) are excluded by design per paper §8.2 — they are exercised by the kernel, not trusted by it.

**Inspection bound (per URS R-006 / paper §8.3):** the six kernel files together shall be inspectable in 30–60 minutes by a reader with no prior context. The implementer holds this bound as a soft constraint; if any kernel file grows past one-sitting size, the first revision shall refactor it down rather than admit a larger kernel.

**Tooling exposure:** the `TRUSTED_KERNEL` constant is importable and may be consumed by future tooling (e.g., a CI check that warns when kernel files exceed a line-count proxy for inspectability). No such check ships in this ADR; the constant's job at first ship is to make the kernel boundary explicit and reviewable.

---

## Consequences

### One new artifact_type lands; the F-41 registry grows from 5 to 6

`.intent/artifact_types/urs.yaml` is added per D1. The registry's existing five declarations (`doc`, `infra`, `intent_json`, `intent_yaml`, `prompt`) are unchanged; the URS declaration is additive. F-42's `supported_sensors` list-form contract (ADR-091 D4) accommodates the new sensor without schema change.

### One new worker declaration lands at `.intent/workers/urs_satisfaction_sensor.yaml`

The worker declaration carries `identity.class: sensing`, references the `urs` artifact_type by name in `mandate.scope.artifact_type`, and ships with a fresh UUID v4 generated at implementation time per CLAUDE.md. The declaration is consumed by the daemon's per-cycle worker loop on next restart after the ship.

### One new sensor codebase lands at `src/will/workers/urs_satisfaction_sensor/`

Six kernel files + three strategy files + `__init__.py` modules per D2. Each public class and function carries a `# ID: <uuid>` comment per CLAUDE.md. Every kernel module's correctness is asserted by inspection per the trusted-kernel discipline.

### One new CLI command lands at `core-admin specs verify`

The command is implemented under `src/cli/commands/specs.py` (created if absent, extended if present) as a `@core_command` per CLAUDE.md. The command surfaces the same Verifier the daemon runs per-cycle, with the same coverage-manifest output, in a text or JSON format the governor can route into other tooling.

### URS-line discipline becomes mechanically enforceable

Before this ADR, URS-line discipline (ADR-093 D4) was reviewer-enforced. After this ADR's ship and the first daemon cycle that runs the Verifier, any URS-line URS that lands without a manifest produces a `malformed_no_manifest` finding on the blackboard, surfaced on the dashboard panel per D5. The discipline becomes load-bearing rather than aspirational.

### Five grandfathered URSs sit in a stable "coverage entry, no findings" posture

The five pre-URS-line URSs produce coverage manifest entries marked `pre_urs_line_grandfathered` on every Verifier cycle. They do not generate per-criterion findings. The dashboard panel reflects this honestly: the coverage manifest count includes them; the finding count does not. Per `feedback_park_cleanup_when_boundary_works`, the stable posture defers to live work.

### The recursive cleanup from ADR-093 D8 is vindicated by first invocation

ADR-093 D8 retrofitted `URS-requirement-fulfillment-verification.md` with a criterion manifest to close the recursive defect — the URS that demands manifests would have rejected itself as malformed. The first Verifier cycle after this ADR's ship runs that manifest, producing 12 per-criterion verdicts. The recursive cleanup goes from "argued to be sufficient on paper" to "demonstrated by the runtime instrument."

### Fixture lifecycle remains reviewer-enforced; the audit-rule design is deferred

Per D7, the discipline is governor + reviewer attention at first ship. A separable GH issue records the audit-rule design as forward work, gated on observed amendment patterns. No fixture-lifecycle audit rule lands in this ADR's implementation phase.

### Trusted kernel becomes explicit and inspectable

The `TRUSTED_KERNEL` constant per D9 makes the meta-recursion boundary visible: a reader can import the list, walk the six files, and form a judgment about correctness in one sitting. Without the constant, the kernel boundary would live only in this ADR's prose; with it, the boundary is enforceable by inspection and (future) tooling.

### No LLM enters the verdict path; the cognitive_capabilities declaration omits it

The worker declaration explicitly omits `cognitive_capabilities` (paper §5.4). The Verifier never imports `cognitive_service`. The `requires_human_evidence` verdict is deterministic — the verdict is "human evidence required," not "satisfied or unsatisfied." This discipline holds across all three strategy modules.

### Two amendments to sibling documents ship in the implementation phase

Per paper §12.1 and §12.2, the CCC paper §8 and `URS-mechanism-coherence.md` §3 receive amendments registering the URS Verifier as the fourth coherence-family instrument. These ship in the implementation change-set as governor-authored or governor-confirmed Path A writes.

---

## Verification

- This ADR exists at `.specs/decisions/ADR-094-urs-satisfaction-sensor-implementation.md`.
- `.intent/artifact_types/urs.yaml` lands per D1, validated against `META/artifact_type.schema.json`.
- `.intent/workers/urs_satisfaction_sensor.yaml` lands with `identity.class: sensing`, fresh UUID v4, and `mandate.scope.artifact_type: [urs]`.
- `src/will/workers/urs_satisfaction_sensor/` ships with the file layout per D2; every public class and function carries a `# ID: <uuid>` comment per CLAUDE.md.
- `src/will/workers/urs_satisfaction_sensor/kernel/__init__.py` exposes `TRUSTED_KERNEL: list[str]` with the six kernel paths per D9.
- `src/cli/commands/specs.py` exposes `verify` as a `@core_command` per D4 with `--format` defaulting to `text`.
- The first daemon cycle after restart produces a coverage manifest enumerating 6 URSs (1 with manifest, 5 grandfathered) and per-criterion findings only for `URS-requirement-fulfillment-verification`.
- Per-criterion findings carry subjects `urs::URS-requirement-fulfillment-verification::R-<NNN>` per paper §9.1 / ADR-091 D2.
- Behavioral verdicts on the URS-requirement-fulfillment criteria depend on fixtures landed under `.intent/fixtures/urs/URS-requirement-fulfillment-verification/` or `.specs/fixtures/urs/URS-requirement-fulfillment-verification/` per the D2 discriminator. The first-ship fixture set covers at minimum R-001, R-003, R-004, R-011, R-012 (the behavioral criteria from the URS's Appendix A) plus R-009.
- The CCC paper §8 receives the sibling-instrument amendment per paper §12.1.
- `URS-mechanism-coherence.md` §3 receives the prior-work-table amendment per paper §12.2.
- GH issue is filed at ship recording the fixture-lifecycle-audit-rule design as deferred forward work per D7.
- Five grandfathered URSs remain un-retrofitted per D8; optional retrofit is recorded as governor-discretion forward work.

---

## References

- `.specs/papers/CORE-URS-Verifier.md` — the paper this ADR codifies. §13 items 1–8 land as D1–D8; §8.2 obligation lands as D9.
- `.specs/requirements/URS-requirement-fulfillment-verification.md` — the URS the paper operationalizes. Its Appendix A Criterion Manifest is the first-ship fixture and the primary exercise of the Verifier's behavioral verdict paths.
- ADR-093 D4 — URS-line discipline. This ADR ships the mechanical enforcement.
- ADR-093 D7 — grandfathering posture. D8 above honors it by deferring retrofits.
- ADR-093 D8 — recursive cleanup. The first Verifier cycle vindicates that closure.
- ADR-091 D2 — canonical subject format. Instantiated as `urs::<urs_id>::<criterion_id>` per D9 / paper §9.1.
- ADR-091 D4 — `supported_sensors` list-form. D1 honors the form by listing `urs_satisfaction_sensor` against the new artifact_type.
- ADR-090 D1 — artifact_type registry shape. D1 introduces a sixth declaration.
- ADR-090 D5 — forward contract for F-42 and F-43. The URS Verifier honors that contract by registering through the registry, not bypassing it.
- ADR-067 — CCC paper. The sibling-instrument register in CCC §8 receives the amendment per paper §12.1.
- Memory `feedback_two_surface_requires_two_structures` — informed D1's choice of new artifact_type over reusing `spec_markdown`.
- Memory `feedback_hardening_over_coverage` + `feedback_exception_register_growth_trap` — informed D7's reviewer-attention posture over a premature audit rule.
- Memory `feedback_park_cleanup_when_boundary_works` — informed D5's choice to route through the existing dashboard panel and D8's defer-all-retrofits posture.
- Memory `user_prefers_visibility_over_polish` — informed D6's active-at-ship posture.
- Memory `feedback_phase_goal_absorbs_design` — interrogated each deferral as "what does the engineer need?" rather than "what does the paper allow?"
- Memory `feedback_conviction_signal` — the eight deferrals were closed without hedge; each decision carries its rejected alternative explicitly.
