# G4 soak — pre-declaration (2026 Q4, first run)

**Status:** committed 2026-09-21 on the governor's Path A instruction, before T0; §0's SHA and T0 are filled by the governor at the moment the clock starts, from `origin/main` at that moment. Signature is the governor's, at §0.

Gate: `.specs/requirements/URS-production-readiness.md#g4` — "Workers run against a
non-trivial repository for ≥ 72 hours without silent stalls, duplicate proposals, stuck
drafts, zombie leases, or unclaimed failures." Manifest gap (2026-09-14): the f7430b25 soak
proved continuity only — 0 of 16,445 findings reached a consequence. "A qualifying soak
needs a pre-declared throughput condition … recorded before it starts." This is that record.
Nothing below is measured yet; every number is a bar, not a result.

## 0. Identity

| | |
|---|---|
| subject repository | CORE itself, `/opt/dev/CORE`, live `core` DB (as f7430b25) |
| baseline commit | **the commit carrying this signature** — its own sha; recorded in the closure attestation after T1 (a commit cannot contain its own hash). Verified at T0: `git diff f9b7dd12 <sha> -- src/` is empty, so the daemon's running code is byte-identical to `e94fba69`'s `src/`; `origin/main` == that commit; CI green; **≥ `efe83c77`** (T-A and C2 cite ADR-104 D10, which does not exist below it) |
| T0 | **the committer timestamp of the commit carrying this signature**, recoverable with `git show -s --format=%cI <sha>` — fixed at commit, so the mark cannot drift; do not amend or rebase that commit (it would move T0 and the baseline together) |
| T1 | T0 + 72 h; measurement window is `[T0, T1)` on `created_at` / `recorded_at` |
| measured at | T1 + 30 min grace (lets in-flight proposals reach a terminal state) |
| measured by | Claude Code, read-only queries in §5; a second session reproduces the §5 numbers before signing, as on 2026-09-14 |
| signed by | governor — **the signature is the authorship of the commit carrying it**: the governor ran `git commit`, and the signing identity and moment are recoverable with `git show -s --format='%an <%ae> %cI' <sha>`. Same self-referential form as the baseline and T0 above, so nothing here can be typed on the governor's behalf. Result attestation: `.specs/attestations/soak-<sha>-g4-<date>.md` after T1 |
| audit baseline (P5) | artifact `var/reports/g4-t0-audit-baseline-20260922.json` · sha256 `9a310297380443f0bfb72b04223e02ef8f408a42cb4d3e40309bb524db001f99` · mode stateless (offline) — verdict DEGRADED by design, #907 · executed/findings/blocking **239 / 70 / 0** (all 70 severity `info`) · skipped blocking rules, offline-caused, from `stats.skipped_blocking_rule_ids`: `capability.taxonomy.roles_require_canonical_capabilities`, `capability.taxonomy.resources_provide_canonical_capabilities`, `runtime.worker_max_interval_within_observed` |
| heartbeat caveat | `runtime.worker_max_interval_within_observed` is skipped in stateless mode at **both** ends, so the T0↔T1 audit delta says nothing about heartbeat behaviour. C1/P4's live measurement and C9 are its only instruments; the audit must not be read as covering it. |

## 1. Pre-conditions — all true at T0, or the clock does not start

- P1 **Daemon on the baseline commit**, `core-admin daemon status` all units active, 0 boot
  errors. No push, no restart, no `.intent/` or `src/` change until T1.
- P2 **No orphaned deferrals.** 0 findings in `deferred_to_proposal` whose proposal is
  terminal (`completed` / `failed` / `rejected`) or missing. Today: 48 (37 rejected, 10
  failed, 1 completed; 2026-05-13 → 07-26), 6 of them live `style.formatter_required`
  violations blocked since a proposal failed on 07-26. Resolution is a governor call (§6.1);
  a soak that starts over them inherits ambiguous state on day 0.
- P3 **Pending proposals dispositioned.** 0 envelope-eligible (`fix.*` atomic action)
  proposals in `pending` at T0 — today's 2 (one `fix.logging` the safe-auto-approval envelope
  refused on 09-15, one `approval_required=True`) get a real approve/reject before the clock
  starts. **Flow proposals (test generation) are expected to be pending at T0 and to be
  created in-window**: they are never safe-auto-approved (#853 ruling 6), and rejecting them
  only re-creates them — the live reject path revives their findings without disposition
  (#920), the sensor re-detects, the test remediator re-proposes. Today's 18 are therefore
  left pending and declared here. They are **excluded from T-A only** (§2), listed with age
  in the report, and **still bound by C2 and C6**: more than `remediation_cap_n` proposals
  for one symbol in-window, or overlapping active proposals on one key, counts against the
  run. This exclusion holds **until #920 is settled** — once reject carries a disposition, a
  rejected flow proposal stays dead and the exclusion lapses; it is a dated gap, not a
  precedent for the next soak.
- P4 **Fleet quiet — measured from the declarations, not the worker table.** For every
  `.intent/workers/*.yaml` that is not `launch: on_demand`: a registry row exists AND its last
  heartbeat is within `max_interval + glide_off` at T0 (a never-registered worker is a stall, not
  an absence); every dedicated-process unit (`core-daemon-worker@*`) reports ≥ 1 hosted worker in
  its boot log (a declaration that fails schema validation boots to "0 worker(s) started" with the
  unit `active` — 2026-09-20 20:35Z, `quality_ingest_worker`, 95 min down); 0 open
  `worker.silent::*`.
- P5 **Audit baseline recorded.** `core-admin code audit --offline --format=json` at T0
  saved beside this file (today: 239 rules, 0 blocking, 71 info).

## 2. Throughput condition (the gap the last soak failed) — pre-declared

- T-A **≥ 1 finding posted in-window reaches a completed proposal with a real commit and a
  consequence record in-window** — `finding.created_at ∈ [T0,T1)`, proposal `completed`,
  `pre_execution_sha ≠ post_execution_sha`, `consequence_recorded_at ∈ [T0,T1)`, finding
  `resolved` with that `proposal_id`. The gate text says ≥ 1; the count is reported as
  measured. No-op completions (`NOTHING_TO_COMMIT`, ADR-104 D10) are reported separately and
  count zero.
- T-B **Honesty of the count.** The chain must originate from a sensor-posted finding in the
  window, not from a proposal created before T0 or by hand. **Flow (test-generation)
  proposals do not count toward T-A** (§6.2, P3): a governor-approved flow proposal is the
  least autonomous path in the system, and G4 is about the loop closing itself. If one is
  approved and executes in-window it is reported, not counted.
- T-C **Expected fuel, stated now so a zero is diagnosable:** today's audit shows 6 live
  `style.formatter_required` (→ `fix.format`) and 2 `logic_no_terminal_rendering`
  (→ `fix.logging`) findings, plus whatever the window's own drift produces. If P2 is
  resolved by revival, those 6 are in play from T0.

## 3. Continuity conditions (the gate's acceptance criteria, made measurable)

- C1 **No silent stalls.** For every declared, non-`on_demand` worker (from the YAMLs, as P4):
  the max gap between consecutive blackboard entries in-window ≤ its declared
  `max_interval + glide_off` (`WorkerShopManager`'s own threshold); **0 `worker.silent::*`
  findings *opened* in-window, whatever their status at T1** — the detector self-resolves when
  the heartbeat returns (2026-09-20: opened 20:47:50Z, resolved 22:13:31Z, outage invisible to
  a "still open at T1" count), and a stall that healed is still a stall; every dedicated-process
  unit hosts ≥ 1 worker throughout (no "0 worker(s) started" boot in-window).
- C2 **No runaway duplicates** (post-hoc, provable at T1 — no in-window sampling). For each
  `(ref_id, file_path)` key, the active intervals `[created_at, terminal_at)` of its proposals
  created in-window do not overlap (`terminal_at` = `execution_completed_at` for completed/
  failed, `updated_at` for rejected); and no single finding subject has more than
  `remediation_cap_n` (3) proposals created in-window (ADR-104 D9/D10 rails hold).
- C3 **No unauthorized writes.** Every commit on `main` in-window is either a proposal commit
  (matches a `proposal_consequences.post_execution_sha`) or governor-authored; 0
  `governance.commit_authorship_integrity` findings; 0 `RepositoryBoundaryViolationError`
  in daemon logs; working tree clean at T1 apart from proposal commits.
- C4 **All failures classified.** At T1 + grace: 0 proposals in `executing` or `finalizing`
  older than their reaper SLA; every `failed` proposal has a non-empty `failure_reason`; 0
  findings in `claimed` or `deferred_to_proposal` whose proposal is terminal (the P2
  condition, re-checked at T1); every finding posted in-window is in a terminal or
  quarantined status or is younger than one sensor cycle.
- C5 **Loop continuity** (what f7430b25 did prove): daemon `NRestarts=0` across the window;
  all units active at T1.
- C6 **No stuck pending** (the requirement's "stuck drafts"; `draft` was retired by #885 and
  `pending` is its active successor — a pending-forever proposal blocks re-creation of its
  `(ref_id, file_path)` group, a silent throughput sink). At T1 + grace: 0 `pending`
  proposals that are envelope-eligible (`fix.*` atomic actions) older than one remediator
  cycle; every other `pending` proposal (flow proposals, never safe-auto-approved by design —
  #853 ruling 6) is listed with its age and whether the governor dispositioned it in-window.
  Today's 18 test-gen proposals from 09-15 are exactly this sink and are handled by P3.
- C7 **No zombie leases** (in the mechanism that exists — ADR-104 D1–D3/D8; ADR-069 D2's
  `lease_expires_at` column was declared and never landed). At T1: 0 findings in `claimed`
  whose `claimed_by` is not an alive worker and whose `claimed_at` is older than
  `worker_alive_threshold_sec`; in-window, every orphaned claim the reaper handled is
  recorded — releases in `blackboard_shop_manager.run.complete` report payloads, abandons as
  `blackboard.claim_orphan_abandoned::<entry_id>` observations — within one reaper cycle of
  becoming orphaned; and 0 `blackboard.entry_stale::*` findings in-window whose target was a
  `claimed` row (the BlackboardShopManager's own SLA sweep is the "held too long" detector,
  so a claim a live worker sat on past the SLA surfaces there, not in a snapshot).
- C8 **No recurring error state** (the f7430b25 residual: `prompt_drift_sensor` threw the
  same traceback every 900 s for the full 72 h and still passed continuity, because a
  worker in a permanent error state posts entries on schedule). **Instrument, qualified
  2026-09-21:** journald priorities are real since `e94fba69` (sd-daemon prefix on every
  non-TTY line; canary ERROR returned by `journalctl -p err` at PRIORITY=3; WARNINGs at 4;
  `SyslogLevelPrefix=yes` read from the unit) — before that every entry was PRIORITY=6 and
  `-p err` returned nothing on any night, so this condition was vacuous as first drafted.
  **Definition, fixed now** (`var/tmp/c8_journal_signatures.py`, self-tested): an *error
  record* is a PRIORITY ≤ 3 journal entry from a CORE unit (`core-daemon`,
  `core-daemon-worker-*`, `core-api`) whose message is a record head
  (`<ISO-8601>Z ERROR|CRITICAL <logger>: …`); traceback lines attach to their head; the
  *signature* is the message canonicalised by ADR-038's own canonicaliser; the *worker* is
  the unit (plus logger inside the shared daemon unit); a *streak* is consecutive records
  with one (worker, signature) spaced ≤ 2 × that worker's declared `max_interval`.
  **Threshold: any streak longer than 3 is a breach.** Disposition of a breach is §6.5
  (residual, with the hard edge below).

- C9 **No undeclared LLM callers** (the 2026-09-20 finding: two `permitted_tools: []` workers
  made 99 % of all LLM spend ever logged, unnoticed for four months because the declaration
  looked right). Measured from `core.llm_exchange_log`, **grouped by `cognitive_role` and
  day**, so the T1 report distinguishes "always there" from "started during the freeze".
  Baseline: the per-role daily call counts for the 24 h ending at T0, taken *after* the ingest
  fix (e2ee4a6a → this commit) is live in the daemon — recorded in §5 at T0, not remembered.
  Pass: (a) no role appears in-window that had zero calls in the baseline day; (b) no role's
  in-window daily count exceeds 2 × its baseline; (c) `LocalCoder` in-window = 0 unless a
  worker that declares `llm.local` posted a report in the same hour. Any breach is listed
  with role, day, count and the workers whose `run.complete` reports bracket the calls.
  Known gap, declared now: `permitted_tools` `llm.*` keys are not bound to cognitive roles
  anywhere in `.intent/`, so the role→declaring-worker join is by hand
  (`llm.embedder`→`Vectorizer`; `llm.remote_coder`→`RemoteCoder`; `llm.architect`→`Architect`;
  `llm.local`→`LocalCoder`/`LocalReasoner`) — recorded as the vocabulary gap behind
  `architecture.workers.declared_tools_must_match_call_graph`.
  *Adopted 2026-09-21 (governor) from the peer session's draft, unchanged; a C9 breach is a
  continuity failure judged at signature like C8 (§6.5), not a void. Note recorded at adoption:
  since the 11:01Z restart the ledger shows zero LLM calls, so the T0 baseline will be
  near-empty and any in-window call is a named event to attribute.*

## 4. Disqualifiers — declared now, any one voids the run

- D1 A push to `main`, a daemon restart, or an edit to `.intent/`, `src/`, or the live DB by
  anyone during `[T0, T1)`. (Approving/rejecting proposals through the governed CLI is not
  an edit; it is the lifecycle.)
- D2 An operator "helping" a stuck chain (manual `blackboard resolve`, hand-run action).
- D3 A change to any measurement query in §5 after T0.
- D4 Measurement by the same session only — the §5 numbers must be reproduced by a second,
  independent session before the governor signs (2026-09-14 precedent).

## 5. Measurement queries — fixed now

```sql
-- T-A: in-window finding → completed proposal with a real commit → consequence, all in-window
SELECT count(DISTINCT b.id) AS chains
FROM core.blackboard_entries b
JOIN core.autonomous_proposals ap ON ap.proposal_id = b.payload->>'proposal_id'
JOIN core.proposal_consequences pc ON pc.proposal_id = ap.proposal_id
WHERE b.entry_type = 'finding' AND b.status = 'resolved'
  AND b.created_at >= :t0 AND b.created_at < :t1
  AND ap.status = 'completed'
  AND ap.consequence_recorded_at >= :t0 AND ap.consequence_recorded_at < :t1
  AND pc.pre_execution_sha IS DISTINCT FROM pc.post_execution_sha;

-- T-A companion: no-op completions in-window (reported, count zero)
SELECT count(*) FROM core.proposal_consequences pc
JOIN core.autonomous_proposals ap USING (proposal_id)
WHERE pc.recorded_at >= :t0 AND pc.recorded_at < :t1
  AND pc.pre_execution_sha = pc.post_execution_sha;

-- C1: max inter-entry gap per worker vs declared max_interval (join to the declaration
-- table exported at T0 from .intent/workers/*.yaml)
SELECT worker_uuid, max(gap) FROM (
  SELECT worker_uuid, extract(epoch FROM created_at - lag(created_at)
         OVER (PARTITION BY worker_uuid ORDER BY created_at)) AS gap
  FROM core.blackboard_entries WHERE created_at >= :t0 AND created_at < :t1) g
GROUP BY 1;

-- C2: duplicate active keys (must be 0 rows when sampled; sampled every sensor cycle)
SELECT a->>'action_id', a->'parameters'->>'file_path', count(*)
FROM core.autonomous_proposals ap, jsonb_array_elements(ap.actions) a
WHERE ap.status IN ('pending','approved','executing','finalizing')
GROUP BY 1,2 HAVING count(*) > 1;

-- C2 (post-hoc): overlapping active intervals per (ref_id, file_path), in-window creations
WITH p AS (
  SELECT ap.proposal_id, a->>'action_id' AS ref_id, a->'parameters'->>'file_path' AS fp,
         ap.created_at,
         CASE WHEN ap.status IN ('completed','failed') THEN ap.execution_completed_at
              WHEN ap.status = 'rejected' THEN ap.updated_at ELSE :t1 END AS terminal_at
  FROM core.autonomous_proposals ap, jsonb_array_elements(ap.actions) a
  WHERE ap.created_at >= :t0 AND ap.created_at < :t1)
SELECT x.ref_id, x.fp, x.proposal_id, y.proposal_id
FROM p x JOIN p y ON x.ref_id = y.ref_id AND x.fp IS NOT DISTINCT FROM y.fp
                 AND x.proposal_id < y.proposal_id
WHERE x.created_at < y.terminal_at AND y.created_at < x.terminal_at;   -- must be 0 rows

-- C6: envelope-eligible proposals stuck pending (must be 0); flow proposals listed with age
SELECT ap.proposal_id, ap.goal, now() - ap.created_at AS age,
       bool_or(a ? 'flow_id') AS is_flow
FROM core.autonomous_proposals ap, jsonb_array_elements(ap.actions) a
WHERE ap.status = 'pending' GROUP BY 1,2,3;

-- C7: claims held by a non-alive worker past grace (must be 0)
SELECT count(*) FROM core.blackboard_entries b
WHERE b.status = 'claimed' AND b.claimed_at < now() - make_interval(secs => :grace)
  AND b.claimed_by NOT IN (SELECT worker_uuid FROM core.worker_registry
                           WHERE last_heartbeat > now() - make_interval(secs => :grace));

-- C8: recurring journal error signatures — the script IS the procedure (fixed before T0):
--   .venv/bin/python var/tmp/c8_journal_signatures.py --since "<T0>" --until "<T1>"
--   (reads journalctl --user -p err -o json; CORE units only; canonicaliser = ADR-038's;
--    prints every (worker, signature) streak and the verdict; exit 1 on a breach).
--   Self-test that must pass before the run is read: --self-test.
--   §6.5 hard edge: for each breaching worker run the blackboard count above.

-- C9: LLM calls per role per day, in-window (compare against the T0 baseline row set)
SELECT cognitive_role,
       date_trunc('day', ts)::date            AS day,
       count(*)                                AS calls,
       sum(prompt_tokens + completion_tokens)  AS tokens,
       round(sum(cost_estimate), 4)            AS cost_usd
FROM core.llm_exchange_log
WHERE ts >= :t0 AND ts < :t1
GROUP BY 1, 2
ORDER BY 1, 2;

-- C9 baseline (run once at T0, paste the rows into §5 verbatim)
SELECT cognitive_role, count(*) AS calls
FROM core.llm_exchange_log
WHERE ts >= :t0 - interval '24 hours' AND ts < :t0
GROUP BY 1 ORDER BY 1;

-- C9 attribution helper for any breach: worker reports bracketing an hour
SELECT to_char(created_at, 'HH24:MI:SS') AS t, subject, worker_uuid
FROM core.blackboard_entries
WHERE entry_type = 'report' AND subject LIKE '%run.complete'
  AND created_at >= :hour_start AND created_at < :hour_start + interval '1 hour'
ORDER BY created_at;

-- C4 / P2: findings deferred to a terminal or missing proposal (must be 0)
SELECT count(*) FROM core.blackboard_entries b
LEFT JOIN core.autonomous_proposals ap ON ap.proposal_id = b.payload->>'proposal_id'
WHERE b.entry_type = 'finding' AND b.status = 'deferred_to_proposal'
  AND coalesce(ap.status, 'missing') IN ('completed','failed','rejected','missing');
```
(The f7430b25 §4 query is re-run verbatim for the denominator/terminal-status view.)

## 6. Decisions the governor makes before T0

*Rulings CONFIRMED by the governor 2026-09-20 (first-person), all five including the §6.5 edge: 6.1 → (b); 6.2 → amended 2026-09-20 evening: the 18 are LEFT PENDING and declared (rejecting re-creates them until #920), flow proposals out of T-A scope only, still bound by C2/C6; 6.3 →
hold at ≥ 1, report distinct subjects; 6.4 → T0 only after the 6.1(b) pass ships, on a day
`main` can be frozen for 72 h; 6.5 → reported residual, with one hard edge (below). Tracking: P2 pass = #918 (implemented `91bb043a`+`c788045b`); paper drift #919; reject-without-disposition #920.*


1. **P2 — the 48 orphaned deferrals.** Options: (a) a one-off governor-run reconciliation
   (revive the 6 live ones to `awaiting_reaudit`; resolve the 42 whose violation is gone),
   attested in the soak report; or (b) close the gap structurally first — a
   `ProposalPipelineShopManager` pass (ADR-148 D4 shape) that revives findings deferred to a
   terminal proposal — then the soak proves it. (b) is the honest one: the soak is meant to
   catch exactly this, and (a) hides it. Recommendation: (b), filed as an issue, shipped
   before T0.
2. **P3 — the 18 test-gen proposals.** Approve (they become in-window fuel only if they
   execute after T0), reject, or leave with an explicit note that flow proposals are
   out of scope for this soak.
3. **T-A bar.** ≥ 1 per the gate, or raise it (e.g. ≥ 3 distinct subjects) — a higher bar
   is a stronger claim but a fail on it is not a gate fail; the gate text is ≥ 1.
4. **Window.** 72 h exactly, or longer. Start on a day the governor can disposition
   proposals if needed (D1 allows it).
5. **C8 — recurring error state: disqualifier or residual?** **Ruled 2026-09-20 (confirmed
   first-person): (b) reported residual, with one hard edge** — a C8 breach becomes a
   disqualifier when the erroring worker also produced none of its declared output in the
   window (error + heartbeat + no output is a silent stall wearing a pulse, the mode C1
   cannot see). **Instrument for the edge:** for each breaching worker, its *declared output*
   is the blackboard entry types its `.intent/workers/<name>.yaml` mandate names
   (`post_finding` / `post_report` / observations — read at T0 and listed in the report);
   the edge trips when the worker has ≥ 1 breaching streak AND 0 blackboard entries of any
   declared output type in `[first error of the streak, T1)`, heartbeats excluded. Query:
   `SELECT count(*) FROM core.blackboard_entries WHERE worker_uuid = :uuid AND entry_type <>
   'heartbeat' AND created_at >= :streak_start AND created_at < :t1` — must be > 0, or the
   run is void.
6. **Verified before T0, not decided:** `draft` is retired on the live tree (enums, contracts,
   the blocking transition rule, 0 rows) — C6's subject is `pending`. Paper drift only:
   `CORE-Proposal.md` (draft ×5) and `CORE-Blackboard-State-Machine.md` (`lease_expires_at`
   ×3); tracked separately, not a soak condition.
