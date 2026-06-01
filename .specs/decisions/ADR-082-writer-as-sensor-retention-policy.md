<!-- path: .specs/decisions/ADR-082-writer-as-sensor-retention-policy.md -->

# ADR-082 — Writer-as-sensor retention policy

**Date:** 2026-06-01
**Status:** Accepted
**Author:** Darek (Dariusz Newecki)
**Drafter:** Claude (session 2026-06-01 — drafted under Path A execute-verb authorization, "yes, proceed with that plan")
**Grounding paper:** `papers/CORE-Blackboard-Architecture.md` — the writer-as-sensor pattern (rate-limited writer surfaces its own back-pressure as a blackboard finding) is a constitutional shape; this ADR adds the retention specification that ADR-070 D8 omitted.
**Related:** Issue #520 (broadened scope: this ADR generalizes its proposal to the writer-as-sensor class), ADR-044 (`llm_gate_verdicts` TTL precedent — the shape this ADR follows for terminal hygiene), ADR-070 D8 (the writer-as-sensor OPEN-finding pattern this ADR scopes retention for), ADR-081 Step 3a-telemetry (added `loop_hold.sample` as the first high-rate observability subject, made the concern concrete)

---

## Context

### Two surfaces that accumulate without a sweep

The blackboard hosts two related-but-distinct entry classes that grow without bound under current policy:

**Class A — terminal-status telemetry.** Writers post observability rows with `status='abandoned'` at creation (the `Worker.post_observation` contract). The row is terminal at the moment it lands; there is no remediation pathway, no further state transition, and no stale-alert generation (the #450 fix removed that loop). `loop_hold.sample::<stem>` is the canonical example: ADR-081 Step 3a-telemetry estimates ~13K rows/day under steady-state observation. The row stays in `core.blackboard_entries` forever.

**Class B — DELEGATE-class OPEN findings.** Writer-as-sensor rules (ADR-070 D8) emit `status='open'` findings for governor visibility when a rate limit or invariant fires. The rule's auto-remediation entry is `DELEGATE` — by design, no autonomous worker resolves them; the operator either acts on the surfaced concern or accepts the pacing. Three canonical examples on the current frame:

- `coherence.violation_executor.blast_bound` — one finding per over-cap cycle of `ViolationExecutorWorker`. Observed accumulation: 117 OPEN entries over 4 days (2026-05-29 → 2026-06-01) at ~1/hour cadence, with no resolved rows across the rule's lifetime.
- `coherence.repo_artifacts.drift` — orphan-row alerts from `RepoCrawlerWorker`. Same shape.
- `runtime.worker_process_classification` advisory findings (ADR-081 D7). Same shape — though current observation shows zero firings because heavy workers are correctly classified, the steady-state would accumulate identically once drift appears.

### The omission

ADR-070 D8 established the writer-as-sensor pattern (rate-limited writer surfaces its own back-pressure as a finding) without specifying retention. ADR-044 established a TTL pattern for `llm_gate_verdicts` cache rows but scoped it to that one table. ADR-081 Step 3a made the omission concrete by introducing the first high-rate observability subject. #520 surfaced the gap explicitly for Class A and left the door open ("a more general `blackboard.telemetry_ttl_days` if we want it to cover sibling observability subjects") for Class B.

The 117 `blast_bound` findings are the prompt-by-evidence: the gap is no longer theoretical.

### Why one ADR with two mechanisms, not two ADRs

Class A and Class B share the principle (writer-as-sensor produces governor-visibility blackboard rows that must declare retention) but require materially different mechanisms. Per memory `feedback_two_surface_requires_two_structures`, a unification claim that does not survive the material difference is the bug; **one** policy ADR governs the principle, **two** implementations satisfy it.

- **Class A → hard DELETE.** The row has no remaining governance meaning past TTL. ADR-044's `llm_gate_verdicts` precedent applies directly.
- **Class B → status transition `open → resolved`.** The row carries the governance signal "alert was raised, governor did not act within window." DELETE would be lossy and irreversible; transition preserves the audit trail and is the cheaper rollback path if TTL turns out to be misconfigured.

`abandoned` would also be a defensible terminal status for Class B but is rejected per `reference_blackboard_abandoned_two_semantics`: the column already overloads two meanings (sensor-by-design vs remediation-gave-up); adding TTL-timeout as a third would compound the conflation.

### Why the open finding's content is recoverable after auto-resolution

The writer-as-sensor pattern co-emits two rows per event: the OPEN finding (governor inbox) and a `<worker>.run.complete` report carrying the same payload as a `report`-typed row. `ViolationExecutorWorker.run()` posts `blast_bound: {cap, hit, deferred_files: N}` on every cycle that hits the bound; the same shape exists for `RepoCrawlerWorker` and for the ADR-081 D7 detector. The OPEN finding is purely the attention signal; the system of record is the report. Auto-resolving the attention signal therefore loses no evidence — the report row remains, and the OPEN entry retains its full payload, just with `status='resolved'` and a `payload.resolution` attribution block recording the TTL-sweep authority.

### Why BlackboardShopManager hosts the sweep

The worker already owns blackboard hygiene: it runs the SLA-tier stale detector and the `entry_stale` auto-resolve sweep. Per memory `feedback_protocols_reflex_check`, adding a new abstraction when an existing rule fits is the anti-pattern. `DbSyncWorker`'s ~5-minute cadence is too aggressive for a TTL-day-scale sweep (wasted DB pressure on a no-op `WHERE created_at < now() - 7 days` filter every 5 minutes); `BlackboardShopManager`'s 600s cadence (recently bumped per commit `5600becf`) is the right interval.

---

## Decisions

### D1 — Writer-as-sensor blackboard entries MUST declare retention

Any constitutional pattern that emits blackboard rows for governor visibility — whether terminal observation telemetry (Class A) or DELEGATE-class OPEN findings (Class B) — MUST specify a retention policy. The policy lives at `.intent/enforcement/config/operational_config.yaml`'s `blackboard:` section. The shape is two parallel allowlists, each paired with a TTL.

Absence from both allowlists is fail-closed: the sweep does not touch subjects it has not been told about. This preserves the existing constitutional surface for all non-listed subjects and bounds the blast radius of a misconfigured policy.

### D2 — Mechanism 1: terminal telemetry hard-DELETE

For rows whose subject begins with one of `blackboard.telemetry_subject_prefixes` AND status is in `('resolved', 'abandoned')` AND `created_at < now() - make_interval(days => telemetry_ttl_days)`: hard DELETE.

- Subject matching is `LIKE prefix || '%'` (prefix match). Allows `loop_hold.sample::<stem>` to match a single prefix without exhaustively enumerating every worker stem.
- Default `telemetry_ttl_days: 7`.
- Default `telemetry_subject_prefixes: ["loop_hold.sample::"]` — the only Class A subject ADR-081 has introduced.
- ADR-044 precedent on shape: hygiene, not correctness; tunable without semantic impact.

### D3 — Mechanism 2: DELEGATE OPEN finding status transition

For rows whose subject equals one of `blackboard.delegate_finding_subjects` AND status is `'open'` AND `created_at < now() - make_interval(days => delegate_finding_ttl_days)`: status transition `open → resolved` with `resolved_at = now()` and `payload.resolution` stamped:

```json
{
  "reason": "ADR-082 TTL sweep: governor inattention exceeded retention window",
  "resolved_by": "blackboard_shop_manager",
  "resolution_authority": "system.ttl_sweep",
  "resolved_at": "<ISO8601 UTC>"
}
```

- Subject matching is exact equality. The allowlist is closed; new DELEGATE subjects MUST be added explicitly. Prefix matching is reserved for Class A (telemetry stems vary across workers) — Class B subjects are governance-decided rule IDs and have no per-instance suffix.
- Default `delegate_finding_ttl_days: 7`.
- Default `delegate_finding_subjects`: `coherence.violation_executor.blast_bound`, `coherence.repo_artifacts.drift`. Each must be DELEGATE in `.intent/enforcement/remediation/auto_remediation.yaml` — the allowlist is a strict subset of `DELEGATE`-status rules. (ADR-081 D7's `runtime.worker_process_classification` is advisory and currently zero-emitting; it is not yet in the default allowlist and will be added if firings begin to accumulate.)
- Target status is `'resolved'`, not `'abandoned'`, per `reference_blackboard_abandoned_two_semantics`.

### D4 — Sweep host: BlackboardShopManager

`BlackboardShopManager.run()` invokes both sweeps once per cycle, between the existing `entry_stale` auto-resolve sweep (which addresses meta-noise) and the new stale-entry detection. The cycle's `blackboard_shop_manager.run.complete` report payload gains a `ttl_sweep` block recording the row counts swept per mechanism. Observability for the sweeps is the same blackboard surface the worker already uses.

Hosting on this worker preserves the constitutional rule that workers post to the blackboard and only the blackboard — the sweep methods on `BlackboardService` are Body-layer, called via the service registry.

### D5 — Row cap rail: `sweep_batch_max`

Both mechanisms accept a `batch_max` parameter sourced from `blackboard.sweep_batch_max` (default 500). The SQL uses a bounded subquery (`WHERE id IN (SELECT id … LIMIT :batch_max)`) so PostgreSQL's lack of `DELETE … LIMIT` is sidestepped without losing the cap.

The rail is required per `feedback_destructive_autonomous_needs_rails_first`: even with a TTL filter, a misconfigured prefix list or a sudden subject-shape change could otherwise scan and mutate millions of rows in one transaction. The cap caps the per-cycle blast; sustained backlogs drain over multiple cycles, matching the writer-as-sensor pacing principle.

### D6 — Empty allowlist is fail-closed

If `telemetry_subject_prefixes` is empty, Mechanism 1 is a no-op (returns 0). If `delegate_finding_subjects` is empty, Mechanism 2 is a no-op (returns 0). An operator who wants to disable a mechanism does so by emptying its allowlist in the YAML; no code change required, no flag to flip. Mirrors the enum-subset memory `feedback_enum_subset_canonicalize_and_fail_closed`: empty/missing fails closed.

### D7 — New subjects join the allowlist by ADR amendment

Adding a new subject to either allowlist is a governance act, not a runtime decision. The amendment can be a short addendum to this ADR or a new ADR cross-referencing it. The YAML edit alone is not a constitutional event — without the ADR text, future readers cannot reconstruct why the subject earned retention.

---

## Consequences

### Resolves issue #520

The acceptance criteria #520 lists are satisfied:

- TTL knob in `operational_config.yaml`'s `blackboard:` section ✓
- Periodic DELETE that respects the TTL ✓
- One ADR capturing the broader principle ✓ (this document)

`loop_hold.sample` rows past 7 days will be DELETEd at the start of the next `BlackboardShopManager` cycle. Steady-state row count for Class A is bounded by `(emission_rate × ttl_days)` plus the in-flight cycle, replacing the unbounded growth #520 projected (~4M rows/year at the upper bound).

### Bounds the 117 blast_bound backlog (gradual drain)

`coherence.violation_executor.blast_bound` OPEN findings older than 7 days will transition `open → resolved` at the next sweep cycle. The 117 backlog observed on 2026-06-01 spans 2026-05-29 → 2026-06-01 (oldest entry 3 days old) — at TTL=7 days, **none of the existing 117 drain on the first sweep cycle**; the oldest cross the window on 2026-06-05 and drain progressively over the following days, with steady-state thereafter capped at `(emission_rate × 7 days)` ≈ ~210 rows for the current ~30/day cadence. If the operator wants immediate drain of the existing backlog, the TTL can be lowered temporarily via `delegate_finding_ttl_days` in `operational_config.yaml`; the post_report row-of-record makes that safe. The `payload.resolution` block on swept rows makes them discoverable in either case.

### `coherence.repo_artifacts.drift` joins the same lifecycle

The third writer-as-sensor sibling — currently emitting at lower cadence per ADR-070 D8 orphan detection — gains the same retention treatment. No change to its emission semantics; only its lifecycle past TTL is now bounded.

### What the sweep does NOT do

- It does NOT change the writer's emission behavior. Class B continues to post fresh OPEN findings every cycle the rate limit fires; the system continues to surface back-pressure for the governor.
- It does NOT close the underlying violations. The 117 `blast_bound` findings drain not because the upstream queue stops over-running the cap, but because the OPEN findings are governor-attention signals whose attention window expired. The cap-vs-queue mismatch (queues consistently at 14–25 against a cap of 10) remains a separate governance question — addressed at the operator level by amending the cap, hunting upstream sensor over-emission, or accepting the pacing.
- It does NOT autonomously sweep heartbeat or report entries. Those have their own SLA lifecycle (BlackboardShopManager's existing stale detector) and do not match either allowlist by default.

### Audit trail integrity

For Class B, the swept row retains its full payload — only status, resolved_at, updated_at, and the appended `payload.resolution` block change. A future migration that wanted to re-open ttl_swept rows (e.g., raised TTL on the same allowlist) could do so deterministically by joining on `payload.resolution.resolution_authority = 'system.ttl_sweep'`. DELETE would have foreclosed that path; transition preserves it.

For Class A, the row is gone — but Class A rows were terminal observability with no governance signal beyond the moment of emission. The matching ADR-081 D7 detector queries `loop_hold.sample` with `ORDER BY created_at DESC LIMIT :cap` and a `cycle_window` of 5 — it only needs recent samples; old samples are noise.

### Sweep observability surfaces

The cycle's `blackboard_shop_manager.run.complete` report carries `payload.ttl_sweep.telemetry_deleted` and `payload.ttl_sweep.delegate_resolved` row counts. Operators inspect sweep activity via the same `core-admin workers blackboard` paths they already use; no new CLI surface needed.

### Misconfiguration recovery

A wrong subject in either allowlist results in (a) for Class A: terminal rows of the wrong subject get DELETEd — recoverable only via backup; (b) for Class B: OPEN findings of the wrong subject get auto-resolved — recoverable via SQL that reverts status='resolved' rows whose payload.resolution.resolution_authority is 'system.ttl_sweep'. The asymmetric blast radius is one reason Class B uses transition rather than DELETE; the asymmetry is also why both allowlists are closed (D7) rather than pattern-derived.

---

## Verification

- `core-admin code audit` PASS with no rule silently disabled (`Dispatch` baseline preserved per `feedback_honesty_gated_audit`).
- `ruff check` clean on `src/will/workers/blackboard_shop_manager.py`, `src/body/services/blackboard_service/blackboard_service.py`, `src/shared/infrastructure/intent/operational_config.py`.
- Smoke: `python -c "from shared.infrastructure.intent.operational_config import load_operational_config; c = load_operational_config().blackboard; assert c.telemetry_ttl_days == 7 and c.sweep_batch_max == 500"`.
- Post-restart observation: first `BlackboardShopManager.run.complete` log line carries `telemetry_swept=N, delegate_swept=M` shape with N and M matching the count of allowlist-matching rows past their respective TTLs (zero on 2026-06-01 since the 117 backlog's oldest row is 3 days old < 7-day TTL).
- SQL re-check after each sweep cycle: `SELECT COUNT(*) FROM core.blackboard_entries WHERE subject = 'coherence.violation_executor.blast_bound' AND status = 'open' AND created_at < now() - interval '7 days'` returns 0.
- Verified 2026-06-01 20:16 UTC: `core-daemon` restart clean; `BlackboardShopManager` first cycle posted `cycle complete — flagged=0, telemetry_swept=0, delegate_swept=0` (expected — no rows past TTL on first run); no errors in `_sweep_telemetry_ttl` or `_sweep_delegate_findings_ttl`.

---

## References

- Issue #520 — Class A surfacing (`loop_hold.sample` retention gap). Broadened by this ADR.
- Issue #519 — graceful-shutdown lag observation; the same `BlackboardShopManager` runtime context this ADR's sweeps operate within.
- ADR-044 — `llm_gate_verdicts` TTL precedent. Shape adopted for Mechanism 1.
- ADR-070 D8 — writer-as-sensor OPEN-finding pattern. Retention specification this ADR adds.
- ADR-081 — process-isolation classification; Step 3a-telemetry made the retention gap concrete by introducing `loop_hold.sample` as the first high-rate observability subject.
- Paper `CORE-Blackboard-Architecture.md` — the writer-as-sensor pattern is a first-class blackboard shape.
- Memory `feedback_destructive_autonomous_needs_rails_first` — the row-cap rail rationale.
- Memory `reference_blackboard_abandoned_two_semantics` — why D3 uses `resolved` and not `abandoned`.
- Memory `feedback_two_surface_requires_two_structures` — why one ADR governs two implementations rather than collapsing them or splitting into two ADRs.
- Memory `feedback_enum_subset_canonicalize_and_fail_closed` — empty allowlist fails closed.
- Memory `feedback_protocols_reflex_check` — why `BlackboardShopManager` hosts the sweep rather than a new abstraction.
