# ADR-005: Govern audit verdict policy in `.intent/`

**Status:** Accepted
**Date:** 2026-04-20
**Authors:** Darek (Dariusz Newecki)
**Related:** ADR-004 (task_type phase map in `.intent/`)
**Reconnaissance:** `.specs/state/2026-04-20-audit-verdict-governance.md`

## Context

`ConstitutionalAuditor._determine_verdict` (src/mind/governance/auditor.py) is
the sole authoritative producer of `AuditVerdict`. It encodes the decision
rule for audit compliance in three branches:

1. any crashed rule → `DEGRADED`
2. any finding with `severity == ERROR` and `context.finding_type !=
   "ENFORCEMENT_FAILURE"` → `FAIL`
3. otherwise → `PASS`

This rule is the most load-bearing governance decision CORE makes. It
determines what "the code is compliant" means in every audit report, every
convergence metric, and every claim in the Prior Art whitepaper.

The rule currently lives entirely in `src/`. `.intent/phases/audit.yaml`
authorizes the audit phase to `declare_pass_fail` and forbids it from
`bypass_failed_rules`, but nowhere in `.intent/` does any file codify the
severity-to-verdict mapping, the crashed-rules precondition, or the
`ENFORCEMENT_FAILURE` carve-out.

This is a policy/mechanism inversion. The principle established in ADR-002
— *policy in `.intent/`, mechanism in `src/`* — is violated: the
programmer, not the governor, currently decides what counts as compliance.
Changing the verdict rule requires a `src/` edit, which bypasses the
constitutional review path that `.intent/` edits go through.

ADR-004 solved the same inversion for the task-type-to-phase mapping by
moving it from a `_PHASE_BY_TASK_TYPE` dict in `src/` to
`.intent/enforcement/config/task_type_phases.yaml` with a governed loader.
The same pattern applies here.

## Decision

Author `.intent/enforcement/config/audit_verdict.yaml` codifying the
severity-to-verdict mapping, the carve-out list, and the DEGRADED
preconditions as data. Author a governed loader at
`src/shared/infrastructure/intent/audit_verdict.py` mirroring the
`task_type_phases.py` pattern. Retrofit `_determine_verdict` to branch on
the loaded policy rather than on hardcoded values.

The policy YAML is the governance authority. `src/` becomes pure
mechanism: given a policy and a set of findings, produce the verdict the
policy describes.

## Alternatives Considered

**Leave the rule in `src/` and document it in a paper.** Rejected — a
paper is not machine-checkable against `src/`. The rule and the paper
would drift. The purpose of `.intent/` is precisely to be the source the
runtime reads.

**Use `.intent/cim/thresholds.yaml`.** Rejected — that file governs CIM
drift detection thresholds, a different concern. Mixing verdict policy
into it would conflate two unrelated authorities.

**Fall back to hardcoded defaults when the YAML is missing (ADR-004
pattern).** Rejected — see §3 below. This is the one place ADR-004's
pattern does not translate.

**Make `_determine_verdict` a method on a `VerdictPolicy` object
constructed from the YAML, rather than a staticmethod reading the policy
per call.** Deferred — the construction-time binding has ergonomic
appeal, but it complicates the retrofit (wider surface change) without
changing the governance outcome. Worth revisiting if verdict policy
grows multiple consumers.

## §3 — Fallback behaviour: missing policy forces DEGRADED

ADR-004 established the pattern that a missing/corrupt `.intent/` config
file falls back to hardcoded constants that mirror the YAML defaults. For
phase routing, this is a safe degradation — the worst case is that a
task routes to its intended phase anyway.

For the verdict rule, the same pattern is unsafe. If an operator deletes
or corrupts `audit_verdict.yaml`, silent fallback would mean:

- The audit continues to return `PASS` for code that passes the old
  hardcoded rule.
- The governor has no signal that the policy file is missing.
- A future `.intent/` edit to tighten the rule (say, adding
  `WARNING` to `fail_severities`) has no effect because the file the
  governor edited is not the file the code is reading.

This converts "the verdict law is missing" into "the verdict law is
silently the old one." The failure mode is indistinguishable from
success.

The alternative — and the decision — is that a missing or unreadable
`audit_verdict.yaml` forces `AuditVerdict.DEGRADED`. This is
philosophically consistent with the existing DEGRADED semantic: a
crashed rule produces DEGRADED because compliance is unknown when the
check for it failed. A missing verdict policy is a stronger form of the
same — compliance is unknown when the rule for deciding it is absent.

Operational consequence: a governor who accidentally corrupts the YAML
sees every subsequent audit return DEGRADED until the file is restored.
This is loud, visible, and recoverable. The silent-PASS alternative is
none of those things.

## Consequences

**Positive:**

- The verdict rule becomes a `.intent/` edit. The governor can tighten
  compliance (e.g., `WARNING` → `fail_severities` for a strict release
  gate) without touching `src/`.
- The rule that defines compliance is now reviewable as constitutional
  law rather than as a programmer choice.
- Missing-policy failures become instrument-failure signals, not silent
  behaviour changes.
- The Prior Art whitepaper's §4 claim (CORE covers policy declaration
  end-to-end) gets one more row of concrete evidence: the verdict rule
  itself is declared policy.

**Negative:**

- The Evidence Ledger at `src/cli/resources/code/audit.py` does not
  currently persist `crashed_rule_ids`. After this change, "why was this
  run DEGRADED?" is answerable only from the live audit output or logs,
  not from the ledger. Ledger extension is out of scope for this ADR but
  should be tracked.
- A missing policy file now makes the audit instrument unavailable, not
  just suboptimal. This raises the operational cost of `.intent/`
  corruption. Mitigated by: YAML is version-controlled; schema validation
  at load time; explicit DEGRADED signal rather than silent failure.

**Open follow-ups:**

- Extend the Evidence Ledger to persist `crashed_rule_ids` and the
  resolved policy snapshot (what rule was in force when this verdict
  was produced). Required for full consequence-log traceability of
  verdict decisions.
- Consider a constitutional rule that forbids `src/` from computing
  `AuditVerdict` values outside `_determine_verdict`. Currently informal.
- Stale docstring cleanup at `src/mind/governance/audit_types.py:34`
  (`AuditSeverity.LOW` reference — the enum has no `LOW`). Drive-by in
  the implementation session.
