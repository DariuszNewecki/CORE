# ADR-006: Align `modularity.needs_split` implementation with its statement

**Status:** Accepted
**Date:** 2026-04-20
**Authors:** Darek (Dariusz Newecki)
**Related:** ADR-005 (audit verdict governance)
**Reconnaissance:** `.specs/state/2026-04-20-modularity-needs-split-diagnostic.md`

## Context

The `modularity.needs_split` rule in `.intent/rules/code/modularity.json`
states:

> A source file that exceeds the line limit AND contains a single coherent
> responsibility SHOULD be split into smaller files along natural seams.
> The logic must be preserved exactly — splitting is mechanical
> redistribution, not refactoring.

The check method `ModularityChecker.check_needs_split` emits a finding
when `loc > max_lines` and `len(_identify_concerns(imports)) <= 2`.
`_identify_concerns` is a substring-match classifier over six external
domain buckets (`database`, `web`, `testing`, `ml`, `cli`, `file_io`).

The 2026-04-20 diagnostic established that the statement and the
implementation measure different things. The statement names "single
coherent responsibility." The implementation measures "narrow external
domain-library exposure." For any file whose responsibilities are
expressed through internal modules or stdlib, the proxy collapses and
the rule degenerates to "file has more than 400 lines."

Evidence from the 2026-04-20 audit (32 `modularity.needs_split`
findings, WARNING severity):

- 21 of 32 findings (65.6%) are CLASSIFIER-BLIND: `_identify_concerns`
  returns ≤2 buckets while the sibling `_detect_responsibilities`
  classifier — content-based pattern matching used by the same class's
  `check_refactor_score` method — returns ≥3. The file contains
  multiple responsibilities; the import-based classifier cannot see
  them.
- 0 of 32 findings show both classifiers agreeing on coherence.

The gap is structural, not statistical. It follows from the deliberate
narrowness of `IMPORT_CONCERNS` (which excludes infrastructure
primitives and internal modules by design — correct for the coupling
term in `check_refactor_score`, wrong for the coherence question in
`check_needs_split`).

## Decision

The rule statement is governance law. The implementation is mechanism.
When they disagree, the mechanism is corrected to match the statement,
not the other way around.

Replace `_identify_concerns(imports)` with `_detect_responsibilities(
content)` inside `check_needs_split`. The threshold semantics stay
the same — fire when the count is ≤ 2. Everything else in the check
(line-limit gate, finding shape, severity) is unchanged. The finding's
`details` payload replaces `concern_count` / `concerns` with
`responsibility_count` / `responsibilities` so consumers of the
finding see the signal that actually drove it.

`_identify_concerns` remains untouched and continues to serve
`check_refactor_score` (as the coupling term) and `check_needs_refactor`
(as the multi-discipline gate). This is deliberate: those two callers
measure external coupling, which is what `_identify_concerns` actually
computes. Only `check_needs_split` was calling it under the wrong name.

## Alternatives Considered

**Retire `modularity.needs_split` entirely.** Rejected. The rule
statement describes a distinct governance concern — files that are
oversized AND internally coherent, to be split mechanically without
discipline-boundary decisions. `modularity.needs_refactor` catches the
opposite failure mode (mixed disciplines); `modularity.refactor_score_threshold`
is a continuous score that does not produce a binary split candidate.
Retiring `needs_split` leaves the "coherent-but-too-long" case without
a dedicated reporting signal.

**Widen `IMPORT_CONCERNS` to include internal module prefixes.**
Rejected. The `IMPORT_CONCERNS` docstring explicitly argues for
excluding internal and infrastructure imports, and widening would
change behaviour of `check_refactor_score` and `check_needs_refactor`
too — a much larger blast radius to solve a problem localized to one
caller. The minimum-risk fix is at the caller, not the classifier.

**Rewrite the rule statement to match the current implementation.**
Rejected. The statement is load-bearing elsewhere — the `fix.modularity`
remediation action, the Prior Art whitepaper's §4 claim, and the
`modularity.json` rationale all cite "coherent responsibility." The
honest revision would propagate into every one of those. More
fundamentally: "narrow external-domain exposure" is not a governance
criterion anyone would choose if authoring the rule today. The
statement is the defensible description; the implementation was the
shortcut.

## §3 — On the calibration of `_detect_responsibilities`

The diagnostic's §8 item 1 flags that `_detect_responsibilities` has
not been validated against a labelled golden set. This ADR proceeds
without that validation for three reasons:

1. The counterfactual scan is strictly narrowing against the current
   codebase: 21 findings drop, 11 remain, 0 new flags. Replacement
   cannot introduce false positives relative to today's state.
2. `modularity.needs_split` is a WARNING rule under ADR-005's verdict
   policy. WARNING findings do not fail audits; the operational cost
   of a miscalibrated reporting signal is bounded.
3. `_detect_responsibilities` is already the responsibility signal
   inside `check_refactor_score`. This ADR does not introduce a new
   instrument — it makes one caller consult an instrument already in
   use by its siblings.

A future ADR is warranted if `_detect_responsibilities` is promoted to
feed a blocking-tier rule, or if operational evidence shows it
systematically misclassifies. Instrument qualification at that point
means a labelled golden set and a confusion matrix. Not today.

## §4 — Interaction with `fix.modularity` autonomous remediation

`modularity.needs_split` is mapped to the `fix.modularity` action in
`.intent/enforcement/remediation/auto_remediation.yaml` at Tier 2
ACTIVE, confidence 0.85, risk=high. Under the pre-retrofit
implementation the remediator received findings whose input premise
("single coherent responsibility") was false for ~65% of cases; those
CLASSIFIER-BLIND findings drop under the retrofit.

Post-retrofit, the remediator receives findings grounded in the
responsibility classifier. This improves — but does not fully resolve
— the autonomy mismatch. The diagnostic's §6 critique of DOMINANT-CLASS
findings survives and now applies to the 11 findings that remain
flagged: 6 of the 11 are DOMINANT-CLASS, and file-level splitting a
dominant-class file crosses a discipline boundary that the rule's
rationale explicitly disclaims.

This ADR does not address that mismatch. The Logic Conservation Gate
validates behaviour preservation, not responsibility-seam fidelity,
and evaluating intra-class structure requires tooling the checker
does not currently have. A follow-up ADR is warranted for either:
(a) a class-structure signal that gates `fix.modularity` on
DOMINANT-CLASS findings, or (b) a confidence downgrade on
DOMINANT-CLASS findings until the class-structure question is
resolved.

## Consequences

**Positive:**

- The rule statement and the rule implementation agree. Changing the
  statement becomes a meaningful governance action again.
- Reporting honesty improves: a `modularity.needs_split` finding now
  means what it says. Operators can trust the finding's premise when
  deciding whether to act on it.
- The 21 findings that drop under the retrofit are evidence the
  current ~32 figure overstates the codebase's actual split-candidate
  burden. A fresh audit after retrofit produces a smaller, truer
  number.
- The fix is minimal: one caller's classifier swap, no change to
  `_identify_concerns`, no change to other rules.

**Negative:**

- Finding shape changes. Any tooling that inspected
  `details.concern_count` / `details.concerns` on `needs_split`
  findings will need to inspect `details.responsibility_count` /
  `details.responsibilities` instead. Consumers known at ADR time:
  `fix.modularity` (reads the message, not the details), the audit
  report renderer (reads severity and message). No consumer reads
  the old fields programmatically based on a grep of `src/`; the
  schema change is low-risk but not zero.
- Post-retrofit count of `modularity.needs_split` findings drops
  from 32 to 11 in the same audit run. This is a measurement
  artefact of the fix, not a convergence event. The consequence log
  and any convergence-rate metric must not interpret it as
  autonomous remediation.

**Open follow-ups:**

- DOMINANT-CLASS autonomy gate — either a class-structure signal
  on `fix.modularity` or a confidence downgrade (see §4).
- Golden-set calibration of `_detect_responsibilities` if and when
  it feeds a blocking rule (see §3).
- Audit-run persistence of finding schema versions, so a
  `concerns`-to-`responsibilities` detail rename is distinguishable
  from a content change when bisecting historical audits.
