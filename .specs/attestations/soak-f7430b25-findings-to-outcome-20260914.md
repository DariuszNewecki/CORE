# Soak f7430b25 — findings-to-outcome analysis

Investigative, read-only. Prepared 2026-09-14 from recorded state in the `core` database.
Reproduced 2026-09-14 by a second, independent session against the same database: the §4
query returns findings_in_window = 16,445 · linked_to_proposal = 0 · in_consequence_log = 0,
and the two corroborating counts return 0 and 0. Figures unchanged.

Window: 2026-07-23 09:17:45 CEST → 2026-07-26 09:17:45 CEST
Baseline commit: f7430b25
Companion to: .specs/attestations/soak-closure-f7430b25-20260726.md

## Verdict: A. DERIVABLE — 0 of 16,445

No finding recorded in the soak window progressed through the consequence chain
(finding → proposal → execution → consequence record). Cross-confirmed on three
independent tables.

## 1. The attestation report

`.specs/attestations/soak-closure-f7430b25-20260726.md` states no findings-to-outcome
figure. §3 counts entries by type only (68,495 total / 26,383 heartbeats / 24,975 reports /
16,637 findings). Nothing in it links findings to proposals, consequences, or resolutions.

Side note: the heartbeat total row says 26,383 but its own per-day column sums to 26,883 —
an arithmetic slip in the report.

## 2. Schema — the link exists, in three places

`core.blackboard_entries` has no FK to proposals. The linkage is:

| Link | Field | Written by |
|---|---|---|
| finding → proposal | `blackboard_entries.payload->>'proposal_id'` (+ `status='deferred_to_proposal'`) | `BlackboardProposalService.defer_entries_to_proposal` |
| proposal → resolved findings | `proposal_consequences.findings_resolved` (jsonb array of entry ids), sourced from `autonomous_proposals.constitutional_constraints['finding_ids']` | `proposal_execution_pipeline.record_consequence` |
| terminal outcome | `blackboard_entries.status` ∈ {resolved, abandoned, deferred_to_proposal, dry_run_complete, indeterminate, suppressed} (`.intent/META/enums.json` → `blackboard_entry_status`), with `resolved_at` | various |

`BlackboardProposalService.resolve_deferred_entries_for_completed_proposal` closes the loop:
`deferred_to_proposal` → `resolved` `WHERE payload->>'proposal_id' = :proposal_id`.

## 3. Data presence

Present. `core.blackboard_entries` holds 2,241,026 rows spanning 2026-05-10 → 2026-09-14
(full restore from the 2026-09-13 rebuild). Reports (24,975), heartbeats (26,883) and
findings for 07-23 / 07-24 / 07-25 (3,389 / 5,475 / 5,474) reproduce the attestation exactly.

One discrepancy: findings on the 07-26 partial day are 2,107 now vs 2,299 in the report —
192 rows short (1.2% of the denominator). Not explained: no window ceiling reproduces all
three type-counts at once, and the only hard-delete path
(`BlackboardShopManager` keep-last-100 sweep on `loop_hold.sample::*` telemetry findings)
would have hit days 23–25 too, which are intact. The denominator is therefore 16,445 as the
data stands today, with 192 rows of unknown provenance at attestation time. This does not
affect the numerator, which is 0 under every reading.

## 4. Query and result

```sql
SELECT
  count(*)                                                        AS findings_in_window,
  count(*) FILTER (WHERE status IN ('resolved','abandoned','deferred_to_proposal',
                                    'dry_run_complete','indeterminate','suppressed')) AS terminal_any,
  count(*) FILTER (WHERE payload ? 'proposal_id')                 AS linked_to_proposal,
  count(*) FILTER (WHERE EXISTS (
      SELECT 1 FROM core.proposal_consequences pc
      WHERE pc.findings_resolved @> to_jsonb(b.id::text)))        AS in_consequence_log
FROM core.blackboard_entries b
WHERE entry_type = 'finding'
  AND created_at >= '2026-07-23 09:17:45+02'
  AND created_at <  '2026-07-26 09:17:45+02';
```

Result: findings_in_window = 16,445 · terminal_any = 16,445 · linked_to_proposal = 0 ·
in_consequence_log = 0

Corroboration from the proposal side:

```sql
SELECT count(*) FROM core.autonomous_proposals
 WHERE created_at >= '2026-07-23 09:17:45+02' AND created_at < '2026-07-26 09:17:45+02';
-- 0   (last proposal before window: 2026-07-20 20:59 UTC; first after: 2026-07-26 15:03 UTC)

SELECT count(*) FROM core.proposal_consequences
 WHERE recorded_at >= '2026-07-23 09:17:45+02' AND recorded_at < '2026-07-26 09:17:45+02';
-- 0
```

## 5. What the 16,445 findings were — why the chain never engaged

| Subject | Status / mechanism | n | Nature |
|---|---|---:|---|
| `test.coverage.complete::*` | resolved / human | 8,636 | Posted already-resolved (<5 s); informational |
| `python::*` | resolved / reaudit | 3,456 | Cleared by the audit sensor; 95% within 5 s |
| `blackboard.remediation_cap_reached::*` | abandoned / human | 2,165 | Posted already-abandoned; cap notices |
| `python::test.runner.missing::*` | abandoned / reaudit | 2,160 | The only actionable ones. All 2,160 claimed by `TestRemediatorWorker`; all carried inherited `remediation_attempt_count = 3` → file-level circuit breaker (`remediation_cap_n: 3`, `.intent/enforcement/config/operational_config.yaml`) abandoned them before any proposal was created |
| misc (`worker.silent`, `entry_stale`, `coherence.repo_artifacts.drift`) | resolved / self_resolve, human | 28 | Housekeeping |

Sample abandoned payload:

```
python::test.runner.missing::src/will/workers/coherence_sensor.py
{"test_file": "tests/will/workers/coherence_sensor/test_generated.py",
 "source_file": "src/will/workers/coherence_sensor.py",
 "remediation_attempt_count": 3}
resolved_at - created_at = 00:00:28
```

## 6. Reading

100% of window findings reached a terminal *status*; 0% reached a terminal *outcome via the
consequence chain*. The fleet spent 72 h re-detecting the same cap-exhausted subjects and
re-abandoning them. The G4 soak proved loop continuity; the recorded state shows it did not
exercise the proposal → execution → consequence path at all.

## Appendix — supporting queries run

```sql
-- per-type counts in window
SELECT entry_type, count(*) FROM core.blackboard_entries
 WHERE created_at >= '2026-07-23 09:17:45+02' AND created_at < '2026-07-26 09:17:45+02'
 GROUP BY 1;
-- finding 16445 | heartbeat 26883 | report 24975

-- per-day findings (CEST)
SELECT (created_at AT TIME ZONE 'Europe/Warsaw')::date, count(*) FROM core.blackboard_entries
 WHERE entry_type='finding' AND created_at >= '2026-07-23 09:17:45+02'
   AND created_at < '2026-07-26 09:17:45+02' GROUP BY 1 ORDER BY 1;
-- 07-23 3389 | 07-24 5475 | 07-25 5474 | 07-26 2107

-- status / mechanism / proposal-link breakdown
SELECT status, resolution_mechanism, count(*),
       count(*) FILTER (WHERE resolved_at < '2026-07-26 09:17:45+02') AS resolved_in_window,
       count(*) FILTER (WHERE payload ? 'proposal_id') AS has_proposal_id,
       count(*) FILTER (WHERE occurrence_count > 1) AS dedup_hits
  FROM core.blackboard_entries
 WHERE entry_type='finding' AND created_at >= '2026-07-23 09:17:45+02'
   AND created_at < '2026-07-26 09:17:45+02'
 GROUP BY 1,2 ORDER BY 3 DESC;
-- resolved/human 8637 (8636 in window, 0 proposal_id, 1 dedup)
-- resolved/reaudit 3456 | abandoned/human 2165 | abandoned/reaudit 2160 | resolved/self_resolve 27

-- posted-terminal vs transitioned, claim and cap markers
SELECT regexp_replace(subject, '::.*$', '::*'), status,
       count(*) FILTER (WHERE resolved_at - created_at < interval '5 seconds') AS terminal_within_5s,
       count(*) FILTER (WHERE resolved_at - created_at >= interval '5 seconds') AS transitioned_later,
       count(*) FILTER (WHERE claimed_by IS NOT NULL) AS ever_claimed,
       count(*) FILTER (WHERE (payload->>'remediation_attempt_count')::int >= 3) AS cap_hit
  FROM core.blackboard_entries
 WHERE entry_type='finding' AND created_at >= '2026-07-23 09:17:45+02'
   AND created_at < '2026-07-26 09:17:45+02'
 GROUP BY 1,2 ORDER BY 3 DESC;
```
