# CCC Backlog Cleanup — 2026-05-31

Status: diagnosis + decision record + closure note. Not doctrine. The
deferred cleanup ran end-to-end 2026-05-31 — see **Closure** at bottom.
Original diagnosis preserved as the historical record of why the cleanup
was deferred in the first place.

This record lives in `.specs/planning/` rather than as a GitHub issue, by
governor decision (no new issues for this work). It is the tracking home so
the deferred generator-dedup fix is not parked silently. The tooling gap
itself is tracked by #496 (expanded).

---

## Why this exists

The audit footer reported 3345 unreviewed CCC candidates, regrown from a clean
state after the 2026-05-26 backlog clearance. This document records the
diagnosis, the cleanup decision (defer until governed cleanup verbs land), and
the substantive generator fix that is ADR-shaped and owned by a future session.

---

## Diagnosis (verified 2026-05-31, live DB)

The headline 3345 decomposes into three parts:

- **~154 rows — denormalized-count drift.** `coherence_runs.unreviewed_count`
  lags partial-triage decrements (ADR-067's documented failure mode; the
  `repair-counts` revisit-trigger, tracked by #496). Largest single gap: run
  `4a48c1d3` reports 941 but holds 790 true unreviewed. Cosmetic; ~5% of the
  headline.
- **~1395 rows — cross-run re-emission.** Four full-corpus runs are open
  simultaneously, all opened after the 2026-05-26 clear. 465 `(documents,
  claim)` identities appear in all four. Triage state is honored across runs
  (only 2 cases of dismissed/confirmed re-emerging as unreviewed); identity is
  not — each run re-emits the same claims without consulting prior open runs.
- **~1796 rows — unique unreviewed claims.** The genuine backlog floor.
  Concentrated in the two largest check classes: ROW3_CITATION (1460) and
  SAMECONCERN (1383) together are 89% of unreviewed — the surface that grew
  through ADR-073/077/079, the topology paper, and the
  capability-scoped-FS-authority paper.

Open runs (all post-clear):

| run | opened | candidates | true unreviewed |
|---|---|---|---|
| 4a48c1d3 | 2026-05-26 20:42 | 941 | 790 |
| 899aa91a | 2026-05-27 08:34 | 807 | 805 |
| f264894e | 2026-05-27 11:29 | 812 | 811 |
| 408f7c5d | 2026-05-27 18:58 | 785 | 785 |

All ten pre-2026-05-26 runs are closed with unreviewed=0. The ADR-073 redesign
hygiene held; the regrowth is entirely post-clear, from issuing parallel
`--full` runs without closing the prior open run between them.

Hypothesis outcome: count-drift partially true (~5%, cosmetic);
one-large-legit-run false; stale-pre-073-runs false; cross-run re-emission true
and dominant. The system inflated its own backlog ~4× over the real floor.

If/when cleanup runs via governed verbs, the supersession identity is:
`408f7c5d` (latest full scan) is canonical; `4a48c1d3`, `899aa91a`,
`f264894e` are superseded. Expected result: 3345 → 785.

---

## Decision — defer cleanup until governed verbs land

The reset is **not executed this session**. CORE's core posture is "do not
bypass the governed loop," and CCC is the convergence-debt detector itself —
the uniquely wrong surface to bypass. A one-time direct-DB cleanup would also
template the bypass for the next regrowth, which is structurally guaranteed
absent the dedup fix.

Cleanup defers to whenever **#496 (expanded)** ships, providing two governed
verbs:

- `coherence repair-counts` — original ADR-067 revisit prescription; recomputes
  denormalized counts from the candidates table.
- `coherence supersede <old_run_id> --by <canonical_run_id> --note "..."` —
  bulk-dismiss the older run's remaining unreviewed candidates with the
  supplied note, close the run, repair the canonical run's count. Mandatory
  `--note` records the supersession honestly.

The 3345 sits honestly in the audit footer until those verbs land. It IS the
honest number absent governed cleanup; it stays visible to the governor.

---

## Mechanism — when cleanup runs through #496-expanded

Through the governed verbs (after #496 ships), the cleanup is:

1. `coherence supersede 4a48c1d3 --by 408f7c5d --note "superseded by canonical full run 408f7c5d (cleanup 2026-05-31)"`
2. `coherence supersede 899aa91a --by 408f7c5d --note "superseded by canonical full run 408f7c5d (cleanup 2026-05-31)"`
3. `coherence supersede f264894e --by 408f7c5d --note "superseded by canonical full run 408f7c5d (cleanup 2026-05-31)"`
4. `coherence repair-counts` (idempotent; reconciles any remaining denormalized lag)

Result: 3345 → 785 via three governed operations, fully audit-trailed in
`triage_note`. No bypass; supersession is recorded as such on every dismissed
candidate.

---

## Deferred substantive fix (does not ship in the cleanup)

The cleanup-via-supersede does not fix the generator. Without a dedup
mechanism, the next parallel `--full` regrows the backlog — exactly as the
2026-05-26 clear did. The substantive fix is ADR-shaped and owned by a
dedicated session.

Working title: **"Cross-run dedup at candidate generation — bound CCC backlog
regrowth."**

Design candidates the ADR weighs:

- **(a) Identity-keyed UPSERT** — `identity = hash(documents, claim, relation)`,
  `INSERT … ON CONFLICT DO NOTHING` (or update `last_seen_run_id`). Triage state
  attaches to identity, not row; re-runs do not multiply.
- **(b) Consult-before-emit** — generator skips identities already present in
  open runs. Simpler; races between concurrent runs.
- **(c) Single-live-run discipline** — at most one open run; a new `--full`
  appends to or blocks on the live run. Strongest invariant; biggest
  operational constraint.

The generator is LLM-driven and non-deterministic — successive `--full` runs
surface partly different claims (the ~1331 single-run-only rows in this
population). Dedup bounds exact re-emission but not generative variance; the
ADR must address both.

This document is the home for the dedup design context until the ADR is
authored. No GitHub issue is filed for this work by governor decision;
re-derivation in a future session starts from this record.

---

## Operational discipline until both fixes land

**Single live run.** Do not issue a new `--full` while a CCC run is open. This
is the manual stand-in for candidate (c), and the only thing preventing
recurrence between now and the dedup ADR. The 2026-05-26 clear failed precisely
because this discipline was not held.

This discipline matters more now, not less, because the 3345 is sitting
visible until #496-expanded lands — a new `--full` issued during that interval
compounds the inflation against the deferred cleanup.

---

## Tracking

- **Tooling gap** (missing governed verbs `repair-counts` + `supersede`) →
  tracked by **#496 (expanded)** — body now covers both verbs, sharing the
  same architectural gap.
- **Generator dedup design** → this document. No GitHub issue per governor
  decision; the future ADR session re-derives from here.
- **2026-05-26 clearance memory** → annotated: the clear did not survive the
  post-clear run cadence; the system regenerated through the absence of
  cross-run dedup.

---

## Closure — 2026-05-31

The deferred cleanup ran end-to-end after #496 shipped (commit
`b25681a0`). Mechanism executed exactly as written in the "Mechanism"
section above:

```
$ coherence supersede 4a48c1d3-5b1c-4231-9de2-755aa730987b --by 408f7c5d-… --note "…"
$ coherence supersede 899aa91a-f56d-4868-a1ce-ae8c7d3a08d0 --by 408f7c5d-… --note "…"
$ coherence supersede f264894e-780f-4134-be53-66039a514023 --by 408f7c5d-… --note "…"
$ coherence repair-counts
```

Result on the live DB:

| run | pre-cleanup unreviewed | post-cleanup |
|---|---|---|
| 4a48c1d3 | 790 | 0 (closed) |
| 899aa91a | 805 | 0 (closed) |
| f264894e | 811 | 0 (closed) |
| 408f7c5d (canonical) | 785 | 785 (open) |

Headline: **3345 → 785** (the 76% drop predicted in "Diagnosis"). The
intermediate repair-counts step corrected an additional 154 rows of
denormalized drift before the supersedes (planning doc estimate: ~154
rows; exact match). Every dismissed candidate carries the `triage_note`
"superseded by canonical full run 408f7c5d (cleanup 2026-05-31)" — 2406
rows total, fully auditable through ordinary triage history. No bypass.

### What this closure does NOT discharge

1. **Generator dedup design.** Still ADR-shaped and unimplemented. The
   next parallel `--full` will re-inflate the backlog against 408f7c5d
   exactly as the 2026-05-26 clear was re-inflated. The "Deferred
   substantive fix" section above remains the home for this work.
2. **Single-live-run discipline.** Still required by hand until the
   generator dedup ADR lands. The new floor (785 on 408f7c5d) replaces
   the old "clean" reference point.
3. **Misleading `DRY RUN MODE` banner.** Filed as **#504** during
   verification — pre-existing CLI decorator ergonomics issue, not a
   #496 regression. Both new verbs print the banner but mutate
   regardless; behavior matches existing `coherence triage`.

### Tracking — final

- **#496** — closed by `b25681a0` (cleanup verbs landed).
- **#504** — opened during verification; CLI decorator banner cleanup.
- **Generator dedup ADR** — unowned; design candidates above remain the
  starting context.
