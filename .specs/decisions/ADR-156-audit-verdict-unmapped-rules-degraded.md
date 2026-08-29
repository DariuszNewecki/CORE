---
kind: adr
id: ADR-156
title: "ADR-156 — Audit verdict DEGRADEs on unmapped mapping-required rules"
status: accepted
---

<!-- path: .specs/decisions/ADR-156-audit-verdict-unmapped-rules-degraded.md -->

# ADR-156 — Audit verdict DEGRADEs on unmapped mapping-required rules

**Date:** 2026-08-29
**Governing paper:** ADR-005 (`.specs/decisions/ADR-005-govern-audit-verdict-policy.md`) — this ADR extends ADR-005's verdict-policy scheme, it does not replace it
**Status:** Accepted (2026-08-29)
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-08-29 — drafted under governor direction, issue #822; amended same session per governor review — predicate renamed to `any_unmapped_mapping_required_rules`, D1a precedence table and test added, D2 item 1 YAML-header correction added; accepted same session)
**Relates to:** #822 (the originating issue), #820 Group B (where the gap was surfaced and the governor directed recording it separately), commit `0ff9a99e` (made `rule_requires_enforcement_mapping` canonical), ADR-066 (the adjacent, non-overlapping "unmapped" surface — see Context)

---

## Context

### The defect

`AuditVerdict.PASS`'s docstring (`src/mind/governance/auditor.py:41`) promises:

> "PASS: All checked rules passed. No crashes. No unmapped blocking rules."

`ConstitutionalAuditor._determine_verdict` (`auditor.py:137-179`) does not honor the third clause. Its actual logic, quoted in full:

```python
policy = load_audit_verdict_policy()
if policy.get("_error"):
    return AuditVerdict.DEGRADED
if "any_crashed_rules" in policy["degraded_on"] and crashed_rule_ids:
    return AuditVerdict.DEGRADED
if "stats_error" in policy["degraded_on"] and stats.get("stats_error"):
    return AuditVerdict.DEGRADED
fail_sevs = {AuditSeverity[name] for name in policy["fail_severities"]}
ignored_types = set(policy["ignored_finding_types"])
has_blocking_violations = any(...)  # findings-based, ignores unmapped-ness entirely
if has_blocking_violations:
    return AuditVerdict.FAIL
return AuditVerdict.PASS
```

`stats["unmapped_rules"]` is computed correctly upstream (`constitutional_auditor_dynamic.py:334-336`, via `_find_unmapped_rule_ids` → `_mapping_required_rule_ids` → the canonical predicate `shared.infrastructure.intent.rule_registry.rule_requires_enforcement_mapping`, `rule_registry.py:39-61`) and is read exactly once in `run_full_audit_async` — at `auditor.py:123`, for a log line only. It never reaches `_determine_verdict`. A repository with one or more mapping-required rules unmapped currently returns `PASS`.

**Verified latent, not live, at current baseline `17ec2a42`:** running the real pipeline against this repository's current `.intent/` returns `unmapped_rules: 0` (239 mapping-required / 256 declared rules). Confirmed unaffected by the `17ec2a42` retirement commit, which never touched `.intent/`. Zero drift on any of the four relevant files (`auditor.py`, `audit_verdict.yaml`, `audit_verdict.py`, `rule_registry.py`) since `0ff9a99e`. Zero existing test exercises `_determine_verdict` with a nonzero `unmapped_rules` (`tests/mind/governance/test_auditor___determine_verdict.py` has exactly 3 tests: crash → DEGRADED, stats_error → DEGRADED, blocking finding → FAIL).

### Why this is governed, not a quick fix

`.intent/enforcement/config/audit_verdict.yaml`'s own header states: *"This file is the governance authority over audit verdict semantics. Changing verdict semantics is a `.intent/` edit, not a `src/` edit."* Its `degraded_on` list is closed-vocabulary by design — see next section — so a stricter verdict rule cannot be silently patched into `_determine_verdict` without a corresponding governance decision authorizing the new precondition.

### The trap this ADR exists to close: the fix is not YAML-only

`src/shared/infrastructure/intent/audit_verdict.py:42` declares:

```python
_KNOWN_PRECONDITIONS: frozenset[str] = frozenset({"any_crashed_rules", "stats_error"})
```

`_validate_policy` (lines 51-88) raises `ValueError` for any `degraded_on` entry outside this frozenset. `load_audit_verdict_policy` catches that and returns the error sentinel `{"_error": True, "reason": ...}` (lines 124-131), which `_determine_verdict` already treats as DEGRADED — but via the **policy-load-failure branch** (`auditor.py:150-155`, which even logs `"Audit policy unavailable (...) — returning DEGRADED per ADR-005 §3"`), not via the new precondition doing its job.

Concretely: if `.intent/enforcement/config/audit_verdict.yaml` alone gained `any_unmapped_mapping_required_rules` in `degraded_on` — exactly what issue #822's "Proposed resolution" section literally describes — every subsequent audit would go DEGRADED. That looks like the fix working. It is actually the validator rejecting a governed vocabulary word it doesn't recognize yet, logged as an *instrument failure*, not as the intended semantic. This is a class of failure this codebase already has a name for and actively guards against elsewhere (`ADR-005 §3`'s own rationale: "silent fallback converts 'the verdict law is missing' into 'the verdict law is silently the old one'... indistinguishable from success"). This ADR exists specifically so that trap does not get walked into by a well-intentioned narrow implementation of #822.

### Disambiguation from ADR-066

ADR-066 ("Unmapped-Rules Invariant") governs a different surface: whether an active rule's *findings* have a routing entry in `.intent/enforcement/remediation/auto_remediation.yaml` (remediation-dispatch mapping — can a finding be auto-fixed or must it go to a human). This ADR governs whether a declared rule has an entry in `.intent/enforcement/mappings/**` (engine-dispatch mapping — can the rule even be *executed* at all). Both use the word "unmapped" for genuinely different governed relationships. They are adjacent, not overlapping, and this ADR does not touch ADR-066's surface.

---

## Decision

### D1 — Semantic: unmapped mapping-required rule ⇒ compliance unknown ⇒ DEGRADED

> If one or more rules that canonically require an enforcement mapping (per `rule_requires_enforcement_mapping`) are unmapped, audit compliance is unknown and the verdict MUST be `DEGRADED` — not `FAIL`, and not `DEGRADED`-via-policy-load-error.

`DEGRADED`, not `FAIL`, is the correct verdict: an unmapped rule means the audit could not check compliance for it, which is exactly `AuditVerdict.DEGRADED`'s existing documented meaning ("compliance is unknown, not known-bad") — not "code is known non-compliant," which is `FAIL`'s meaning and would be a category error here.

The authoritative count is the existing `stats["unmapped_rules"]` statistic, already computed by `get_dynamic_execution_stats`. No new counting logic. No new interpretation of "mapping-required," "blocking," or "non-advisory" — this ADR binds to the single existing canonical predicate, `shared.infrastructure.intent.rule_registry.rule_requires_enforcement_mapping`, which already excludes advisory-tier rules (`ADVISORY_ENFORCEMENT = "advisory"`, `rule_registry.py:33,61`). No second interpretation is introduced anywhere in this decision.

**Naming:** the new `degraded_on` vocabulary word is `any_unmapped_mapping_required_rules`, not `any_unmapped_non_advisory_rules`. The governed concept is "requires an enforcement mapping" — `rule_requires_enforcement_mapping`'s own name and the concept D1 binds to. "Non-advisory" is that predicate's *current implementation detail* (today, the predicate happens to reduce to `enforcement != "advisory"`), not the concept itself. Naming the config vocabulary after the implementation detail would create a second description of the same governed idea that could silently drift from the predicate if its implementation ever changes for a reason unrelated to verdict semantics; naming it after the predicate's own name cannot drift, by construction.

### D1a — Verdict precedence is explicit, not incidental

`_determine_verdict` evaluates its DEGRADED preconditions (`any_crashed_rules`, `stats_error`, and this ADR's new `any_unmapped_mapping_required_rules`) before it evaluates `fail_severities` against findings, and `.intent/enforcement/config/audit_verdict.yaml`'s own header already states this as policy, not incidental code order: `degraded_on` preconditions "force DEGRADED regardless of finding severities." This ADR makes that precedence binding for the new precondition too, explicitly, so a future refactor cannot silently reorder the branches and change the outcome:

| `unmapped_rules` | Blocking (`BLOCK`-severity) finding | Verdict |
|---|---|---|
| `== 0` | yes | `FAIL` |
| `> 0` | no | `DEGRADED` |
| `> 0` | yes | **`DEGRADED`** — DEGRADED precedes FAIL; compliance is unknown, so it cannot be asserted as known-bad either |

The third row is the case a future implementation could get wrong if the new branch is ever moved after the FAIL check instead of alongside its DEGRADED siblings — it MUST be covered by a dedicated regression test (D3, item 4 below), not left to fall out of implementation order by accident.

### D2 — One paired, atomic change across governance and interpreter

This ADR authorizes, as a single coherent unit — not sequenced, not optional in part — the following three coordinated surfaces. None is meaningful without the other two; implementing any subset leaves the system either inert (interpreter changed, policy unchanged) or broken (policy changed, interpreter's closed vocabulary rejects it — see Context).

1. **`.intent/enforcement/config/audit_verdict.yaml`** — add `any_unmapped_mapping_required_rules` to `degraded_on`. This is the governed semantic decision; the YAML remains the authority over *whether* this precondition is active.

   Also authorized in this same item: correct the file's header comment, which currently reads *"Changing verdict semantics is a `.intent/` edit, not a `src/` edit."* This ADR is itself proof that statement is too absolute — D2 items 2 and 3 are `src/` edits this same governance decision requires. Replace it with wording equivalent to:

   > "Verdict semantics are governed here. Source code may change only as necessary to interpret and execute vocabulary authorized by this policy and its governing ADRs."

   This is **not** a change to `.intent/`'s authority — the YAML remains the sole source of *which* preconditions are active and what they mean; `src/` still cannot introduce or redefine a precondition on its own. It is a correction of an inaccurate self-description, distinguishing "governs the semantic decision" (stays exclusively `.intent/`) from "contains the machinery that executes what's been authorized" (necessarily `src/`, and only ever in service of a decision already made in `.intent/`).

2. **`src/shared/infrastructure/intent/audit_verdict.py`** — extend `_KNOWN_PRECONDITIONS` to include `"any_unmapped_mapping_required_rules"`, so the governed vocabulary word is recognized rather than rejected as unknown. This is machinery, not a semantic decision — it makes the interpreter capable of understanding a word the governance layer is now permitted to use.

3. **`src/mind/governance/auditor.py::ConstitutionalAuditor._determine_verdict`** — add:
   ```python
   if (
       "any_unmapped_mapping_required_rules" in policy["degraded_on"]
       and stats.get("unmapped_rules", 0) > 0
   ):
       return AuditVerdict.DEGRADED
   ```
   placed alongside the two existing early DEGRADED-precondition checks (`any_crashed_rules`, `stats_error`), before the FAIL-severity check. (Ordering relative to the FAIL check does not itself change correctness — DEGRADED and FAIL are independent early-return branches, not stacked conditions — but the new branch belongs textually with its siblings for readability and because all three preconditions share the same "instrument/coverage, not code correctness" character.)

The naming of the new `_KNOWN_PRECONDITIONS` entry and the `degraded_on` entry MUST be identical (`any_unmapped_mapping_required_rules`) — no renaming across the YAML/`src/` boundary, so a governor reading either surface sees the same vocabulary.

### D3 — Required regression tests

Implementation of D2 MUST include tests proving, at minimum:

1. A valid policy containing `any_unmapped_mapping_required_rules` in `degraded_on` loads successfully (does not hit `_error`).
2. `unmapped_rules == 0` does not degrade an otherwise-PASS audit.
3. `unmapped_rules > 0` (with the new precondition present in `degraded_on`) produces `DEGRADED`.
4. **`unmapped_rules > 0` together with a `BLOCK`-severity finding present (with the new precondition in `degraded_on`) produces `DEGRADED`, not `FAIL`** — the D1a precedence case. This test must construct findings that would trigger `FAIL` on their own, combine them with a nonzero `unmapped_rules`, and assert the result is `DEGRADED`. This is the regression guard against a future refactor moving the new branch after the FAIL-severity check.
5. The `DEGRADED` result in (3) and (4) is caused by the new precondition branch specifically — not by `policy.get("_error")` being true. (E.g., assert the policy dict loaded is not the error sentinel, or assert on a distinguishing log/return-path signal — the point is to catch a regression back into the exact trap this ADR closes.)
6. Advisory-tier rules remain excluded from `unmapped_rules` through the existing, unmodified `rule_requires_enforcement_mapping` predicate — a rule with `enforcement: advisory` and no mapping does not trigger this precondition.
7. Existing crash / `stats_error` / blocking-finding verdict behavior is unchanged (the 3 existing tests in `test_auditor___determine_verdict.py` continue to pass unmodified, plus this ADR's new cases are additive, not replacements).

Test the observable verdict contract (`_determine_verdict`'s return value and `load_audit_verdict_policy`'s success/error outcome) rather than duplicating `rule_requires_enforcement_mapping`'s or `_find_unmapped_rule_ids`'s internals, which are already covered elsewhere and are not the subject of this change.

### D4 — Terminology correction: `AuditVerdict.PASS` docstring

The current docstring clause "No unmapped blocking rules" is imprecise: the governing concept is not severity-based ("blocking"), it is `rule_requires_enforcement_mapping`'s mapping-required/non-advisory predicate. Implementation of D2 MUST also correct `auditor.py:41`'s docstring (and the parallel DEGRADED-clause docstring at line 43-45, which already says "or are unmapped" correctly but should be checked for consistency) to name the actual predicate — e.g., "No unmapped rules that require an enforcement mapping (see `rule_requires_enforcement_mapping`)" — rather than inventing or implying a "blocking severity" concept that does not govern this behavior anywhere in the codebase.

---

## Explicit non-scope

This ADR does **not** authorize, and implementation must not drift into:

- Any change to `.intent/enforcement/remediation/auto_remediation.yaml` or ADR-066's remediation-dispatch mapping surface.
- Any general redesign of `AuditVerdict` or `_determine_verdict` beyond the single new precondition specified in D2.
- Any refactor of rule-counting/accounting logic (`get_dynamic_execution_stats`, `_find_unmapped_rule_ids`, `_mapping_required_rule_ids`) — these are correct today and untouched.
- The unrelated `rule_extractor.py:266-271` log line ("Found %d declared-only rules (no enforcement mappings)"), which does not exclude advisory rules the way `unmapped_rules` does and is cosmetic diagnostic output only — not consumed by `_determine_verdict`, not part of this decision. It may be recorded as a minor follow-up issue if the governor judges it worth fixing, but it is out of scope here specifically so a narrow verdict fix does not grow sideways.
- Any change to advisory-rule semantics or the definition of `ADVISORY_ENFORCEMENT`.
- Restoring, reinterpreting, or migrating any archived policy semantics (unrelated to this ADR's subject; noted only for consistency with this session's other work).

---

## Consequences

### Positive

- Closes the gap between `AuditVerdict.PASS`'s documented contract and `_determine_verdict`'s actual behavior — the third clause of the docstring becomes true.
- Reuses the single existing canonical predicate (`rule_requires_enforcement_mapping`) rather than introducing a third interpretation of "mapping-required"/"non-advisory"/"blocking" alongside the two that already exist for adjacent concepts (this predicate itself, and ADR-066's separate remediation-mapping check).
- Names and closes, in the same change, a specific implementation trap (`_KNOWN_PRECONDITIONS` closed-vocabulary rejection masquerading as correct DEGRADED behavior) that a narrower, YAML-only reading of #822 would have walked into silently — the audit would have appeared to work while actually failing closed for the wrong reason.
- Gives the governor a live, verifiable safety net: if a future rule is added to `.intent/rules/` without a corresponding entry in `.intent/enforcement/mappings/`, the audit now surfaces that as DEGRADED instead of silently reporting PASS.
- Makes DEGRADED-over-FAIL precedence explicit and test-guarded (D1a) rather than an accident of current branch order, closing a specific future-refactor risk this ADR itself would otherwise have introduced.
- Corrects `audit_verdict.yaml`'s header from an absolute "no `src/` edit" claim this ADR disproves to an accurate distinction between semantic authority (`.intent/`, unchanged) and interpreter machinery (`src/`, evolves only in service of an authorized decision) — future readers of that file no longer have to discover the exception the hard way.

### Negative

- Adds one more early-return branch to `_determine_verdict`, marginally increasing the function's branching complexity (three DEGRADED preconditions instead of two).
- If a rule is added and its mapping is added in a separate commit (a legitimate two-step workflow), the intervening audit run(s) will report DEGRADED rather than PASS — this is intentional (compliance genuinely is unknown in that window) but is a behavior change operators should expect after this ships.

### Neutral

- No change to `FAIL`-triggering behavior, `fail_severities`, or `ignored_finding_types`.
- No change to ADR-066's remediation-dispatch mapping surface.
- No change to `rule_requires_enforcement_mapping` itself or to advisory-rule handling.
- The `rule_extractor.py` cosmetic log-line inconsistency (non-advisory-excluding "declared-only rules" message) remains, unaddressed by this ADR, and may look superficially inconsistent with a clean `unmapped_rules: 0` stat to a log reader — noted here so it isn't mistaken for a defect in this ADR's implementation if observed later.

---

## Verification

Diagnostic evidence gathered before drafting (read-only; no implementation performed under this ADR yet — it authorizes future implementation, listed as required tests in D3):

- `AuditVerdict.PASS` docstring and `_determine_verdict`'s exact current logic confirmed by direct read of `auditor.py:41` and `auditor.py:137-179` on baseline `17ec2a42`.
- `unmapped_rules` computation chain confirmed real and wired exactly as this ADR describes: `rule_requires_enforcement_mapping` (`rule_registry.py:39-61`) → `_mapping_required_rule_ids` → `_find_unmapped_rule_ids` → `get_dynamic_execution_stats` (`constitutional_auditor_dynamic.py:334-336`).
- Live run against this repository's actual `.intent/` on `17ec2a42`: `unmapped_rules: 0`, `mapping_required_rules: 239`, `total_declared_rules: 256`, `crashed_rules: 0` — defect confirmed latent, not live.
- `git log 0ff9a99e..HEAD` on `auditor.py`, `audit_verdict.yaml`, `audit_verdict.py`, `rule_registry.py`: zero commits — issue #822's technical claims confirmed current, no drift.
- `_KNOWN_PRECONDITIONS` closed-vocabulary trap confirmed by direct read of `audit_verdict.py:42,82-88` — the mechanism that would reject a YAML-only implementation of #822's literal proposed resolution.
- `tests/mind/governance/test_auditor___determine_verdict.py` confirmed to hold exactly 3 tests, none exercising `unmapped_rules` — gap confirmed untested as well as unimplemented.
- ADR-066 read in full; confirmed it governs `auto_remediation.yaml` remediation-dispatch mapping, a different surface from this ADR's `enforcement/mappings/**` engine-dispatch mapping — no overlap, no conflict.

Verification required at implementation time (not yet performed, no code changed under this ADR): the seven tests specified in D3 (including the D1a precedence case), plus `ruff`/`mypy` clean on the three touched files, plus a live confirmation that `core-admin`'s audit path still returns `PASS` on this repository's current clean `unmapped_rules: 0` state after the change (regression check that D2 doesn't flip a currently-clean repo to DEGRADED).

---

## References

- #822 — the originating issue; this ADR's Decision section corrects and formalizes its "Proposed resolution," which was YAML-only and would have triggered the `_KNOWN_PRECONDITIONS` trap.
- #820 Group B — where the underlying gap was first surfaced; the governor directed recording it separately (#822) rather than folding a verdict-semantics change into the accounting-predicate commit.
- Commit `0ff9a99e` — made `rule_requires_enforcement_mapping` canonical and advisory-excluding; this ADR's D1 binds to that predicate without reinterpretation.
- ADR-005 (`.specs/decisions/ADR-005-govern-audit-verdict-policy.md`) — establishes `.intent/enforcement/config/audit_verdict.yaml` as the governance authority over verdict semantics and the fail-closed-on-missing-policy discipline this ADR's D2 explicitly avoids undermining.
- ADR-066 (`.specs/decisions/ADR-066-unmapped-rules-invariant.md`) — the adjacent, non-overlapping remediation-dispatch "unmapped" surface; disambiguated in Context, untouched by this ADR.
